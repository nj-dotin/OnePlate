# PHRS Hackathon MVP

Proactive Hunger Response System (PHRS) combines:

- Restaurant surplus uploads with expiry/safety estimation
- YOLO-inspired demand hotspot detection (fallback JSON + optional realtime)
- Direct user food requests
- Smart matching (need, urgency, quantity, distance)
- OTP-verified pickup and delivery
- Impact credits ledger for restaurant, NGO, and sponsor visibility

## Stack

- Python
- Streamlit
- Ultralytics YOLOv8 (optional realtime mode)
- OpenCV (optional realtime mode)
- In-memory data layer (always works)
- Supabase schema file for later integration

## Project Structure

- `app/streamlit_app.py` main dashboard
- `app/data_store.py` in-memory state and workflows
- `app/logic.py` scoring and matching helpers
- `app/otp.py` OTP generation and verification
- `app/vision.py` hotspot loader + optional YOLO processing
- `scripts/run_yolo.py` optional CLI script to generate hotspot JSON
- `data/*.json` seed listings, requests, hotspot fallback
- `supabase/schema.sql` Supabase-ready schema
- `preplan.md` final project plan

## Install

You already started installing dependencies. If needed later, run:

```powershell
pip install -r requirements.txt
```

## Run

```powershell
python -m streamlit run app/streamlit_app.py --server.port 8501
```

Or:

```powershell
./run_demo.ps1
```

## Demo Flow (Recommended)

1. Open `Demand Hotspots` and click `Load Hotspots` in fallback mode.
2. In `Restaurant`, add one new listing.
3. In `Requests`, add one user request.
4. In `Matching + Dispatch`, create a dispatch job from a top suggestion.
5. Copy OTPs shown in UI.
6. In `OTP Verify`, verify pickup and delivery.
7. In `Company Dashboard`, show updated impact ledger/credits.

## Optional Realtime YOLO

If your environment supports YOLO runtime and you have a sample video:

```powershell
python scripts/run_yolo.py --video video/sample.mp4 --out data/hotspots.generated.json
```

Then in the UI you can use `Realtime YOLO` mode.

## Important Pitch Notes

- Do not claim direct tax deduction implementation in MVP.
- Position credits as measurable impact units for CSR/ESG reporting.
- Do not label individuals from vision; use area-level unmet-need hotspot language.
