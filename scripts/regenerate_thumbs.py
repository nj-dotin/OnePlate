from app.vision import quick_realtime_hotspots, save_hotspots_to_json
from pathlib import Path

video = Path('WhatsApp Video 2026-05-02 at 12.01.28 AM.mp4')
print('Video exists:', video.exists())
hotspots = quick_realtime_hotspots(str(video), max_frames=800, step=3, thumbnail_dir=Path('data/hotspot_thumbnails'))
print('Generated', len(hotspots), 'hotspots')
if hotspots:
    save_hotspots_to_json('data/hotspots.generated.json', hotspots, metadata={'source':'realtime-yolo-regenerate'})
    print('Saved data/hotspots.generated.json')
