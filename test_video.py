import sys
sys.path.insert(0, '.')

from app.video_processor import VideoProcessor

# Process the uploaded video
video_path = 'beg_2.mp4'
processor = VideoProcessor('yolov8n.pt')

print('🎬 Processing video: ' + video_path)
print('=' * 60)
sys.stdout.flush()

# Extract frames with YOLO
print('[DEBUG] Starting extract_frames...')
sys.stdout.flush()
frames = processor.extract_frames(video_path, fps_sample=5, max_frames=50)
print('[DEBUG] Frames extracted: ' + str(len(frames)))
sys.stdout.flush()

print('✅ Extracted ' + str(len(frames)) + ' frames')
print('=' * 60)
sys.stdout.flush()

# Process and aggregate hotspots
if frames:
    print('[DEBUG] Starting detect_hotspots_from_frames...')
    sys.stdout.flush()
    hotspots = processor.detect_hotspots_from_frames(frames)
    print('[DEBUG] Hotspots detected: ' + str(len(hotspots)))
    sys.stdout.flush()
    print('🔥 Detected ' + str(len(hotspots)) + ' hotspots from YOLO')
    print('=' * 60)
    sys.stdout.flush()
    
    for i, hotspot in enumerate(hotspots, 1):
        print('Hotspot ' + str(i) + ':')
        print('  Cluster Size: ' + str(hotspot.get('cluster_size')))
        print('  Classes: ' + str(hotspot.get('detected_classes')))
        print('  People Detections: ' + str(hotspot.get('people_detections')))
        sys.stdout.flush()
    
    # Upload to Supabase (this converts internal format to Supabase schema)
    print('[DEBUG] Starting upload_frames_to_supabase...')
    sys.stdout.flush()
    success, error = processor.upload_frames_to_supabase(frames, hotspots, 'beg_2.mp4')
    print('[DEBUG] Upload result: ' + str(success) + ', error: ' + str(error))
    sys.stdout.flush()
    
    if success:
        print('✅ Successfully uploaded ' + str(len(hotspots)) + ' hotspots to Supabase!')
    else:
        print('❌ Upload error: ' + str(error))
    
    print('=' * 60)
    print('🎉 Video processing complete!')
    sys.stdout.flush()
else:
    print('❌ No frames extracted!')
