from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
import uuid

from app.logic import (
    haversine_km,
    match_priority,
    need_score,
    remaining_safe_minutes,
    safety_score,
    urgency_from_remaining,
)
from app.otp import OTPManager


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PHRSStore:
    restaurants: list[dict[str, Any]] = field(default_factory=list)
    ngos: list[dict[str, Any]] = field(default_factory=list)
    companies: list[dict[str, Any]] = field(default_factory=list)
    food_listings: list[dict[str, Any]] = field(default_factory=list)
    user_requests: list[dict[str, Any]] = field(default_factory=list)
    hotspots: list[dict[str, Any]] = field(default_factory=list)
    dispatch_jobs: list[dict[str, Any]] = field(default_factory=list)
    impact_ledger: list[dict[str, Any]] = field(default_factory=list)
    notifications: list[dict[str, Any]] = field(default_factory=list)
    otp_mgr: OTPManager = field(default_factory=OTPManager)

    @classmethod
    def from_seed(cls, root: str | Path = ".") -> "PHRSStore":
        root_path = Path(root)
        inst = cls()

        inst.restaurants = [
            {"id": "r1", "name": "Green Bowl", "lat": 12.9718, "lng": 77.5948, "impact_score": 74},
            {"id": "r2", "name": "Urban Thali", "lat": 12.9697, "lng": 77.5934, "impact_score": 68},
            {"id": "r3", "name": "City Meals", "lat": 12.9735, "lng": 77.5962, "impact_score": 71},
        ]

        inst.ngos = [
            {"id": "n1", "name": "Hope Relief", "lat": 12.9723, "lng": 77.5933, "reliability_score": 82},
            {"id": "n2", "name": "Meal Bridge", "lat": 12.9701, "lng": 77.5955, "reliability_score": 76},
        ]

        inst.companies = [
            {"id": "c1", "name": "Acme Foods Pvt Ltd", "sponsor_balance": 5000, "branding_name": "Acme Cares"}
        ]

        food_file = root_path / "data" / "sample_food.json"
        if food_file.exists():
            seed_food = json.loads(food_file.read_text(encoding="utf-8"))
            for item in seed_food:
                inst.add_food_listing(
                    restaurant_id=item["restaurant_id"],
                    food_type=item["food_type"],
                    quantity=int(item["quantity"]),
                    cooked_at_iso=item["time_cooked"],
                )

        req_file = root_path / "data" / "sample_requests.json"
        if req_file.exists():
            seed_reqs = json.loads(req_file.read_text(encoding="utf-8"))
            for req in seed_reqs:
                inst.add_user_request(
                    requester_name=req["requester_name"],
                    quantity_needed=int(req["quantity_needed"]),
                    lat=float(req["lat"]),
                    lng=float(req["lng"]),
                )

        return inst

    def restaurant_by_id(self, restaurant_id: str) -> dict[str, Any] | None:
        return next((r for r in self.restaurants if r["id"] == restaurant_id), None)

    def ngo_by_id(self, ngo_id: str) -> dict[str, Any] | None:
        return next((n for n in self.ngos if n["id"] == ngo_id), None)

    def food_by_id(self, food_id: str) -> dict[str, Any] | None:
        return next((f for f in self.food_listings if f["id"] == food_id), None)

    def request_by_id(self, request_id: str) -> dict[str, Any] | None:
        return next((r for r in self.user_requests if r["id"] == request_id), None)

    def hotspot_by_id(self, hotspot_id: str) -> dict[str, Any] | None:
        return next((h for h in self.hotspots if h["id"] == hotspot_id), None)

    def dispatch_job_by_id(self, job_id: str) -> dict[str, Any] | None:
        return next((j for j in self.dispatch_jobs if j["id"] == job_id), None)

    def add_notification(
        self,
        *,
        recipient_type: str,
        recipient_id: str,
        recipient_name: str,
        title: str,
        message: str,
        source_kind: str,
        source_id: str,
        source_label: str,
        is_read: bool = False,
    ) -> dict[str, Any]:
        notification = {
            "id": _id("note"),
            "recipient_type": recipient_type,
            "recipient_id": recipient_id,
            "recipient_name": recipient_name,
            "title": title,
            "message": message,
            "source_kind": source_kind,
            "source_id": source_id,
            "source_label": source_label,
            "is_read": is_read,
            "created_at": _now_iso(),
        }
        self.notifications.append(notification)
        return notification

    def notify_ngos(self, title: str, message: str, source_kind: str, source_id: str, source_label: str) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        for ngo in self.ngos:
            created.append(
                self.add_notification(
                    recipient_type="ngo",
                    recipient_id=ngo["id"],
                    recipient_name=ngo["name"],
                    title=title,
                    message=message,
                    source_kind=source_kind,
                    source_id=source_id,
                    source_label=source_label,
                )
            )
        return created

    def unread_notifications(self, recipient_type: str | None = None) -> list[dict[str, Any]]:
        rows = self.notifications
        if recipient_type is not None:
            rows = [row for row in rows if row["recipient_type"] == recipient_type]
        return [row for row in rows if not row.get("is_read")]

    def mark_notification_read(self, notification_id: str) -> bool:
        note = next((n for n in self.notifications if n["id"] == notification_id), None)
        if not note:
            return False
        note["is_read"] = True
        return True

    def mark_all_notifications_read(self, recipient_type: str | None = None) -> int:
        count = 0
        for note in self.notifications:
            if recipient_type is not None and note["recipient_type"] != recipient_type:
                continue
            if not note.get("is_read"):
                note["is_read"] = True
                count += 1
        return count

    def add_food_listing(self, restaurant_id: str, food_type: str, quantity: int, cooked_at_iso: str) -> dict[str, Any]:
        rest = self.restaurant_by_id(restaurant_id)
        if not rest:
            raise ValueError("Invalid restaurant")
        rem = remaining_safe_minutes(food_type, cooked_at_iso)
        sc = safety_score(food_type, cooked_at_iso)
        listing = {
            "id": _id("food"),
            "restaurant_id": restaurant_id,
            "restaurant_name": rest["name"],
            "food_type": food_type,
            "quantity_total": quantity,
            "quantity_available": quantity,
            "time_cooked": cooked_at_iso,
            "remaining_minutes": rem,
            "safety_score": sc,
            "urgency": urgency_from_remaining(rem),
            "status": "available" if quantity > 0 else "empty",
            "created_at": _now_iso(),
            "lat": rest["lat"],
            "lng": rest["lng"],
        }
        self.food_listings.append(listing)
        self.notify_ngos(
            title="New surplus posted",
            message=f"{rest['name']} added {quantity} plates of {food_type}.",
            source_kind="food_listing",
            source_id=listing["id"],
            source_label=rest["name"],
        )
        return listing

    def refresh_listing_scores(self) -> None:
        for item in self.food_listings:
            rem = remaining_safe_minutes(item["food_type"], item["time_cooked"])
            item["remaining_minutes"] = rem
            item["safety_score"] = safety_score(item["food_type"], item["time_cooked"])
            item["urgency"] = urgency_from_remaining(rem)
            if item["quantity_available"] <= 0:
                item["status"] = "empty"

    def add_user_request(self, requester_name: str, quantity_needed: int, lat: float, lng: float) -> dict[str, Any]:
        req = {
            "id": _id("req"),
            "requester_name": requester_name,
            "quantity_needed": quantity_needed,
            "lat": lat,
            "lng": lng,
            "status": "open",
            "created_at": _now_iso(),
        }
        self.user_requests.append(req)
        self.notify_ngos(
            title="Customer request arrived",
            message=f"{requester_name} requested {quantity_needed} plates and needs help now.",
            source_kind="user_request",
            source_id=req["id"],
            source_label=requester_name,
        )
        return req

    def set_hotspots(self, hotspots: list[dict[str, Any]]) -> None:
        self.hotspots = hotspots

    def open_targets(self) -> list[dict[str, Any]]:
        targets: list[dict[str, Any]] = []
        for req in self.user_requests:
            if req["status"] != "open":
                continue
            targets.append(
                {
                    "target_kind": "request",
                    "target_id": req["id"],
                    "name": req["requester_name"],
                    "lat": req["lat"],
                    "lng": req["lng"],
                    "need_score": float(req["quantity_needed"] * 8),
                    "quantity_needed": int(req["quantity_needed"]),
                    "priority": "MEDIUM",
                }
            )
        for hs in self.hotspots:
            targets.append(
                {
                    "target_kind": "hotspot",
                    "target_id": hs["id"],
                    "name": hs["zone"],
                    "lat": hs["lat"],
                    "lng": hs["lng"],
                    "need_score": float(hs["need_score"]),
                    "quantity_needed": max(5, int(hs["people_count"] * 2)),
                    "priority": hs["priority"],
                }
            )
        return targets

    def suggest_matches(self) -> list[dict[str, Any]]:
        self.refresh_listing_scores()
        active_food = [f for f in self.food_listings if f["status"] == "available" and f["quantity_available"] > 0]
        targets = self.open_targets()
        suggestions: list[dict[str, Any]] = []

        for target in targets:
            best: dict[str, Any] | None = None
            for food in active_food:
                dist = haversine_km(food["lat"], food["lng"], target["lat"], target["lng"])
                urgency_weight = 1.8 if food["urgency"] == "HIGH" else (1.3 if food["urgency"] == "MEDIUM" else 1.0)
                score = match_priority(
                    need=target["need_score"],
                    quantity=min(food["quantity_available"], target["quantity_needed"]),
                    distance_km=dist,
                    urgency_weight=urgency_weight,
                )
                candidate = {
                    "target_kind": target["target_kind"],
                    "target_id": target["target_id"],
                    "target_name": target["name"],
                    "food_id": food["id"],
                    "restaurant_name": food["restaurant_name"],
                    "food_type": food["food_type"],
                    "distance_km": round(dist, 2),
                    "suggested_qty": min(food["quantity_available"], target["quantity_needed"]),
                    "priority_score": score,
                    "food_urgency": food["urgency"],
                    "target_priority": target["priority"],
                }
                if best is None or candidate["priority_score"] > best["priority_score"]:
                    best = candidate
            if best:
                suggestions.append(best)

        suggestions.sort(key=lambda x: x["priority_score"], reverse=True)
        return suggestions

    def create_dispatch(self, suggestion: dict[str, Any], ngo_id: str) -> dict[str, Any]:
        ngo = self.ngo_by_id(ngo_id)
        if not ngo:
            raise ValueError("Invalid NGO")

        job = {
            "id": _id("job"),
            "suggestion": suggestion,
            "ngo_id": ngo_id,
            "ngo_name": ngo["name"],
            "status": "created",
            "pickup_verified": False,
            "delivery_verified": False,
            "created_at": _now_iso(),
        }
        self.dispatch_jobs.append(job)
        pickup_key = f"pickup:{job['id']}"
        delivery_key = f"delivery:{job['id']}"
        job["pickup_otp"] = self.otp_mgr.generate(pickup_key)
        job["delivery_otp"] = self.otp_mgr.generate(delivery_key)
        self.add_notification(
            recipient_type="ngo",
            recipient_id=ngo_id,
            recipient_name=ngo["name"],
            title="Dispatch assigned",
            message=f"A new dispatch is ready for {ngo['name']}: {suggestion['restaurant_name']} -> {suggestion['target_name']}.",
            source_kind="dispatch_job",
            source_id=job["id"],
            source_label=ngo["name"],
        )
        return job

    def verify_pickup(self, job_id: str, otp_code: str) -> bool:
        job = next((j for j in self.dispatch_jobs if j["id"] == job_id), None)
        if not job:
            return False
        ok = self.otp_mgr.verify(f"pickup:{job_id}", otp_code)
        if ok:
            job["pickup_verified"] = True
            job["status"] = "picked_up"
        return ok

    def verify_delivery(self, job_id: str, otp_code: str) -> bool:
        job = next((j for j in self.dispatch_jobs if j["id"] == job_id), None)
        if not job:
            return False
        ok = self.otp_mgr.verify(f"delivery:{job_id}", otp_code)
        if not ok:
            return False

        job["delivery_verified"] = True
        job["status"] = "delivered"
        s = job["suggestion"]
        listing = self.food_by_id(s["food_id"])
        if listing:
            listing["quantity_available"] = max(0, listing["quantity_available"] - int(s["suggested_qty"]))
            if listing["quantity_available"] == 0:
                listing["status"] = "empty"

        if s["target_kind"] == "request":
            req = self.request_by_id(s["target_id"])
            if req:
                req["status"] = "fulfilled"

        meals = int(s["suggested_qty"])
        credits = meals * 2
        self.impact_ledger.append(
            {
                "id": _id("ledger"),
                "actor_type": "restaurant",
                "actor_id": listing["restaurant_id"] if listing else "unknown",
                "meals_saved": meals,
                "credits_added": credits,
                "event_ref": job_id,
                "created_at": _now_iso(),
            }
        )
        self.impact_ledger.append(
            {
                "id": _id("ledger"),
                "actor_type": "ngo",
                "actor_id": job["ngo_id"],
                "meals_saved": meals,
                "credits_added": credits,
                "event_ref": job_id,
                "created_at": _now_iso(),
            }
        )
        self.impact_ledger.append(
            {
                "id": _id("ledger"),
                "actor_type": "company",
                "actor_id": self.companies[0]["id"] if self.companies else "none",
                "meals_saved": meals,
                "credits_added": credits,
                "event_ref": job_id,
                "created_at": _now_iso(),
            }
        )
        return True

    def total_credits(self, actor_type: str) -> int:
        return sum(row["credits_added"] for row in self.impact_ledger if row["actor_type"] == actor_type)
