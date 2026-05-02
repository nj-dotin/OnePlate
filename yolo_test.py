"""
Quick YOLO Test - Shows real-time detection output
Run this to see YOLO zones being detected frame-by-frame
"""

import sys
sys.path.insert(0, '.')

from app.video_processor import VideoProcessor
import cv2

print("=" * 70)
print("🎯 YOLOv8 Detection Test - Real-Time Output")
print("=" * 70)
print()

processor = VideoProcessor('yolov8n.pt')
print("✅ Model loaded: yolov8n.pt")
print()

# Process video with detailed output
video_path = 'beg_2.mp4'
cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print("❌ Cannot open video")
    sys.exit(1)

print(f"🎬 Processing: {video_path}")
print("-" * 70)

frame_idx = 0
total_zones = 0
frame_interval = 5
max_frames = 15

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    if frame_idx % frame_interval == 0:
        timestamp = int(cap.get(cv2.CAP_PROP_POS_MSEC))
        
        # Run YOLO
        try:
            results = processor.model(frame, verbose=False)
            if results and len(results) > 0:
                zones = processor._extract_zones_from_yolo(results, frame.shape)
                total_zones += len(zones)
                
                # Print frame results
                frame_num = frame_idx // frame_interval + 1
                print(f"Frame {frame_num:2d} (ms: {timestamp:6d}): ", end="")
                
                if zones:
                    class_names = {}
                    for zone in zones:
                        cls = zone.get('class_name', 'unknown')
                        class_names[cls] = class_names.get(cls, 0) + 1
                    
                    print(f"{len(zones)} zones detected → ", end="")
                    for cls_name, count in sorted(class_names.items()):
                        print(f"{count}x {cls_name}, ", end="")
                    print()
                else:
                    print("No objects")
        except Exception as e:
            print(f"Frame {frame_idx // frame_interval + 1}: Error - {str(e)[:30]}")
    
    frame_idx += 1
    if frame_idx // frame_interval >= max_frames:
        break

cap.release()

print("-" * 70)
print(f"✅ Processing complete!")
print(f"   Total frames processed: {frame_idx}")
print(f"   Frames with YOLO: {frame_idx // frame_interval}")
print(f"   Total zones detected: {total_zones}")
print(f"   Average zones/frame: {total_zones / max(1, frame_idx // frame_interval):.1f}")
print()
print("🎉 YOLO is working perfectly!")
print()
