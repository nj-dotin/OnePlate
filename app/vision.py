from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from app.logic import need_score, priority_from_need


ZONE_COORDS = {
    "Zone A": {"lat": 12.9716, "lng": 77.5946},
    "Zone B": {"lat": 12.9721, "lng": 77.5930},
    "Zone C": {"lat": 12.9694, "lng": 77.5969},
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_thumbnail_path(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def normalize_hotspot_row(row: dict[str, Any], index: int = 0) -> dict[str, Any]:
    zone = str(row.get("zone") or f"Zone {index + 1}")
    people_count = int(row.get("people_count", 0))
    persistence = int(row.get("persistence_minutes", 0))
    coords = ZONE_COORDS.get(zone, {"lat": 12.9716, "lng": 77.5946})
    score = float(row.get("need_score", need_score(people_count, persistence)))
    normalized = {
        "id": str(row.get("id") or f"hotspot_{zone.lower().replace(' ', '_')}_{index + 1}"),
        "zone": zone,
        "people_count": people_count,
        "persistence_minutes": persistence,
        "need_score": score,
        "priority": str(row.get("priority") or priority_from_need(score)),
        "lat": float(row.get("lat", coords["lat"])),
        "lng": float(row.get("lng", coords["lng"])),
        "time_detected": str(row.get("time_detected") or _now_iso()),
    }

    for key in (
        "detection_hits",
        "frames_observed",
        "best_confidence",
        "first_seen_frame",
        "last_seen_frame",
        "thumbnail_path",
        "source",
    ):
        if key in row:
            value = row[key]
            normalized[key] = _normalize_thumbnail_path(value) if key == "thumbnail_path" else value

    return normalized


def load_hotspots_from_json(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []

    raw = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        rows = raw.get("hotspots", [])
    elif isinstance(raw, list):
        rows = raw
    else:
        return []

    if not isinstance(rows, list):
        return []

    return [normalize_hotspot_row(row, index) for index, row in enumerate(rows) if isinstance(row, dict)]


def save_hotspots_to_json(
    path: str | Path,
    hotspots: list[dict[str, Any]],
    *,
    metadata: dict[str, Any] | None = None,
) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(metadata or {})
    payload.setdefault("generated_at", _now_iso())
    payload["count"] = len(hotspots)
    payload["hotspots"] = [normalize_hotspot_row(row, index) for index, row in enumerate(hotspots)]
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


def build_hotspots_from_zone_stats(zone_stats: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for zone, stats in zone_stats.items():
        people = int(stats.get("people_count", 0))
        persistence = int(stats.get("persistence_minutes", 0))
        score = need_score(people, persistence)
        coords = ZONE_COORDS.get(zone, {"lat": 12.9716, "lng": 77.5946})
        row = {
            "id": f"hotspot_{zone.lower().replace(' ', '_')}",
            "zone": zone,
            "people_count": people,
            "persistence_minutes": persistence,
            "need_score": score,
            "priority": priority_from_need(score),
            "lat": coords["lat"],
            "lng": coords["lng"],
            "time_detected": _now_iso(),
        }
        for key in (
            "detection_hits",
            "frames_observed",
            "best_confidence",
            "first_seen_frame",
            "last_seen_frame",
            "thumbnail_path",
            "source",
        ):
            if key in stats:
                value = stats[key]
                row[key] = _normalize_thumbnail_path(value) if key == "thumbnail_path" else value
        rows.append(row)
    return rows


def _write_zone_thumbnail(frame: Any, thumbnail_root: Path, video_path: str, zone: str, frame_idx: int) -> str:
    import cv2

    thumbnail_root.mkdir(parents=True, exist_ok=True)
    thumb_name = f"{Path(video_path).stem}_{zone.lower().replace(' ', '_')}.jpg"
    thumb_path = thumbnail_root / thumb_name
    annotated = frame.copy()
    h, w = annotated.shape[:2]

    # Determine zone horizontal bounds
    left = w // 3
    mid = (2 * w) // 3
    if zone == "Zone A":
        zx0, zx1 = 0, left
    elif zone == "Zone B":
        zx0, zx1 = left, mid
    else:
        zx0, zx1 = mid, w

    # Add margins inside the zone for the staging box
    margin_x = max(12, int(0.04 * w))
    bx0 = max(zx0 + margin_x, 0)
    bx1 = min(zx1 - margin_x, w)
    box_width = max(bx1 - bx0, int(0.15 * w))
    box_height = int(h * 0.45)
    by0 = max((h - box_height) // 2, 0)
    by1 = min(by0 + box_height, h)

    # Draw translucent fill for staging box
    overlay = annotated.copy()
    fill_color = (0, 180, 200)  # warm-teal-ish fill
    cv2.rectangle(overlay, (bx0, by0), (bx1, by1), fill_color, -1)
    alpha = 0.18
    cv2.addWeighted(overlay, alpha, annotated, 1 - alpha, 0, annotated)

    # Outline the box with a thicker border
    border_color = (0, 204, 255)  # bright yellow-orange
    cv2.rectangle(annotated, (bx0, by0), (bx1, by1), border_color, 4)

    # Helper to draw text with shadow for legibility
    def _put_text(img, text, pos, scale=0.9, color=(255, 255, 255), thickness=2):
        x, y = pos
        cv2.putText(img, text, (x + 2, y + 2), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness + 1, cv2.LINE_AA)
        cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)

    # Title inside the box
    title = "Staging Area"
    _put_text(annotated, title, (bx0 + 12, by0 + 34), scale=0.9)

    # Zone and frame at top-left
    _put_text(annotated, f"{zone} | frame {frame_idx}", (18, 32), scale=0.8)

    # Optional small caption bottom-left
    caption = "OnePlate - generated hotspot preview"
    _put_text(annotated, caption, (18, h - 18), scale=0.6)

    cv2.imwrite(str(thumb_path), annotated)
    return f"{thumbnail_root.name}/{thumb_name}"


def quick_realtime_hotspots(
    video_path: str,
    max_frames: int = 120,
    step: int = 10,
    *,
    weights: str = "yolov8n.pt",
    thumbnail_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    try:
        import cv2
        from ultralytics import YOLO
    except Exception:
        return []

    video_file = Path(video_path)
    if not video_file.exists():
        return []

    cap = cv2.VideoCapture(str(video_file))
    if not cap.isOpened():
        return []

    try:
        model = YOLO(weights)
    except Exception:
        cap.release()
        return []

    frame_idx = 0
    zone_hits = {
        "Zone A": {"hits": 0, "frames": 0, "best_confidence": 0.0, "thumbnail_path": None},
        "Zone B": {"hits": 0, "frames": 0, "best_confidence": 0.0, "thumbnail_path": None},
        "Zone C": {"hits": 0, "frames": 0, "best_confidence": 0.0, "thumbnail_path": None},
    }
    thumbnail_root = Path(thumbnail_dir) if thumbnail_dir else None

    while frame_idx < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        frame_idx += 1
        if frame_idx % step != 0:
            continue

        h, w = frame.shape[:2]
        a = w // 3
        b = 2 * w // 3

        try:
            results = model.predict(frame, verbose=False, classes=[0])
        except Exception:
            results = []

        boxes = results[0].boxes if results else []
        for z in zone_hits:
            zone_hits[z]["frames"] += 1

        for box in boxes:
            cls_id = int(box.cls[0])
            if cls_id != 0:
                continue
            confidence = float(box.conf[0]) if getattr(box, "conf", None) is not None else 0.0
            x1, _, x2, _ = box.xyxy[0].tolist()
            cx = int((x1 + x2) // 2)
            zone = "Zone A" if cx < a else ("Zone B" if cx < b else "Zone C")
            zone_info = zone_hits[zone]
            zone_info["hits"] += 1
            if confidence >= zone_info["best_confidence"]:
                zone_info["best_confidence"] = confidence
                if thumbnail_root is not None:
                    zone_info["thumbnail_path"] = _write_zone_thumbnail(frame, thumbnail_root, str(video_file), zone, frame_idx)

    cap.release()

    zone_stats: dict[str, dict[str, int]] = {}
    for zone, info in zone_hits.items():
        people_count = max(0, int(round(info["hits"] / max(1, info["frames"]))))
        persistence = min(60, info["hits"])
        zone_stats[zone] = {
            "people_count": people_count,
            "persistence_minutes": persistence,
            "detection_hits": int(info["hits"]),
            "frames_observed": int(info["frames"]),
            "best_confidence": round(float(info["best_confidence"]), 3),
            "thumbnail_path": info["thumbnail_path"],
            "source": "realtime-yolo",
        }

    return build_hotspots_from_zone_stats(zone_stats)
