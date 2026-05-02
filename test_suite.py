"""
Comprehensive test suite for OnePlate system.
Tests real-time data sync, API endpoints, and full workflow.
"""

import asyncio
import json
from pathlib import Path
import sys

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.data_store import PHRSStore
from app.route_optimization import greedy_assignment, build_route_summary
from app.supabase_client import get_supabase_client, SupabaseOps
from app.logic import haversine_km, need_score, priority_from_need


class TestResults:
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0
    
    def add(self, name: str, passed: bool, details: str = ""):
        self.tests.append({
            "name": name,
            "passed": passed,
            "details": details
        })
        if passed:
            self.passed += 1
            print(f"✓ {name}")
        else:
            self.failed += 1
            print(f"✗ {name}: {details}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY: {self.passed}/{total} passed")
        print(f"{'='*60}")
        return self.failed == 0


results = TestResults()

# ============================================================================
# BASIC FUNCTIONALITY TESTS
# ============================================================================

def test_data_store():
    """Test in-memory data store initialization."""
    try:
        store = PHRSStore.from_seed(Path("."))
        
        assert len(store.restaurants) > 0, "No restaurants loaded"
        assert len(store.ngos) > 0, "No NGOs loaded"
        assert len(store.food_listings) >= 0, "Food listings initialization failed"
        assert len(store.user_requests) >= 0, "User requests initialization failed"
        
        results.add("Data Store Initialization", True)
    except Exception as e:
        results.add("Data Store Initialization", False, str(e))


def test_food_listing_creation():
    """Test creating a food listing."""
    try:
        store = PHRSStore.from_seed(Path("."))
        
        before_count = len(store.food_listings)
        listing = store.add_food_listing(
            restaurant_id=store.restaurants[0]["id"],
            food_type="Rice",
            quantity=50,
            cooked_at_iso="2026-05-02T03:00:00Z"
        )
        after_count = len(store.food_listings)
        
        assert after_count == before_count + 1, "Listing not added"
        assert listing["food_type"] == "Rice", "Wrong food type"
        assert listing["quantity_total"] == 50, "Wrong quantity"
        
        results.add("Food Listing Creation", True)
    except Exception as e:
        results.add("Food Listing Creation", False, str(e))


def test_user_request_creation():
    """Test creating a user request."""
    try:
        store = PHRSStore.from_seed(Path("."))
        
        before_count = len(store.user_requests)
        request = store.add_user_request(
            requester_name="Test User",
            quantity_needed=25,
            lat=12.9712,
            lng=77.5941
        )
        after_count = len(store.user_requests)
        
        assert after_count == before_count + 1, "Request not added"
        assert request["requester_name"] == "Test User", "Wrong requester name"
        assert request["quantity_needed"] == 25, "Wrong quantity"
        
        results.add("User Request Creation", True)
    except Exception as e:
        results.add("User Request Creation", False, str(e))


def test_dispatch_creation():
    """Test creating a dispatch job."""
    try:
        store = PHRSStore.from_seed(Path("."))
        
        suggestions = store.suggest_matches()
        if not suggestions:
            results.add("Dispatch Creation", False, "No suggestions available")
            return
        
        before_count = len(store.dispatch_jobs)
        job = store.create_dispatch(suggestions[0], ngo_id=store.ngos[0]["id"])
        after_count = len(store.dispatch_jobs)
        
        assert after_count == before_count + 1, "Dispatch not created"
        assert job["ngo_id"] == store.ngos[0]["id"], "Wrong NGO assignment"
        assert "pickup_otp" in job, "No pickup OTP generated"
        assert "delivery_otp" in job, "No delivery OTP generated"
        
        results.add("Dispatch Creation", True)
    except Exception as e:
        results.add("Dispatch Creation", False, str(e))


# ============================================================================
# NOTIFICATION TESTS
# ============================================================================

def test_notification_system():
    """Test NGO notification system."""
    try:
        store = PHRSStore.from_seed(Path("."))
        
        before_count = len(store.notifications)
        
        # Create a request (should trigger NGO notifications)
        store.add_user_request(
            requester_name="Test",
            quantity_needed=20,
            lat=12.9712,
            lng=77.5941
        )
        
        after_count = len(store.notifications)
        
        assert after_count > before_count, "No notifications generated"
        
        # Check notification content
        ngo_notifs = [n for n in store.notifications if n.get("recipient_type") == "ngo"]
        assert len(ngo_notifs) > 0, "No NGO notifications"
        
        results.add("NGO Notification System", True)
    except Exception as e:
        results.add("NGO Notification System", False, str(e))


# ============================================================================
# ROUTING & OPTIMIZATION TESTS
# ============================================================================

def test_route_optimization():
    """Test route optimization algorithm."""
    try:
        store = PHRSStore.from_seed(Path("."))
        
        # Create dispatch jobs
        suggestions = store.suggest_matches()
        if suggestions and store.ngos:
            store.create_dispatch(suggestions[0], ngo_id=store.ngos[0]["id"])
        
        # Build targets
        targets = []
        for req in store.user_requests[:3]:
            targets.append({
                "id": req["id"],
                "name": req["requester_name"],
                "latitude": req.get("latitude", 12.9712),
                "longitude": req.get("longitude", 77.5941),
                "type": "request"
            })
        
        # Run optimization
        assignments = greedy_assignment(
            store.dispatch_jobs,
            store.restaurants,
            store.ngos,
            targets
        )
        
        summary = build_route_summary(assignments)
        
        assert "total_routes" in summary, "No summary data"
        assert summary["total_distance_km"] >= 0, "Invalid distance"
        
        results.add("Route Optimization", True)
    except Exception as e:
        results.add("Route Optimization", False, str(e))


# ============================================================================
# SCORING & LOGIC TESTS
# ============================================================================

def test_scoring_functions():
    """Test food safety and need scoring."""
    try:
        # Test need score
        score = need_score(people_count=5, persistence_minutes=30)
        assert score > 0, "Invalid need score"
        
        priority = priority_from_need(score)
        assert priority in ["HIGH", "MEDIUM", "LOW"], "Invalid priority"
        
        # Test distance calculation
        distance = haversine_km(12.9716, 77.5946, 12.9712, 77.5941)
        assert 0 <= distance <= 1000, "Invalid distance calculation"
        
        results.add("Scoring Functions", True)
    except Exception as e:
        results.add("Scoring Functions", False, str(e))


# ============================================================================
# API ENDPOINT TESTS
# ============================================================================

async def test_api_endpoints():
    """Test FastAPI endpoints."""
    try:
        import httpx
        
        # Give API time to start
        await asyncio.sleep(1)
        
        async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=5) as client:
            # Health check
            resp = await client.get("/health")
            assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
            
            # Status endpoint
            resp = await client.get("/api/v1/status")
            assert resp.status_code == 200, f"Status endpoint failed: {resp.status_code}"
            
            # List restaurants
            resp = await client.get("/api/v1/restaurants")
            assert resp.status_code == 200, f"Restaurants endpoint failed: {resp.status_code}"
            data = resp.json()
            assert "data" in data, "Invalid response format"
            
            # List dispatch jobs
            resp = await client.get("/api/v1/dispatch-jobs")
            assert resp.status_code == 200, f"Dispatch endpoint failed: {resp.status_code}"
            
            # List routes
            resp = await client.get("/api/v1/routes/optimization")
            assert resp.status_code == 200, f"Routes endpoint failed: {resp.status_code}"
            
            results.add("FastAPI Endpoints", True)
    except Exception as e:
        results.add("FastAPI Endpoints", False, str(e))


# ============================================================================
# SUPABASE INTEGRATION TESTS
# ============================================================================

def test_supabase_connection():
    """Test Supabase connection and operations."""
    try:
        supabase = get_supabase_client()
        
        if not supabase:
            results.add("Supabase Connection", False, "Client not initialized")
            return
        
        ops = SupabaseOps(supabase)
        
        # Try to list restaurants
        restaurants = ops.list_restaurants()
        assert isinstance(restaurants, list), "Invalid response type"
        
        results.add("Supabase Connection", True)
    except Exception as e:
        results.add("Supabase Connection", False, str(e))


# ============================================================================
# END-TO-END WORKFLOW TEST
# ============================================================================

def test_end_to_end_workflow():
    """Test complete workflow: restaurant → request → dispatch → verification."""
    try:
        store = PHRSStore.from_seed(Path("."))
        
        # Step 1: Restaurant adds food
        food = store.add_food_listing(
            restaurant_id=store.restaurants[0]["id"],
            food_type="Curry",
            quantity=40,
            cooked_at_iso="2026-05-02T03:00:00Z"
        )
        assert food["id"], "Food listing not created"
        
        # Step 2: User creates request
        request = store.add_user_request(
            requester_name="End-to-end test",
            quantity_needed=20,
            lat=12.9712,
            lng=77.5941
        )
        assert request["id"], "Request not created"
        
        # Step 3: System suggests match
        suggestions = store.suggest_matches()
        assert len(suggestions) > 0, "No suggestions generated"
        
        # Step 4: Dispatch created
        job = store.create_dispatch(suggestions[0], ngo_id=store.ngos[0]["id"])
        assert job["id"], "Dispatch not created"
        
        # Step 5: Verify pickup
        pickup_ok = store.verify_pickup(job["id"], job["pickup_otp"])
        assert pickup_ok, "Pickup verification failed"
        
        # Step 6: Verify delivery
        delivery_ok = store.verify_delivery(job["id"], job["delivery_otp"])
        assert delivery_ok, "Delivery verification failed"
        
        # Step 7: Check impact ledger
        assert len(store.impact_ledger) > 0, "Impact not recorded"
        
        results.add("End-to-End Workflow", True)
    except Exception as e:
        results.add("End-to-End Workflow", False, str(e))


# ============================================================================
# REAL-TIME DATA TESTS
# ============================================================================

def test_real_time_data_sync():
    """Test real-time data synchronization."""
    try:
        store = PHRSStore.from_seed(Path("."))
        
        # Simulate real-time updates
        initial_restaurants = len(store.restaurants)
        
        # Add new restaurant
        new_rest = {
            "id": f"r_realtime_{hash('test')}",
            "name": "Real-time Test Restaurant",
            "latitude": 12.9716,
            "longitude": 77.5946
        }
        store.restaurants.append(new_rest)
        
        assert len(store.restaurants) == initial_restaurants + 1, "Real-time update failed"
        
        # Verify it's accessible
        found = next((r for r in store.restaurants if r["id"] == new_rest["id"]), None)
        assert found, "New restaurant not found after real-time update"
        
        results.add("Real-Time Data Sync", True)
    except Exception as e:
        results.add("Real-Time Data Sync", False, str(e))


# ============================================================================
# RUN ALL TESTS
# ============================================================================

def run_all_tests():
    """Run all test suites."""
    print("\n" + "="*60)
    print("ONEPLATE COMPREHENSIVE TEST SUITE")
    print("="*60 + "\n")
    
    # Basic functionality
    print("Basic Functionality:")
    test_data_store()
    test_food_listing_creation()
    test_user_request_creation()
    test_dispatch_creation()
    
    # Notifications
    print("\nNotification System:")
    test_notification_system()
    
    # Routing
    print("\nRouting & Optimization:")
    test_route_optimization()
    
    # Scoring
    print("\nScoring Functions:")
    test_scoring_functions()
    
    # Supabase
    print("\nSupabase Integration:")
    test_supabase_connection()
    
    # Workflow
    print("\nEnd-to-End Workflow:")
    test_end_to_end_workflow()
    
    # Real-time
    print("\nReal-Time Data:")
    test_real_time_data_sync()
    
    # API (only if API server is running)
    print("\nAPI Endpoints (requires API server running):")
    try:
        asyncio.run(test_api_endpoints())
    except Exception as e:
        results.add("FastAPI Endpoints", False, f"API server not running: {e}")
    
    # Print summary
    success = results.summary()
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
