from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Dict


FOOD_SAFE_MINUTES: Dict[str, int] = {
    "rice": 240,
    "chapati": 300,
    "bread": 240,
    "curry": 180,
    "dal": 240,
    "vegetable": 240,
    "meat": 120,
    "default": 180,
}

FOOD_RISK_FACTOR: Dict[str, float] = {
    "rice": 1.0,
    "chapati": 0.8,
    "bread": 0.9,
    "curry": 1.2,
    "dal": 1.0,
    "vegetable": 1.0,
    "meat": 1.6,
    "default": 1.1,
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def safe_minutes_for_food(food_type: str) -> int:
    key = (food_type or "").strip().lower()
    return FOOD_SAFE_MINUTES.get(key, FOOD_SAFE_MINUTES["default"])


def risk_for_food(food_type: str) -> float:
    key = (food_type or "").strip().lower()
    return FOOD_RISK_FACTOR.get(key, FOOD_RISK_FACTOR["default"])


def elapsed_minutes(cooked_at_iso: str, now: datetime | None = None) -> int:
    current = now or now_utc()
    cooked_at = parse_dt_iso(cooked_at_iso)
    seconds = max(0, (current - cooked_at).total_seconds())
    return int(seconds // 60)


def remaining_safe_minutes(food_type: str, cooked_at_iso: str, now: datetime | None = None) -> int:
    total_safe = safe_minutes_for_food(food_type)
    elapsed = elapsed_minutes(cooked_at_iso, now)
    return max(0, total_safe - elapsed)


def safety_score(food_type: str, cooked_at_iso: str, now: datetime | None = None) -> int:
    elapsed = elapsed_minutes(cooked_at_iso, now)
    risk = risk_for_food(food_type)
    score = 100.0 - (0.22 * elapsed * risk)
    return max(0, min(100, int(round(score))))


def urgency_from_remaining(remaining_minutes_value: int) -> str:
    if remaining_minutes_value <= 45:
        return "HIGH"
    if remaining_minutes_value <= 120:
        return "MEDIUM"
    return "LOW"


def need_score(people_count: int, persistence_minutes: int, alpha: float = 6.0, beta: float = 2.0) -> float:
    return round(alpha * max(0, people_count) + beta * max(0, persistence_minutes), 2)


def priority_from_need(score: float) -> str:
    if score > 70:
        return "HIGH"
    if score > 30:
        return "MEDIUM"
    return "LOW"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(max(1e-12, 1 - a)))
    return r * c


def match_priority(need: float, quantity: int, distance_km: float, urgency_weight: float = 1.0) -> float:
    safe_distance = max(0.2, distance_km)
    return round((need * max(1, quantity) * urgency_weight) / safe_distance, 2)
