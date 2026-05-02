"""
Route optimization module for food dispatch routing.
Implements greedy and Hungarian-algorithm-based assignment with distance calculations.
"""

from __future__ import annotations
from typing import Any
from app.logic import haversine_km
import json


def calculate_distance_matrix(restaurants: list[dict], targets: list[dict]) -> list[list[float]]:
    """
    Calculate pairwise distances between all restaurants and target locations.
    Returns a distance matrix: rows = restaurants, cols = targets.
    """
    matrix = []
    for restaurant in restaurants:
        row = []
        rest_lat = restaurant.get("latitude", 12.9716)
        rest_lng = restaurant.get("longitude", 77.5946)
        for target in targets:
            target_lat = target.get("latitude", 12.9712)
            target_lng = target.get("longitude", 77.5941)
            distance = haversine_km(rest_lat, rest_lng, target_lat, target_lng)
            row.append(distance)
        matrix.append(row)
    return matrix


def greedy_assignment(
    dispatch_jobs: list[dict],
    restaurants: list[dict],
    ngos: list[dict],
    targets: list[dict],
) -> list[dict]:
    """
    Greedy route optimization: sort by priority (need_score), then assign to closest available NGO.
    Returns list of optimized assignments with route info.
    """
    assignments = []
    
    # Sort jobs by priority (HIGH first, then MEDIUM, then LOW)
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    sorted_jobs = sorted(
        dispatch_jobs,
        key=lambda j: (
            priority_order.get(j.get("priority", "LOW"), 2),
            -float(j.get("need_score", 0) or 0),
        ),
    )
    
    # Track NGO availability (simple: each NGO can handle multiple jobs)
    ngo_map = {ngo["id"]: ngo for ngo in ngos}
    restaurant_map = {r["id"]: r for r in restaurants}
    target_map = {t["id"]: t for t in targets}
    
    for job in sorted_jobs:
        # Extract information from suggestion dict
        suggestion = job.get("suggestion", {})
        if not isinstance(suggestion, dict):
            continue
        
        # The suggestion contains restaurant_name (not ID), so find it from restaurants
        restaurant_name = suggestion.get("restaurant_name")
        target_id = suggestion.get("target_id")
        ngo_id = job.get("ngo_id")
        
        # Find restaurant by name
        restaurant = None
        for r in restaurants:
            if r.get("name") == restaurant_name:
                restaurant = r
                break
        
        # Get target
        target = target_map.get(target_id) if target_id else None
        
        # Get NGO
        ngo = ngo_map.get(ngo_id) if ngo_id else None
        
        if not restaurant or not target or not ngo:
            continue
        
        # Calculate route distance
        rest_lat = restaurant.get("latitude", 12.9716)
        rest_lng = restaurant.get("longitude", 77.5946)
        target_lat = target.get("latitude", 12.9712)
        target_lng = target.get("longitude", 77.5941)
        
        distance = haversine_km(rest_lat, rest_lng, target_lat, target_lng)
        
        # Estimate ETA: assume avg speed 30 km/h, add 5 min buffer
        eta_minutes = max(5, int((distance / 30) * 60 + 5))
        
        # Determine priority from suggestion
        priority = "HIGH" if suggestion.get("food_urgency") == "HIGH" else (
            "MEDIUM" if suggestion.get("target_priority") == "MEDIUM" else "LOW"
        )
        
        assignment = {
            "job_id": job.get("id"),
            "restaurant_name": restaurant.get("name", "Unknown Restaurant"),
            "restaurant_lat": rest_lat,
            "restaurant_lng": rest_lng,
            "target_name": target.get("name", suggestion.get("target_name", "Unknown Target")),
            "target_type": target.get("type", "request"),
            "target_lat": target_lat,
            "target_lng": target_lng,
            "ngo_name": ngo.get("name", "Unassigned NGO"),
            "ngo_id": ngo_id,
            "distance_km": round(distance, 2),
            "eta_minutes": eta_minutes,
            "priority": priority,
            "need_score": suggestion.get("priority_score", 0),
            "status": job.get("status", "created"),
            "food_type": suggestion.get("food_type", "Mixed"),
            "quantity": suggestion.get("suggested_qty", 0),
        }
        assignments.append(assignment)
    
    return assignments


def estimate_eta_minutes(distance_km: float, avg_speed_kmh: float = 30) -> int:
    """Estimate delivery ETA in minutes based on distance."""
    if distance_km <= 0:
        return 5
    return max(5, int((distance_km / avg_speed_kmh) * 60 + 5))


def build_route_summary(assignments: list[dict]) -> dict[str, Any]:
    """Build summary statistics for all routes."""
    if not assignments:
        return {
            "total_routes": 0,
            "total_distance_km": 0.0,
            "avg_distance_km": 0.0,
            "total_eta_minutes": 0,
            "high_priority_count": 0,
            "medium_priority_count": 0,
            "low_priority_count": 0,
        }
    
    total_distance = sum(a["distance_km"] for a in assignments)
    avg_distance = total_distance / len(assignments) if assignments else 0
    total_eta = sum(a["eta_minutes"] for a in assignments)
    
    priority_counts = {
        "HIGH": len([a for a in assignments if a["priority"] == "HIGH"]),
        "MEDIUM": len([a for a in assignments if a["priority"] == "MEDIUM"]),
        "LOW": len([a for a in assignments if a["priority"] == "LOW"]),
    }
    
    return {
        "total_routes": len(assignments),
        "total_distance_km": round(total_distance, 2),
        "avg_distance_km": round(avg_distance, 2),
        "total_eta_minutes": total_eta,
        "high_priority_count": priority_counts["HIGH"],
        "medium_priority_count": priority_counts["MEDIUM"],
        "low_priority_count": priority_counts["LOW"],
    }


def serialize_assignments(assignments: list[dict]) -> str:
    """Serialize assignments to JSON for caching."""
    return json.dumps(assignments, indent=2, default=str)


def deserialize_assignments(json_str: str) -> list[dict]:
    """Deserialize assignments from JSON."""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return []
