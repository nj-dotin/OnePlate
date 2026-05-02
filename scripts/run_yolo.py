from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vision import load_hotspots_from_json, quick_realtime_hotspots, save_hotspots_to_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Run quick YOLO hotspot extraction")
    parser.add_argument("--video", required=True, help="Path to input video")
    parser.add_argument("--out", default="data/hotspots.generated.json", help="Output JSON file")
    parser.add_argument("--fallback", default="data/hotspots.json", help="Fallback hotspot JSON if realtime inference fails")
    parser.add_argument("--weights", default="yolov8n.pt", help="Ultralytics weights to use")
    parser.add_argument("--thumbnail-dir", default="data/hotspot_thumbnails", help="Directory for generated thumbnails")
    parser.add_argument("--max-frames", type=int, default=120)
    parser.add_argument("--step", type=int, default=10)
    args = parser.parse_args()

    out_path = Path(args.out)
    thumbnail_dir = Path(args.thumbnail_dir)
    rows = quick_realtime_hotspots(
        args.video,
        max_frames=args.max_frames,
        step=args.step,
        weights=args.weights,
        thumbnail_dir=thumbnail_dir,
    )

    metadata = {
        "video_path": str(Path(args.video)),
        "weights": args.weights,
        "max_frames": args.max_frames,
        "step": args.step,
        "source": "realtime-yolo",
        "fallback_used": False,
    }

    if not rows:
        fallback_rows = load_hotspots_from_json(args.fallback)
        if fallback_rows:
            rows = fallback_rows
            metadata["source"] = "fallback-json"
            metadata["fallback_used"] = True
        else:
            metadata["source"] = "empty"

    if rows:
        save_hotspots_to_json(out_path, rows, metadata=metadata)
        print(f"Saved {len(rows)} hotspots to {out_path} ({metadata['source']})")
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({**metadata, "hotspots": []}, indent=2), encoding="utf-8")
        print(f"No hotspots produced; wrote empty result to {out_path}")


if __name__ == "__main__":
    main()
