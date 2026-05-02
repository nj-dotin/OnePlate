import sys
sys.path.insert(0, '.')

import cv2
import numpy as np
from ultralytics import YOLO

# Create test video
output_file = 'data/test_video_debug.mp4'
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(output_file, fourcc, 20.0, (640, 480))

for i in range(10):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.circle(frame, (100, 100), 30, (0, 255, 0), -1)
    out.write(frame)

out.release()

# Manual extraction with debugging
cap = cv2.VideoCapture(output_file)
print('Video opened:', cap.isOpened())

fps = cap.get(cv2.CAP_PROP_FPS)
frame_interval = 1
frame_idx = 0
sample_count = 0

model = YOLO('yolov8n.pt')

while sample_count < 3:
    ret, frame = cap.read()
    if not ret:
        print('Frame read failed')
        break
    
    if frame_idx % frame_interval == 0:
        print(f'Processing frame {frame_idx}')
        print(f'  Frame shape: {frame.shape}, dtype: {frame.dtype}')
        
        try:
            print('  Running YOLO...')
            results = model(frame, verbose=False)
            print(f'  YOLO done, boxes: {len(results[0].boxes)}')
            sample_count += 1
        except Exception as e:
            print(f'  Error: {str(e)}')
            import traceback
            traceback.print_exc()
            break
    
    frame_idx += 1

cap.release()
print('Done')
