## Context Map

### Files to Modify
| File | Purpose | Changes Needed |
|------|---------|----------------|
| preplan.md | Product scope and architecture notes | Already refined; no further changes needed for MVP code |

### Files to Create
| File | Purpose |
|------|---------|
| app/streamlit_app.py | Main dashboard and role-based workflow |
| app/data_store.py | In-memory data layer + business actions |
| app/logic.py | Expiry, safety, need scoring, matching helpers |
| app/otp.py | OTP generation and verification |
| app/vision.py | YOLO hotspot loader (fallback + optional realtime) |
| scripts/run_yolo.py | Optional standalone hotspot generation script |
| data/hotspots.json | Fallback hotspot data for guaranteed demo |
| data/sample_food.json | Seed food listing data |
| data/sample_requests.json | Seed request data |
| supabase/schema.sql | Supabase-ready schema for later integration |
| requirements.txt | Python dependencies |
| README.md | Run guide, architecture, and demo steps |

### Dependencies
| Dependency | Relationship |
|------------|--------------|
| streamlit | Dashboard UI |
| numpy | Numeric helper for optional calculations |
| opencv-python | Video frame handling for optional YOLO processing |
| ultralytics | YOLOv8 inference for optional realtime hotspots |

### Test Files
| Test | Coverage |
|------|----------|
| (none yet) | Use in-app smoke path for hackathon MVP |

### Reference Patterns
| File | Pattern |
|------|---------|
| docs/sprint-1/plan.md | Sprint scope and acceptance criteria |

### Risk Assessment
- [ ] Breaking changes to public API
- [x] Database migrations needed (included in supabase/schema.sql)
- [x] Configuration changes required (environment variables optional)
