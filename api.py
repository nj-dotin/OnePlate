"""
OnePlate API Backend - Real-time data, webhooks, and third-party integrations.
FastAPI with WebSocket support for live dispatch tracking.
"""

from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, List, Any
from pathlib import Path
import os

# Import from OnePlate modules
import sys
sys.path.insert(0, str(Path(__file__).parent))

from app.data_store import PHRSStore
from app.route_optimization import greedy_assignment, build_route_summary
from app.supabase_client import get_supabase_client, SupabaseOps
from dotenv import load_dotenv

# Load environment
load_dotenv(Path(__file__).parent / ".env")

app = FastAPI(
    title="OnePlate API",
    description="Real-time food redistribution dispatch system",
    version="1.0.0"
)

# CORS configuration for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global store and active WebSocket connections
store: PHRSStore | None = None
supabase_ops: SupabaseOps | None = None
active_connections: List[WebSocket] = []
CLOUD_WRITE_REQUIRED = os.getenv("CLOUD_WRITE_REQUIRED", "true").lower() in {"1", "true", "yes"}


def normalize_cloud_payload(action: str, data: dict) -> dict[str, Any]:
    payload = dict(data)
    if action in {"dispatch_job", "update_dispatch"}:
        suggestion = payload.get("suggestion", {}) if isinstance(payload.get("suggestion"), dict) else {}
        payload = {
            "id": payload.get("id"),
            "food_id": suggestion.get("food_id"),
            "assigned_ngo_id": payload.get("ngo_id") or payload.get("assigned_ngo_id"),
            "ngo_name": payload.get("ngo_name"),
            "target_kind": suggestion.get("target_kind"),
            "target_id": suggestion.get("target_id"),
            "quantity": suggestion.get("suggested_qty", 0),
            "suggestion": suggestion,
            "pickup_otp": payload.get("pickup_otp"),
            "delivery_otp": payload.get("delivery_otp"),
            "pickup_verified": payload.get("pickup_verified", False),
            "delivery_verified": payload.get("delivery_verified", False),
            "status": payload.get("status", "created"),
            "created_at": payload.get("created_at"),
        }
    return payload


def cloud_write(action: str, data: dict[str, Any]) -> tuple[bool, str | None]:
    if not supabase_ops:
        return False, "Supabase client unavailable"
    payload = normalize_cloud_payload(action, data)
    result = None
    if action == "restaurant":
        result = supabase_ops.create_restaurant(payload)
    elif action == "food_listing":
        result = supabase_ops.create_food_listing(payload)
    elif action == "user_request":
        result = supabase_ops.create_user_request(payload)
    elif action == "dispatch_job":
        result = supabase_ops.create_dispatch_job(payload)
    elif action == "notification":
        result = supabase_ops.create_notification(payload)
    elif action == "impact_entry":
        result = supabase_ops.create_impact_entry(payload)
    elif action == "update_dispatch":
        result = supabase_ops.update_dispatch_job(payload["id"], payload)
    elif action == "update_food":
        result = supabase_ops.update_food_listing(payload["id"], payload)
    elif action == "update_request":
        result = supabase_ops.update_user_request(payload["id"], payload)
    elif action == "update_notification":
        result = supabase_ops.update_notification(payload["id"], payload)
    if result is not None:
        return True, None
    return False, supabase_ops.last_error


@app.on_event("startup")
async def startup():
    """Initialize the data store on app startup."""
    global store, supabase_ops
    store = PHRSStore.from_seed(Path(__file__).parent)
    
    # Try to load from Supabase
    supabase = get_supabase_client()
    if supabase:
        try:
            ops = SupabaseOps(supabase)
            supabase_ops = ops

            # Seed baseline refs once so all devices share the same demo base.
            if not ops.list_restaurants():
                for row in store.restaurants:
                    ops.create_restaurant(row)
            if not ops.list_ngos():
                for row in store.ngos:
                    ops.create_ngo(row)
            if not ops.list_companies():
                for row in store.companies:
                    ops.create_company(row)

            restaurants = ops.list_restaurants()
            ngos = ops.list_ngos()
            food_listings = ops.list_food_listings()
            user_requests = ops.list_user_requests()
            
            if restaurants:
                store.restaurants = restaurants
            if ngos:
                store.ngos = ngos
            if food_listings:
                store.food_listings = food_listings
            if user_requests:
                store.user_requests = user_requests
                
            print("✓ Loaded data from Supabase")
        except Exception as e:
            print(f"⚠ Could not load from Supabase: {e}, using local data")
    
    print(f"✓ OnePlate API started with {len(store.restaurants)} restaurants, {len(store.ngos)} NGOs")


# ============================================================================
# HEALTH & STATUS ENDPOINTS
# ============================================================================

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }


@app.get("/api/v1/status")
async def get_status():
    """Get system status and operational metrics."""
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")
    
    return {
        "system": {
            "status": "operational",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "data": {
            "restaurants": len(store.restaurants),
            "ngos": len(store.ngos),
            "food_listings": len(store.food_listings),
            "user_requests": len(store.user_requests),
            "dispatch_jobs": len(store.dispatch_jobs),
            "hotspots": len(store.hotspots),
        }
    }


# ============================================================================
# RESTAURANTS ENDPOINTS
# ============================================================================

@app.get("/api/v1/restaurants")
async def list_restaurants():
    """Get all restaurants."""
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")
    return {"data": store.restaurants}


@app.post("/api/v1/restaurants")
async def create_restaurant(name: str, latitude: float, longitude: float):
    """Create a new restaurant."""
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")
    
    restaurant = {
        "id": f"r{len(store.restaurants)}",
        "name": name,
        "lat": latitude,
        "lng": longitude,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if CLOUD_WRITE_REQUIRED:
        ok, err = cloud_write("restaurant", restaurant)
        if not ok:
            raise HTTPException(status_code=503, detail=f"Cloud write failed for restaurant: {err or 'unknown error'}")
    store.restaurants.append(restaurant)
    
    # Broadcast to WebSocket clients
    await broadcast({
        "event": "restaurant_created",
        "data": restaurant
    })
    
    return restaurant


# ============================================================================
# FOOD LISTINGS ENDPOINTS
# ============================================================================

@app.get("/api/v1/food-listings")
async def list_food_listings():
    """Get all food listings."""
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")
    
    store.refresh_listing_scores()
    return {"data": store.food_listings}


@app.post("/api/v1/food-listings")
async def create_food_listing(
    restaurant_id: str,
    food_type: str,
    quantity: int,
    cooked_minutes_ago: int = 30
):
    """Create a new food listing (surplus from restaurant)."""
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")
    
    from datetime import timedelta
    cooked_at = datetime.now(timezone.utc) - timedelta(minutes=cooked_minutes_ago)
    
    listing = store.add_food_listing(
        restaurant_id=restaurant_id,
        food_type=food_type,
        quantity=quantity,
        cooked_at_iso=cooked_at.isoformat(),
    )

    if CLOUD_WRITE_REQUIRED:
        ok, err = cloud_write("food_listing", listing)
        if not ok:
            store.food_listings = [row for row in store.food_listings if row.get("id") != listing.get("id")]
            raise HTTPException(status_code=503, detail=f"Cloud write failed for food listing: {err or 'unknown error'}")

    # Persist notification fanout too.
    for note in store.notifications:
        if note.get("source_id") == listing.get("id") and note.get("source_kind") == "food_listing":
            cloud_write("notification", note)
    
    # Broadcast to WebSocket clients
    await broadcast({
        "event": "food_listing_created",
        "data": listing
    })
    
    return listing


@app.get("/api/v1/food-listings/available")
async def get_available_listings():
    """Get available (not yet dispatched) food listings."""
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")
    
    available = [f for f in store.food_listings if f.get("status") == "available"]
    return {"data": available}


# ============================================================================
# USER REQUESTS ENDPOINTS
# ============================================================================

@app.get("/api/v1/requests")
async def list_requests():
    """Get all user requests."""
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")
    return {"data": store.user_requests}


@app.post("/api/v1/requests")
async def create_request(
    requester_name: str,
    quantity: int,
    latitude: float,
    longitude: float
):
    """Create a new food request."""
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")
    
    request = store.add_user_request(
        requester_name=requester_name,
        quantity_needed=quantity,
        lat=latitude,
        lng=longitude,
    )

    if CLOUD_WRITE_REQUIRED:
        ok, err = cloud_write("user_request", request)
        if not ok:
            store.user_requests = [row for row in store.user_requests if row.get("id") != request.get("id")]
            raise HTTPException(status_code=503, detail=f"Cloud write failed for request: {err or 'unknown error'}")

    for note in store.notifications:
        if note.get("source_id") == request.get("id") and note.get("source_kind") == "user_request":
            cloud_write("notification", note)
    
    # Broadcast to WebSocket clients
    await broadcast({
        "event": "request_created",
        "data": request
    })
    
    return request


# ============================================================================
# NGOs ENDPOINTS
# ============================================================================

@app.get("/api/v1/ngos")
async def list_ngos():
    """Get all NGOs."""
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")
    return {"data": store.ngos}


@app.get("/api/v1/ngos/{ngo_id}/notifications")
async def get_ngo_notifications(ngo_id: str):
    """Get notifications for an NGO."""
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")
    
    unread = [
        note for note in store.notifications
        if note.get("recipient_type") == "ngo"
        and note.get("recipient_id") == ngo_id
        and not note.get("is_read")
    ]
    return {"data": unread}


# ============================================================================
# DISPATCH JOBS ENDPOINTS
# ============================================================================

@app.get("/api/v1/dispatch-jobs")
async def list_dispatch_jobs():
    """Get all dispatch jobs."""
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")
    return {"data": store.dispatch_jobs}


@app.post("/api/v1/dispatch-jobs")
async def create_dispatch_job(background_tasks: BackgroundTasks):
    """Create a new dispatch job (automatic matching)."""
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")
    
    suggestions = store.suggest_matches()
    if not suggestions:
        raise HTTPException(status_code=400, detail="No matching suggestions available")
    
    if not store.ngos:
        raise HTTPException(status_code=400, detail="No NGOs available")
    
    job = store.create_dispatch(suggestions[0], ngo_id=store.ngos[0]["id"])

    if CLOUD_WRITE_REQUIRED:
        ok, err = cloud_write("dispatch_job", job)
        if not ok:
            store.dispatch_jobs = [row for row in store.dispatch_jobs if row.get("id") != job.get("id")]
            raise HTTPException(status_code=503, detail=f"Cloud write failed for dispatch job: {err or 'unknown error'}")

    for note in store.notifications:
        if note.get("source_id") == job.get("id") and note.get("source_kind") == "dispatch_job":
            cloud_write("notification", note)
    
    # Broadcast to WebSocket clients
    await broadcast({
        "event": "dispatch_created",
        "data": job
    })
    
    return job


@app.get("/api/v1/dispatch-jobs/{job_id}")
async def get_dispatch_job(job_id: str):
    """Get a specific dispatch job."""
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")
    
    job = store.dispatch_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Dispatch job not found")
    
    return job


@app.post("/api/v1/dispatch-jobs/{job_id}/verify-pickup")
async def verify_pickup(job_id: str, otp_code: str):
    """Verify pickup for a dispatch job."""
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")
    
    if store.verify_pickup(job_id, otp_code):
        job = store.dispatch_job_by_id(job_id)
        if isinstance(job, dict):
            cloud_write("update_dispatch", job)
        
        await broadcast({
            "event": "pickup_verified",
            "data": job
        })
        
        return {"success": True, "message": "Pickup verified"}
    
    raise HTTPException(status_code=400, detail="Invalid OTP or expired")


@app.post("/api/v1/dispatch-jobs/{job_id}/verify-delivery")
async def verify_delivery(job_id: str, otp_code: str):
    """Verify delivery for a dispatch job."""
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")
    
    if store.verify_delivery(job_id, otp_code):
        job = store.dispatch_job_by_id(job_id)
        if isinstance(job, dict):
            cloud_write("update_dispatch", job)

        if isinstance(job, dict):
            suggestion = job.get("suggestion", {}) if isinstance(job.get("suggestion"), dict) else {}
            food_id = suggestion.get("food_id")
            if food_id:
                listing = store.food_by_id(food_id)
                if listing:
                    cloud_write("update_food", listing)

        for entry in store.impact_ledger:
            if entry.get("event_ref") == job_id:
                cloud_write("impact_entry", entry)
        
        await broadcast({
            "event": "delivery_verified",
            "data": job
        })
        
        return {"success": True, "message": "Delivery verified, credits added"}
    
    raise HTTPException(status_code=400, detail="Invalid OTP or expired")


# ============================================================================
# ROUTE OPTIMIZATION ENDPOINTS
# ============================================================================

@app.get("/api/v1/routes/optimization")
async def get_optimized_routes():
    """Get optimized routes for all active dispatch jobs."""
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")
    
    # Build targets
    targets = []
    for req in store.user_requests:
        if req.get("status") == "open":
            targets.append({
                "id": req["id"],
                "name": req["requester_name"],
                "latitude": req.get("lat", 12.9712),
                "longitude": req.get("lng", 77.5941),
                "type": "request",
            })
    
    for hotspot in store.hotspots[:5]:
        targets.append({
            "id": hotspot["id"],
            "name": f"Hotspot {hotspot.get('zone', '?')}",
            "latitude": hotspot.get("latitude", 12.9712),
            "longitude": hotspot.get("longitude", 77.5941),
            "type": "hotspot",
        })
    
    # Run optimization
    assignments = greedy_assignment(
        store.dispatch_jobs,
        store.restaurants,
        store.ngos,
        targets
    )
    
    summary = build_route_summary(assignments)
    
    return {
        "summary": summary,
        "routes": assignments
    }


# ============================================================================
# IMPACT LEDGER ENDPOINTS
# ============================================================================

@app.get("/api/v1/impact-ledger")
async def get_impact_ledger():
    """Get impact metrics and credit ledger."""
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")
    
    return {
        "ledger": store.impact_ledger,
        "totals": {
            "restaurant_credits": store.total_credits("restaurant"),
            "ngo_credits": store.total_credits("ngo"),
            "company_credits": store.total_credits("company"),
        }
    }


# ============================================================================
# WEBHOOKS & INTEGRATIONS
# ============================================================================

@app.post("/api/v1/webhooks/register")
async def register_webhook(
    event_type: str,
    webhook_url: str,
    secret: str | None = None
):
    """Register a webhook for real-time events."""
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")
    
    webhook = {
        "id": f"wh_{len(getattr(store, 'webhooks', []))}",
        "event_type": event_type,
        "url": webhook_url,
        "secret": secret,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    
    if not hasattr(store, 'webhooks'):
        store.webhooks = []
    
    store.webhooks.append(webhook)
    
    return {
        "success": True,
        "webhook_id": webhook["id"],
        "message": f"Webhook registered for {event_type} events"
    }


# ============================================================================
# WEBSOCKET REAL-TIME UPDATES
# ============================================================================

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time dispatch updates."""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        # Send initial system state
        await websocket.send_json({
            "event": "connected",
            "data": {
                "restaurants": len(store.restaurants) if store else 0,
                "ngos": len(store.ngos) if store else 0,
                "active_jobs": len(store.dispatch_jobs) if store else 0,
            }
        })
        
        # Keep connection alive and listen for messages
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
            if data == "ping":
                await websocket.send_json({"event": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})
    
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        active_connections.remove(websocket)


async def broadcast(message: Dict[str, Any]):
    """Broadcast message to all connected WebSocket clients."""
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception as e:
            print(f"Error broadcasting to client: {e}")


# ============================================================================
# ROOT & DOCUMENTATION
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "OnePlate API",
        "version": "1.0.0",
        "description": "Real-time food redistribution dispatch system",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "status": "/api/v1/status",
            "restaurants": "/api/v1/restaurants",
            "food_listings": "/api/v1/food-listings",
            "requests": "/api/v1/requests",
            "dispatch": "/api/v1/dispatch-jobs",
            "routes": "/api/v1/routes/optimization",
            "impact": "/api/v1/impact-ledger",
            "websocket": "ws://localhost:8000/ws/live",
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
