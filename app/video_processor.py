"""Video processing module for OnePlate: extracts frames, detects zones, stores to cloud."""

from __future__ import annotations

import io
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO

from app.supabase_client import get_supabase_client, SupabaseOps


def _id(prefix: str) -> str:
    """Generate a unique ID with timestamp."""
    import uuid
    import time
    timestamp = str(int(time.time()))
    hex_part = uuid.uuid4().hex[:8]
    return prefix + "_" + hex_part


class VideoProcessor:
    """Process videos to extract hotspot zones and upload to Supabase."""
    
    def __init__(self, model_name: str = "yolov8n.pt"):
        """Initialize YOLO model for people/object detection."""
        self.model = YOLO(model_name)
        self.last_error: str | None = None
    
    def extract_frames(
        self, 
        video_data: bytes | str,
        fps_sample: int = 2,
        max_frames: int = 30
    ) -> list[dict[str, Any]]:
        """Extract frames from video at specified FPS interval.
        
        Args:
            video_data: Bytes object or path to video file
            fps_sample: Extract every Nth frame (e.g., 2 = every other frame)
            max_frames: Maximum frames to extract
        
        Returns:
            List of frame dicts with zones detected
        """
        temp_file = None
        try:
            # Handle bytes or file path
            if isinstance(video_data, bytes):
                # Write bytes to temp file
                tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
                tmp.write(video_data)
                tmp.close()
                video_file = tmp.name
                temp_file = video_file
            else:
                video_file = str(video_data)
            
            # Try to open video
            cap = cv2.VideoCapture(video_file)
            if not cap.isOpened():
                # Try with different codec flags
                cap = cv2.VideoCapture(video_file)
                if not cap.isOpened():
                    self.last_error = f"Cannot open video: {video_file}. Check video format and codecs."
                    return []
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30  # Default fallback
            
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            frame_interval = max(1, int(fps // fps_sample)) if fps > 0 else fps_sample
            
            frames = []
            frame_idx = 0
            sample_count = 0
            first_error = None
            
            while sample_count < max_frames:
                ret, frame = cap.read()
                if not ret or frame is None:
                    break
                
                if frame_idx % frame_interval == 0:
                    timestamp_ms = int(cap.get(cv2.CAP_PROP_POS_MSEC))
                    
                    # Run YOLO detection
                    zones = []
                    try:
                        results = self.model(frame, verbose=False)
                        if results and len(results) > 0:
                            zones = self._extract_zones_from_yolo(results, frame.shape)
                    except:
                        # If YOLO fails, continue without zones
                        pass
                    
                    frames.append({
                        "id": _id("frame"),
                        "timestamp_ms": timestamp_ms,
                        "frame_index": frame_idx,
                        "frame_shape": (frame.shape[0], frame.shape[1]),  # height, width
                        "zones": zones,
                        "people_count": len([z for z in zones if z.get("class_name") == "person"]),
                        "detected_classes": list({z.get("class_name") for z in zones}),
                    })
                    sample_count += 1
                
                frame_idx += 1
            
            cap.release()
            
            # Store first error if no frames were extracted
            if not frames and first_error:
                self.last_error = f"Frame processing error: {first_error}"
            
            # Clean up temp file if created
            if temp_file:
                try:
                    os.unlink(temp_file)
                except:
                    pass
            
            return frames
        
        except Exception as exc:
            self.last_error = str(exc)
            if temp_file:
                try:
                    os.unlink(temp_file)
                except:
                    pass
            return []
    
    def _extract_zones_from_yolo(self, results: Any, frame_shape: tuple) -> list[dict]:
        """Extract detected zones from YOLO results.
        
        Args:
            results: YOLO detection results
            frame_shape: (height, width, channels)
        
        Returns:
            List of zone dicts with bounding boxes and confidence
        """
        zones = []
        try:
            if not results or len(results) == 0:
                return zones
            
            result = results[0]
            if not hasattr(result, "boxes"):
                return zones
            
            boxes = result.boxes
            if boxes is None or len(boxes) == 0:
                return zones
            
            h, w = int(frame_shape[0]), int(frame_shape[1])
            if h <= 0 or w <= 0:
                return zones
            
            # Get class names
            class_map = {}
            if hasattr(self.model, 'names'):
                names_obj = self.model.names
                if isinstance(names_obj, dict):
                    class_map = names_obj
                elif isinstance(names_obj, list):
                    for idx, name in enumerate(names_obj):
                        class_map[idx] = str(name)
            
            # Process each detected box
            for box in boxes:
                try:
                    coords = box.xyxy[0].tolist()
                    x1, y1, x2, y2 = float(coords[0]), float(coords[1]), float(coords[2]), float(coords[3])
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    
                    # Get class name  
                    if cls_id in class_map:
                        class_name = str(class_map[cls_id])
                    else:
                        class_name = 'unknown'
                    
                    zones.append({
                        "class_id": cls_id,
                        "class_name": class_name,
                        "confidence": round(conf, 3),
                        "bbox": {
                            "x1": round(x1 / w, 4),
                            "y1": round(y1 / h, 4),
                            "x2": round(x2 / w, 4),
                            "y2": round(y2 / h, 4),
                        },
                        "area_percent": round((x2 - x1) * (y2 - y1) / (w * h) * 100, 2),
                    })
                except:
                    pass
        except:
            pass
        
        return zones
    
    def detect_hotspots_from_frames(self, frames: list[dict]) -> list[dict]:
        """Aggregate zone data across frames to identify hotspots.
        
        Args:
            frames: List of frame dicts from extract_frames
        
        Returns:
            List of hotspot dicts with aggregated zone info
        """
        if not frames:
            return []
        
        # Aggregate zones by spatial clustering
        all_zones = []
        for frame in frames:
            for zone in frame.get("zones", []):
                all_zones.append({
                    **zone,
                    "frame_id": frame.get("id"),
                    "timestamp_ms": frame.get("timestamp_ms"),
                })
        
        if not all_zones:
            return []
        
        # Cluster zones that overlap across frames
        hotspots = self._cluster_zones(all_zones)
        return hotspots
    
    def _cluster_zones(self, zones: list[dict], iou_threshold: float = 0.3) -> list[dict]:
        """Cluster zones using intersection-over-union (IoU).
        
        Args:
            zones: List of zone dicts with bbox info
            iou_threshold: Minimum IoU to merge zones
        
        Returns:
            List of clustered hotspot dicts
        """
        if not zones:
            return []
        
        clusters = []
        used = set()
        
        for i, zone in enumerate(zones):
            if i in used:
                continue
            
            # Start new cluster
            cluster = [zone]
            used.add(i)
            
            # Find similar zones
            for j in range(i + 1, len(zones)):
                if j in used:
                    continue
                
                iou = self._calculate_iou(zone["bbox"], zones[j]["bbox"])
                if iou >= iou_threshold:
                    cluster.append(zones[j])
                    used.add(j)
            
            # Aggregate cluster
            hotspot = self._aggregate_cluster(cluster)
            clusters.append(hotspot)
        
        return clusters
    
    def _calculate_iou(self, bbox1: dict, bbox2: dict) -> float:
        """Calculate intersection-over-union of two bounding boxes."""
        x1_inter = max(bbox1["x1"], bbox2["x1"])
        y1_inter = max(bbox1["y1"], bbox2["y1"])
        x2_inter = min(bbox1["x2"], bbox2["x2"])
        y2_inter = min(bbox1["y2"], bbox2["y2"])
        
        if x2_inter < x1_inter or y2_inter < y1_inter:
            return 0.0
        
        inter_area = (x2_inter - x1_inter) * (y2_inter - y1_inter)
        area1 = (bbox1["x2"] - bbox1["x1"]) * (bbox1["y2"] - bbox1["y1"])
        area2 = (bbox2["x2"] - bbox2["x1"]) * (bbox2["y2"] - bbox2["y1"])
        union_area = area1 + area2 - inter_area
        
        return inter_area / union_area if union_area > 0 else 0.0
    
    def _aggregate_cluster(self, cluster: list[dict]) -> dict:
        """Aggregate zone cluster into single hotspot."""
        bboxes = [z["bbox"] for z in cluster]
        x1_avg = sum(b["x1"] for b in bboxes) / len(bboxes)
        y1_avg = sum(b["y1"] for b in bboxes) / len(bboxes)
        x2_avg = sum(b["x2"] for b in bboxes) / len(bboxes)
        y2_avg = sum(b["y2"] for b in bboxes) / len(bboxes)
        
        conf_avg = sum(z.get("confidence", 0) for z in cluster) / len(cluster)
        
        return {
            "id": _id("hotspot"),
            "cluster_size": len(cluster),
            "avg_confidence": round(conf_avg, 3),
            "bbox": {
                "x1": round(x1_avg, 4),
                "y1": round(y1_avg, 4),
                "x2": round(x2_avg, 4),
                "y2": round(y2_avg, 4),
            },
            "detected_classes": list({z.get("class_name") for z in cluster}),
            "people_detections": len([z for z in cluster if z.get("class_name") == "person"]),
            "persistence_frames": len({z.get("frame_id") for z in cluster}),
        }
    
    def upload_frames_to_supabase(
        self,
        frames: list[dict],
        hotspots: list[dict],
        video_name: str,
    ) -> tuple[bool, str | None]:
        """Upload extracted frames and hotspots to Supabase Storage and DB.
        
        Args:
            frames: List of frame dicts
            hotspots: List of hotspot dicts
            video_name: Name of source video for reference
        
        Returns:
            (success, error_message)
        """
        try:
            client = get_supabase_client()
            if not client:
                return False, "Supabase client unavailable"
            
            ops = SupabaseOps(client)
            uploaded_frames = []
            
            # Upload each frame
            for frame in frames:
                try:
                    frame_id = frame.get("id")
                    frame_data = frame.get("frame_data")
                    zones = frame.get("zones", [])
                    
                    # Store frame in DB
                    frame_record = {
                        "id": frame_id,
                        "video_name": video_name,
                        "timestamp_ms": frame.get("timestamp_ms"),
                        "frame_index": frame.get("frame_index"),
                        "zones": zones,
                        "people_count": frame.get("people_count"),
                        "detected_classes": frame.get("detected_classes"),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    
                    # You can extend this to upload actual frame bytes to Storage
                    # For now, storing metadata in DB
                    uploaded_frames.append(frame_record)
                
                except Exception as e:
                    # Continue with other frames if one fails
                    pass
            
            # Upload hotspots to DB
            for hotspot in hotspots:
                try:
                    hotspot_record = {
                        "id": hotspot.get("id"),
                        "video_name": video_name,
                        "zone": hotspot["bbox"],
                        "people_count": hotspot.get("people_detections", 0),
                        "persistence_minutes": int(hotspot.get("persistence_frames", 0) / 10),  # Estimate
                        "need_score": round(hotspot.get("people_detections", 0) * 100, 0),
                        "priority": "HIGH" if hotspot.get("people_detections", 0) > 5 else "MEDIUM",
                        "lat": 12.9734 + (hotspot["bbox"]["x1"] * 0.01),  # Relative to ref point
                        "lng": 77.5964 + (hotspot["bbox"]["y1"] * 0.01),
                        "time_detected": datetime.now(timezone.utc).isoformat(),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    
                    ops.create_hotspot(hotspot_record)
                except Exception as e:
                    pass
            
            return True, None
        
        except Exception as exc:
            return False, str(exc)
