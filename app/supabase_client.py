from __future__ import annotations

import os
from typing import Any

from postgrest import SyncPostgrestClient


class SupabaseClient:
    """Simple Supabase client using PostgREST."""
    
    def __init__(self, url: str, key: str) -> None:
        self.url = url
        self.key = key
        # Use sync client for simplicity
        self.client = SyncPostgrestClient(
            base_url=f"{url}/rest/v1",
            headers={"apikey": key, "Authorization": f"Bearer {key}"}
        )
    
    def table(self, name: str) -> Any:
        """Get a table reference."""
        return self.client.table(name)


def get_supabase_client() -> SupabaseClient | None:
    """Get Supabase client if credentials are available."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        return SupabaseClient(url, key)
    except Exception:
        return None


class SupabaseOps:
    """High-level Supabase operations for PHRS."""

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client
        self.last_error: str | None = None

    def _set_error(self, error: Exception) -> None:
        self.last_error = str(error)

    # ============= RESTAURANTS =============
    def list_restaurants(self) -> list[dict[str, Any]]:
        try:
            resp = self.client.table("restaurants").select("*").execute()
            rows = resp.data if resp.data else []
            for row in rows:
                if "lat" not in row:
                    row["lat"] = row.get("location_lat")
                if "lng" not in row:
                    row["lng"] = row.get("location_lng")
            return rows
        except Exception:
            return []

    def get_restaurant(self, restaurant_id: str) -> dict[str, Any] | None:
        try:
            resp = self.client.table("restaurants").select("*").eq("id", restaurant_id).execute()
            return resp.data[0] if resp.data else None
        except Exception:
            return None

    def create_restaurant(self, rest: dict[str, Any]) -> dict[str, Any] | None:
        try:
            payload = dict(rest)
            if "lat" in payload:
                payload["location_lat"] = payload.pop("lat")
            if "lng" in payload:
                payload["location_lng"] = payload.pop("lng")
            resp = self.client.table("restaurants").insert(payload).execute()
            return resp.data[0] if resp.data else None
        except Exception:
            return None

    # ============= NGOS =============
    def list_ngos(self) -> list[dict[str, Any]]:
        try:
            resp = self.client.table("ngos").select("*").execute()
            rows = resp.data if resp.data else []
            for row in rows:
                if "lat" not in row:
                    row["lat"] = row.get("location_lat")
                if "lng" not in row:
                    row["lng"] = row.get("location_lng")
            return rows
        except Exception:
            return []

    def create_ngo(self, ngo: dict[str, Any]) -> dict[str, Any] | None:
        try:
            payload = dict(ngo)
            if "lat" in payload:
                payload["location_lat"] = payload.pop("lat")
            if "lng" in payload:
                payload["location_lng"] = payload.pop("lng")
            resp = self.client.table("ngos").insert(payload).execute()
            return resp.data[0] if resp.data else None
        except Exception:
            return None

    def get_ngo(self, ngo_id: str) -> dict[str, Any] | None:
        try:
            resp = self.client.table("ngos").select("*").eq("id", ngo_id).execute()
            return resp.data[0] if resp.data else None
        except Exception:
            return None

    # ============= COMPANIES =============
    def list_companies(self) -> list[dict[str, Any]]:
        try:
            resp = self.client.table("companies").select("*").execute()
            return resp.data if resp.data else []
        except Exception:
            return []

    def create_company(self, company: dict[str, Any]) -> dict[str, Any] | None:
        try:
            resp = self.client.table("companies").insert(company).execute()
            return resp.data[0] if resp.data else None
        except Exception:
            return None

    def get_company(self, company_id: str) -> dict[str, Any] | None:
        try:
            resp = self.client.table("companies").select("*").eq("id", company_id).execute()
            return resp.data[0] if resp.data else None
        except Exception:
            return None

    # ============= FOOD LISTINGS =============
    def list_food_listings(self) -> list[dict[str, Any]]:
        try:
            resp = self.client.table("food_listings").select("*").order("created_at", desc=True).execute()
            rows = resp.data if resp.data else []
            for row in rows:
                if "lat" not in row and "location_lat" in row:
                    row["lat"] = row.get("location_lat")
                if "lng" not in row and "location_lng" in row:
                    row["lng"] = row.get("location_lng")
            return rows
        except Exception:
            return []

    def get_food_listing(self, food_id: str) -> dict[str, Any] | None:
        try:
            resp = self.client.table("food_listings").select("*").eq("id", food_id).execute()
            return resp.data[0] if resp.data else None
        except Exception:
            return None

    def create_food_listing(self, food: dict[str, Any]) -> dict[str, Any] | None:
        try:
            self.last_error = None
            payload = dict(food)
            resp = self.client.table("food_listings").insert(payload).execute()
            return resp.data[0] if resp.data else None
        except Exception as exc:
            err = str(exc)
            # Some deployments use location_lat/location_lng instead of lat/lng.
            if "Could not find the 'lat' column" in err or "Could not find the 'lng' column" in err:
                try:
                    payload = dict(food)
                    if "lat" in payload:
                        payload["location_lat"] = payload.pop("lat")
                    if "lng" in payload:
                        payload["location_lng"] = payload.pop("lng")
                    self.last_error = None
                    resp = self.client.table("food_listings").insert(payload).execute()
                    return resp.data[0] if resp.data else None
                except Exception as retry_exc:
                    retry_err = str(retry_exc)
                    if "Could not find the 'location_lat' column" in retry_err or "Could not find the 'location_lng' column" in retry_err:
                        try:
                            payload = dict(food)
                            for key in ("lat", "lng", "location_lat", "location_lng"):
                                payload.pop(key, None)
                            self.last_error = None
                            resp = self.client.table("food_listings").insert(payload).execute()
                            return resp.data[0] if resp.data else None
                        except Exception as final_exc:
                            self._set_error(final_exc)
                            return None
                    self._set_error(retry_exc)
                    return None
            self._set_error(exc)
            return None

    def update_food_listing(self, food_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        try:
            self.last_error = None
            payload = dict(updates)
            resp = self.client.table("food_listings").update(payload).eq("id", food_id).execute()
            return resp.data[0] if resp.data else None
        except Exception as exc:
            err = str(exc)
            if "Could not find the 'lat' column" in err or "Could not find the 'lng' column" in err:
                try:
                    payload = dict(updates)
                    if "lat" in payload:
                        payload["location_lat"] = payload.pop("lat")
                    if "lng" in payload:
                        payload["location_lng"] = payload.pop("lng")
                    self.last_error = None
                    resp = self.client.table("food_listings").update(payload).eq("id", food_id).execute()
                    return resp.data[0] if resp.data else None
                except Exception as retry_exc:
                    retry_err = str(retry_exc)
                    if "Could not find the 'location_lat' column" in retry_err or "Could not find the 'location_lng' column" in retry_err:
                        try:
                            payload = dict(updates)
                            for key in ("lat", "lng", "location_lat", "location_lng"):
                                payload.pop(key, None)
                            self.last_error = None
                            resp = self.client.table("food_listings").update(payload).eq("id", food_id).execute()
                            return resp.data[0] if resp.data else None
                        except Exception as final_exc:
                            self._set_error(final_exc)
                            return None
                    self._set_error(retry_exc)
                    return None
            self._set_error(exc)
            return None

    # ============= USER REQUESTS =============
    def list_user_requests(self) -> list[dict[str, Any]]:
        try:
            resp = self.client.table("user_requests").select("*").order("created_at", desc=True).execute()
            return resp.data if resp.data else []
        except Exception:
            return []

    def get_user_request(self, request_id: str) -> dict[str, Any] | None:
        try:
            resp = self.client.table("user_requests").select("*").eq("id", request_id).execute()
            return resp.data[0] if resp.data else None
        except Exception:
            return None

    def create_user_request(self, req: dict[str, Any]) -> dict[str, Any] | None:
        try:
            self.last_error = None
            resp = self.client.table("user_requests").insert(req).execute()
            return resp.data[0] if resp.data else None
        except Exception as exc:
            self._set_error(exc)
            return None

    def update_user_request(self, request_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        try:
            self.last_error = None
            resp = self.client.table("user_requests").update(updates).eq("id", request_id).execute()
            return resp.data[0] if resp.data else None
        except Exception as exc:
            self._set_error(exc)
            return None

    # ============= NOTIFICATIONS =============
    def list_notifications(self) -> list[dict[str, Any]]:
        try:
            resp = self.client.table("notifications").select("*").order("created_at", desc=True).execute()
            return resp.data if resp.data else []
        except Exception:
            return []

    def create_notification(self, notification: dict[str, Any]) -> dict[str, Any] | None:
        try:
            self.last_error = None
            resp = self.client.table("notifications").insert(notification).execute()
            return resp.data[0] if resp.data else None
        except Exception as exc:
            self._set_error(exc)
            return None

    def update_notification(self, notification_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        try:
            self.last_error = None
            resp = self.client.table("notifications").update(updates).eq("id", notification_id).execute()
            return resp.data[0] if resp.data else None
        except Exception as exc:
            self._set_error(exc)
            return None

    # ============= HOTSPOTS =============
    def list_hotspots(self) -> list[dict[str, Any]]:
        try:
            resp = self.client.table("hotspots").select("*").order("time_detected", desc=True).execute()
            return resp.data if resp.data else []
        except Exception:
            return []

    def upsert_hotspots(self, hotspots: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not hotspots:
            return []
        try:
            resp = self.client.table("hotspots").upsert(hotspots).execute()
            return resp.data if resp.data else []
        except Exception:
            return []

    # ============= DISPATCH JOBS =============
    def list_dispatch_jobs(self) -> list[dict[str, Any]]:
        try:
            resp = self.client.table("dispatch_jobs").select("*").order("created_at", desc=True).execute()
            return resp.data if resp.data else []
        except Exception:
            return []

    def get_dispatch_job(self, job_id: str) -> dict[str, Any] | None:
        try:
            resp = self.client.table("dispatch_jobs").select("*").eq("id", job_id).execute()
            return resp.data[0] if resp.data else None
        except Exception:
            return None

    def create_dispatch_job(self, job: dict[str, Any]) -> dict[str, Any] | None:
        try:
            self.last_error = None
            resp = self.client.table("dispatch_jobs").insert(job).execute()
            return resp.data[0] if resp.data else None
        except Exception as exc:
            self._set_error(exc)
            return None

    def update_dispatch_job(self, job_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        try:
            self.last_error = None
            resp = self.client.table("dispatch_jobs").update(updates).eq("id", job_id).execute()
            return resp.data[0] if resp.data else None
        except Exception as exc:
            self._set_error(exc)
            return None

    # ============= IMPACT LEDGER =============
    def list_impact_ledger(self) -> list[dict[str, Any]]:
        try:
            resp = self.client.table("impact_ledger").select("*").order("created_at", desc=True).execute()
            return resp.data if resp.data else []
        except Exception:
            return []

    def create_impact_entry(self, entry: dict[str, Any]) -> dict[str, Any] | None:
        try:
            self.last_error = None
            resp = self.client.table("impact_ledger").insert(entry).execute()
            return resp.data[0] if resp.data else None
        except Exception as exc:
            self._set_error(exc)
            return None

    def total_credits(self, actor_type: str) -> int:
        try:
            resp = self.client.table("impact_ledger").select("credits_added").eq("actor_type", actor_type).execute()
            if not resp.data:
                return 0
            return sum(row.get("credits_added", 0) for row in resp.data)
        except Exception:
            return 0
