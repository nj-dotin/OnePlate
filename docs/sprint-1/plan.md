# PHRS — Sprint 1 (10-hour hackathon MVP)

Overview
- Goal: Build a runnable 10-hour MVP for PHRS (Proactive Hunger Response System) that demonstrates surplus listing discovery, zone-level YOLO hotspot detection, request→match flow, OTP verify, and a Streamlit demo UI. Prefer a Supabase-ready schema but use an in-memory fallback to guarantee demoability.

Timebox
- Total: 10 hours (hackathon)

**Backlog (Priorities)**
- **P0:** Minimum viable features to demo a full end-to-end flow
  - **Streamlit dashboard**: list listings, create request form, admin view for matches.
  - **Surplus listing model**: store listings with `safety_score` and `expiry_score` (simple rule-based calculation).
  - **YOLO hotspot detection**: process provided sample video and output zone-level hotspots (bounding boxes → zone hits). Provide a small pre-baked results file in case realtime inference stalls.
  - **Matching engine**: match user requests to nearby active listings using simple heuristics (distance + scores + availability).
  - **OTP verification**: simple SMS/email OTP stub (log OTP to console) with a toggle to enable a provider later.
  - **In-memory data layer**: fully functional fallback API so demo runs without external infra.

- **P1:** Important niceties if time allows
  - **Supabase-ready schema and migration SQL** (no live deployment required).
  - **Impact credits ledger**: track credits awarded per match (no tax/legal claims UI, just numeric ledger).
  - **Retryable video processing**: small wrapper to re-run YOLO on subsets of frames.
  - **Polish UI/UX**: basic styles, icons, and success/failure states.

**Team split (4 people) — exact task allocation**
- **Person 1 — Frontend / Streamlit Lead (2.5h P0, 1h P1)**
  - Build the Streamlit app shell and pages: Listings, Create Request, Matches, Admin.
  - Hook to the in-memory API endpoints and render `safety_score` / `expiry_score` and match results.
  - Deliver demo storybook screens and a short usage script.

- **Person 2 — Backend / Matching Lead (3h P0, 1h P1)**
  - Implement in-memory data layer and REST endpoints: list/create listings, create requests, run matching engine.
  - Implement rule-based `safety_score` and `expiry_score` functions; expose them on listings create/update.
  - Write Supabase-ready schema SQL file (P1) and migration notes.

- **Person 3 — ML / Vision Lead (3h P0, 1h P1)**
  - Run YOLO on the sample video; output zone-level hotspot JSON (zone id → hit count, timestamps, sample frame thumbnails).
  - Provide a pre-baked JSON/asset fallback and a small wrapper script to toggle realtime vs baked results.
  - Produce a short README on how to re-run inference locally.

- **Person 4 — QA / Integration & DevOps Lead (1.5h P0, 1h P1)**
  - Wire OTP stub, integration tests for the matching flow (smoke tests), and run end-to-end checks.
  - Prepare impact credits ledger display and ensure no tax/legal language is present.
  - Coordinate merging and final demo packaging (one-command run instructions).

Notes on splitting
- Ownership is explicit: each person has a clear P0 deliverable and a P1 stretch goal.
- Cross-check times assume concurrent work; keep communication tight (every 90 minutes sync).

**Acceptance criteria checklist**
- **E2E demoable:** Deploy and run locally with one command and the Streamlit UI shows a full request→match flow.
- **Listings created:** Create at least 3 sample restaurant listings with populated `safety_score` and `expiry_score`.
- **YOLO results:** Zone-level hotspot JSON is available and displayed as an overlay or stats in the UI (or fallback JSON is used when realtime inference disabled).
- **Matching works:** A created user request results in at least one valid match (according to heuristics) and presents contact/fulfillment steps.
- **OTP flow:** OTP is generated and verifiable (console/logging stub acceptable) and gates the confirm action in demo.
- **Impact credits:** Matches increment a visible credits counter (ledger entries saved to in-memory store).
- **No external infra required:** The app runs end-to-end with the in-memory fallback; Supabase artifacts are optional and not required to run demo.
- **Basic tests:** A short checklist of smoke tests (create listing, create request, run match, verify OTP) completes green locally.

**Demo script (bullets)**
- Launch: run the packaged start command and open the Streamlit URL.
- Show `Listings` page: highlight `safety_score` and `expiry_score` on 3 sample entries.
- Toggle Vision: show YOLO zone-hotspot overlay or summary stats; demonstrate fallback JSON if realtime disabled.
- Create Request: fill the request form, request OTP, show OTP from console and confirm.
- Matching: show match results, accept a match, and observe credits ledger increment.
- Admin view: show raw data (listings, requests, hotspot JSON) and Supabase-ready SQL file available for export.

**Risks & mitigations**
- **Risk:** YOLO inference is slow or fails on hackathon machines.
  - **Mitigation:** Pre-bake hotspot JSON and thumbnails; show fallback and note how to re-run offline inference.
- **Risk:** SMS/email OTP provider integration unavailable.
  - **Mitigation:** Use a console-logged OTP stub and an admin switch to enable a provider later.
- **Risk:** Time runs out before end-to-end wiring.
  - **Mitigation:** Prioritize a runnable in-memory flow that demonstrates all end-to-end steps; defer Supabase and polishing to P1.
- **Risk:** Mismatched expectations between team members.
  - **Mitigation:** 90-minute syncs, short acceptance checklist, and one person responsible for final integration (Person 4).

Deliverables & run instructions
- **Files:** `docs/sprint-1/plan.md`, `supabase/schema.sql` (P1), `app/run_demo.sh` or `run_demo.ps1` (start wrapper), `vision/hotspots.json` (fallback).
- **Run locally:** provide a single command (example):
```
python -m streamlit run app/streamlit_app.py --server.port 8501
```

Minimal assumptions
- Python 3.10+, Streamlit, basic ML runtime for YOLO (Pytorch/Ultralytics) optionally required for realtime; fallback JSON guarantees demoability.

Next steps
- Create repo skeleton files, sample data, and a one-line start script; run a first smoke test within hour 1.
