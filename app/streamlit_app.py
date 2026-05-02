from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import sys
import streamlit as st
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load environment variables from .env file
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.data_store import PHRSStore
from app.logic import need_score, priority_from_need
from app.vision import load_hotspots_from_json, quick_realtime_hotspots, save_hotspots_to_json
from app.supabase_client import get_supabase_client, SupabaseOps
from app.route_optimization import greedy_assignment, build_route_summary
import folium
from streamlit_folium import st_folium


ROOT = Path(__file__).resolve().parents[1]
FALLBACK_HOTSPOTS = ROOT / "data" / "hotspots.json"
GENERATED_HOTSPOTS = ROOT / "data" / "hotspots.generated.json"
HOTSPOT_THUMBNAILS = ROOT / "data" / "hotspot_thumbnails"
APP_NAME = "OnePlate"
APP_TAGLINE = "AI-assisted surplus food routing with verified dispatch"
CLOUD_WRITE_REQUIRED = os.getenv("CLOUD_WRITE_REQUIRED", "true").lower() in {"1", "true", "yes"}


def _preferred_hotspot_path() -> Path:
    if GENERATED_HOTSPOTS.exists():
        return GENERATED_HOTSPOTS
    return FALLBACK_HOTSPOTS


def _thumbnail_to_path(thumbnail_value: str | None) -> Path | None:
    if not thumbnail_value:
        return None
    thumbnail_path = Path(thumbnail_value)
    if thumbnail_path.is_absolute():
        return thumbnail_path
    return ROOT / "data" / thumbnail_path


def get_store() -> PHRSStore:
    if "phrs_store" not in st.session_state:
        st.session_state.phrs_store = PHRSStore.from_seed(ROOT)
        
        # Try to load from Supabase if available
        supabase = get_supabase_client()
        if supabase:
            ops = SupabaseOps(supabase)
            try:
                # Seed baseline reference data into Supabase once so every device sees the same fake/demo setup.
                if not ops.list_restaurants():
                    for row in st.session_state.phrs_store.restaurants:
                        ops.create_restaurant(row)
                if not ops.list_ngos():
                    for row in st.session_state.phrs_store.ngos:
                        ops.create_ngo(row)
                if not ops.list_companies():
                    for row in st.session_state.phrs_store.companies:
                        ops.create_company(row)

                # Load restaurants
                restaurants = ops.list_restaurants()
                if restaurants:
                    st.session_state.phrs_store.restaurants = restaurants
                
                # Load NGOs
                ngos = ops.list_ngos()
                if ngos:
                    st.session_state.phrs_store.ngos = ngos
                
                # Load companies
                companies = ops.list_companies()
                if companies:
                    st.session_state.phrs_store.companies = companies
                
                # Load food listings
                food_listings = ops.list_food_listings()
                if food_listings:
                    st.session_state.phrs_store.food_listings = food_listings
                
                # Load user requests
                user_requests = ops.list_user_requests()
                if user_requests:
                    st.session_state.phrs_store.user_requests = user_requests
                
                # Load hotspots
                hotspots = ops.list_hotspots()
                if hotspots:
                    st.session_state.phrs_store.hotspots = hotspots
                
                # Load impact ledger
                impact_ledger = ops.list_impact_ledger()
                if impact_ledger:
                    st.session_state.phrs_store.impact_ledger = impact_ledger

                # Load notifications
                notifications = ops.list_notifications()
                if notifications:
                    st.session_state.phrs_store.notifications = notifications
                
                st.session_state.supabase_ops = ops
                st.session_state.use_supabase = True
            except Exception as e:
                st.warning(f"Could not load from Supabase: {e}. Using local data.")
                st.session_state.use_supabase = False
        else:
            st.session_state.use_supabase = False
        
        # Load local hotspots
        hotspots = load_hotspots_from_json(_preferred_hotspot_path())
        if hotspots:
            st.session_state.phrs_store.set_hotspots(hotspots)
            st.session_state.hotspot_source = str(_preferred_hotspot_path())
    
    return st.session_state.phrs_store


def get_supabase_ops() -> SupabaseOps | None:
    """Get Supabase ops if initialized."""
    return st.session_state.get("supabase_ops")


def _normalize_cloud_payload(action: str, data: dict) -> dict:
    payload = dict(data)
    if action in {"dispatch_job", "update_dispatch"}:
        suggestion = payload.get("suggestion", {}) if isinstance(payload.get("suggestion"), dict) else {}
        payload = {
            "id": payload.get("id"),
            "food_id": suggestion.get("food_id"),
            "assigned_ngo_id": payload.get("ngo_id") or payload.get("assigned_ngo_id"),
            "ngo_name": payload.get("ngo_name"),
            "target_kind": suggestion.get("target_kind"),
            "target_id": suggestion.get("target_id"),
            "quantity": suggestion.get("suggested_qty", 0),
            "suggestion": suggestion,
            "pickup_otp": payload.get("pickup_otp"),
            "delivery_otp": payload.get("delivery_otp"),
            "pickup_verified": payload.get("pickup_verified", False),
            "delivery_verified": payload.get("delivery_verified", False),
            "status": payload.get("status", "created"),
            "created_at": payload.get("created_at"),
        }
    return payload


def sync_to_supabase(action: str, data: dict) -> bool:
    """Sync an action to Supabase if available."""
    ops = get_supabase_ops()
    if not ops:
        return False
    cloud_data = _normalize_cloud_payload(action, data)
    try:
        result = None
        if action == "food_listing":
            result = ops.create_food_listing(cloud_data)
        elif action == "user_request":
            result = ops.create_user_request(cloud_data)
        elif action == "dispatch_job":
            result = ops.create_dispatch_job(cloud_data)
        elif action == "impact_entry":
            result = ops.create_impact_entry(cloud_data)
        elif action == "notification":
            result = ops.create_notification(cloud_data)
        elif action == "update_food":
            result = ops.update_food_listing(cloud_data["id"], cloud_data)
        elif action == "update_request":
            result = ops.update_user_request(cloud_data["id"], cloud_data)
        elif action == "update_dispatch":
            result = ops.update_dispatch_job(cloud_data["id"], cloud_data)
        elif action == "update_notification":
            result = ops.update_notification(cloud_data["id"], cloud_data)
        if result is None:
            st.warning(f"Supabase sync skipped or failed for: {action}")
            return False
        return True
    except Exception as e:
        st.warning(f"Supabase sync failed: {e}")
        return False


def sync_new_notifications(before_count: int, store: PHRSStore) -> None:
    new_notifications = store.notifications[before_count:]
    for notification in new_notifications:
        sync_to_supabase("notification", notification)


def as_table(rows: list[dict]) -> list[dict]:
    return rows if rows else []


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap');

        :root {
            --op-bg: #f6f1e8;
            --op-surface: rgba(255, 255, 255, 0.78);
            --op-surface-strong: #ffffff;
            --op-border: rgba(18, 38, 57, 0.09);
            --op-text: #14324a;
            --op-muted: #6c7a86;
            --op-brand: #ff8f3d;
            --op-brand-2: #1c7c7a;
            --op-brand-3: #243b6b;
            --op-good: #2e9b6c;
            --op-warn: #d68720;
            --op-bad: #c1463b;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(255, 143, 61, 0.16), transparent 24%),
                radial-gradient(circle at top right, rgba(28, 124, 122, 0.15), transparent 22%),
                radial-gradient(circle at bottom right, rgba(36, 59, 107, 0.08), transparent 20%),
                linear-gradient(180deg, #fcf9f4 0%, #f6f0e7 42%, #f8f5ef 100%);
            color: var(--op-text);
            font-family: 'Manrope', sans-serif;
        }

        h1, h2, h3, h4, .op-title, .op-section-title {
            font-family: 'Plus Jakarta Sans', 'Manrope', sans-serif;
            letter-spacing: -0.02em;
        }

        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stToolbar"] { right: 1rem; }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(247,242,234,0.98));
            border-right: 1px solid var(--op-border);
        }

        .op-hero {
            padding: 1.4rem 1.5rem;
            border-radius: 28px;
            background:
                linear-gradient(135deg, rgba(255,255,255,0.94), rgba(255,255,255,0.76)),
                linear-gradient(135deg, rgba(255, 143, 61, 0.12), rgba(28, 124, 122, 0.08));
            border: 1px solid rgba(255,255,255,0.72);
            box-shadow: 0 26px 70px rgba(27, 48, 74, 0.10);
            margin-bottom: 1rem;
        }

        .op-topbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
            padding: 0.75rem 1rem;
            border-radius: 18px;
            background: rgba(255,255,255,0.72);
            border: 1px solid rgba(18, 38, 57, 0.08);
        }

        .op-topbar strong { color: var(--op-text); }
        .op-topbar span { color: var(--op-muted); }

        .op-title {
            font-size: 2.25rem;
            font-weight: 800;
            line-height: 1.02;
            color: var(--op-text);
            margin: 0;
        }

        .op-subtitle {
            color: var(--op-muted);
            font-size: 1rem;
            margin-top: 0.45rem;
            max-width: 58rem;
        }

        .op-chip-row { display: flex; gap: 0.55rem; flex-wrap: wrap; margin-top: 1rem; }
        .op-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.42rem 0.75rem;
            border-radius: 999px;
            font-size: 0.83rem;
            font-weight: 700;
            border: 1px solid var(--op-border);
            background: rgba(255,255,255,0.74);
            color: var(--op-text);
        }
        .op-chip.brand { background: rgba(255, 143, 61, 0.12); color: #9e4d11; }
        .op-chip.good { background: rgba(46, 155, 108, 0.12); color: #1e6d4a; }
        .op-chip.warn { background: rgba(214, 135, 32, 0.12); color: #8b530e; }
        .op-chip.cool { background: rgba(28, 124, 122, 0.12); color: #155c5a; }

        .op-card {
            background: var(--op-surface);
            border: 1px solid var(--op-border);
            border-radius: 24px;
            padding: 1rem 1.05rem;
            box-shadow: 0 18px 42px rgba(27, 48, 74, 0.07);
            margin-bottom: 0.9rem;
            backdrop-filter: blur(14px);
            transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
        }

        .op-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 20px 48px rgba(27, 48, 74, 0.10);
            border-color: rgba(255, 143, 61, 0.22);
        }

        .op-section-title {
            font-size: 1.05rem;
            font-weight: 800;
            color: var(--op-text);
            margin-bottom: 0.25rem;
        }

        .op-section-subtitle {
            color: var(--op-muted);
            font-size: 0.92rem;
            margin-bottom: 0.9rem;
        }

        .op-kpi-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.7rem;
            margin-top: 1rem;
        }

        .op-kpi {
            border-radius: 20px;
            padding: 0.95rem 1rem;
            background: rgba(255,255,255,0.86);
            border: 1px solid rgba(18, 38, 57, 0.08);
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.85);
        }
        .op-kpi-label { color: var(--op-muted); font-size: 0.82rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; }
        .op-kpi-value { font-size: 1.65rem; line-height: 1.05; font-weight: 800; color: var(--op-text); margin-top: 0.4rem; }
        .op-kpi-note { color: var(--op-muted); font-size: 0.86rem; margin-top: 0.25rem; }

        .op-metric-callout {
            background: linear-gradient(135deg, rgba(255, 143, 61, 0.12), rgba(28, 124, 122, 0.10));
            border: 1px solid rgba(18, 38, 57, 0.08);
            padding: 0.9rem 1rem;
            border-radius: 18px;
        }

        .op-empty {
            padding: 1rem;
            border-radius: 18px;
            border: 1px dashed rgba(18, 38, 57, 0.14);
            background: rgba(255,255,255,0.6);
            color: var(--op-muted);
        }

        .op-rail {
            padding: 0.9rem;
            border-radius: 20px;
            background: rgba(255,255,255,0.78);
            border: 1px solid rgba(18, 38, 57, 0.08);
        }

        .op-rail h4 { margin: 0 0 0.45rem 0; }
        .op-rail p { margin-bottom: 0.55rem; color: var(--op-muted); }

        /* Animations */
        @keyframes slideInUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes fadeIn {
            from {
                opacity: 0;
            }
            to {
                opacity: 1;
            }
        }

        @keyframes pulse {
            0%, 100% {
                opacity: 1;
            }
            50% {
                opacity: 0.7;
            }
        }

        @keyframes slideInRight {
            from {
                opacity: 0;
                transform: translateX(-20px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }

        .op-card {
            animation: slideInUp 0.4s ease-out;
        }

        .op-kpi {
            animation: slideInRight 0.5s ease-out;
        }

        .op-chip {
            animation: fadeIn 0.3s ease-in;
        }

        .stButton > button {
            transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
        }

        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 24px rgba(27, 48, 74, 0.15) !important;
        }

        .stButton > button:active {
            transform: translateY(0);
        }

        [data-testid="stSelectbox"] {
            transition: border-color 200ms ease;
        }

        .op-alert-new {
            animation: pulse 2s ease-in-out infinite;
            border-left: 4px solid var(--op-warn);
        }

        .op-route-badge {
            display: inline-block;
            padding: 0.35rem 0.7rem;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 700;
            animation: slideInRight 0.4s ease-out;
        }

        .op-route-badge.high {
            background: rgba(193, 70, 59, 0.12);
            color: #8b2e1e;
        }

        .op-route-badge.medium {
            background: rgba(214, 135, 32, 0.12);
            color: #8b530e;
        }

        .op-route-badge.low {
            background: rgba(46, 155, 108, 0.12);
            color: #1e6d4a;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def pill(text: str, tone: str = "brand") -> str:
    return f'<span class="op-chip {tone}">{text}</span>'


def section_header(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="op-section-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="op-section-subtitle">{subtitle}</div>', unsafe_allow_html=True)


def metric_grid(items: list[tuple[str, str, str]]) -> None:
    cols = st.columns(len(items))
    for col, (label, value, note) in zip(cols, items):
        with col:
            st.markdown(
                f'''
                <div class="op-kpi">
                    <div class="op-kpi-label">{label}</div>
                    <div class="op-kpi-value">{value}</div>
                    <div class="op-kpi-note">{note}</div>
                </div>
                ''',
                unsafe_allow_html=True,
            )


def empty_state(text: str) -> None:
    st.markdown(f'<div class="op-empty">{text}</div>', unsafe_allow_html=True)


def sidebar_rail(store: PHRSStore) -> None:
    st.sidebar.markdown(f"## {APP_NAME}")
    st.sidebar.caption(APP_TAGLINE)
    current_source = st.session_state.get("hotspot_source") or str(_preferred_hotspot_path().name)
    unread_ngos = [note for note in store.notifications if note.get("recipient_type") == "ngo" and not note.get("is_read")]
    st.sidebar.markdown(
        f'''
        <div class="op-rail">
            <h4>Mission Console</h4>
            <p>{pill('Demo ready', 'good')} {pill('Area-level vision', 'cool')} {pill(f'{len(unread_ngos)} NGO alerts', 'warn')}</p>
            <p><strong>Hotspot source:</strong><br/>{current_source}</p>
            <p><strong>Listings:</strong> {len(store.food_listings)}<br/>
            <strong>Requests:</strong> {len(store.user_requests)}<br/>
            <strong>Hotspots:</strong> {len(store.hotspots)}<br/>
            <strong>Dispatch jobs:</strong> {len(store.dispatch_jobs)}</p>
        </div>
        ''',
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("### Quick states")
    if st.session_state.get("use_supabase"):
        st.sidebar.success("Supabase cloud sync: connected")
    elif CLOUD_WRITE_REQUIRED:
        st.sidebar.error("Supabase cloud sync: required but disconnected")
    else:
        st.sidebar.warning("Supabase cloud sync: disconnected (local fallback)")
    st.sidebar.write("- Use Fallback JSON until the sample video is ready")
    st.sidebar.write("- Realtime YOLO uses the local video path")
    st.sidebar.write("- NGO inbox gets new request alerts")
    st.sidebar.write("- OTP is verified in the next tab")

    if unread_ngos:
        st.sidebar.markdown("### Latest NGO alerts")
        for note in unread_ngos[:3]:
            st.sidebar.markdown(
                f'''<div class="op-rail" style="margin-bottom:0.55rem;">
                    <strong>{note.get('title', 'Alert')}</strong><br/>
                    <span style="color: var(--op-muted);">{note.get('message', '')}</span>
                </div>''',
                unsafe_allow_html=True,
            )


def load_hotspots_ui(store: PHRSStore) -> None:
    section_header("Demand Hotspots", "Load generated JSON, fallback JSON, or realtime YOLO output for a live priority map.")
    col1, col2 = st.columns([1, 2], gap="large")
    with col1:
        st.markdown('<div class="op-card">', unsafe_allow_html=True)
        st.markdown(pill("Wait for video upload", "warn") + " " + pill("Realtime YOLO", "cool") + " " + pill("Fallback safe mode", "good"), unsafe_allow_html=True)
        mode = st.radio("Detection Mode", ["Generated JSON", "Fallback JSON", "Realtime YOLO"], horizontal=False)
        video_path = st.text_input("Video path (for realtime mode)", value="video/sample.mp4")
        st.caption("Choose fallback mode now and switch to realtime after you upload a sample clip.")
        if st.button("Load / Refresh Hotspots", type="primary"):
            source_path = GENERATED_HOTSPOTS if mode == "Generated JSON" else FALLBACK_HOTSPOTS
            if mode == "Realtime YOLO":
                hotspots = quick_realtime_hotspots(video_path, thumbnail_dir=HOTSPOT_THUMBNAILS)
                if hotspots:
                    save_hotspots_to_json(
                        GENERATED_HOTSPOTS,
                        hotspots,
                        metadata={"source": "realtime-yolo", "video_path": video_path},
                    )
                    source_path = GENERATED_HOTSPOTS
                else:
                    st.warning("Realtime inference unavailable or failed. Loading the best available JSON fallback.")
                    source_path = GENERATED_HOTSPOTS if GENERATED_HOTSPOTS.exists() else FALLBACK_HOTSPOTS

            hotspots = load_hotspots_from_json(source_path)
            if not hotspots and source_path != FALLBACK_HOTSPOTS:
                hotspots = load_hotspots_from_json(FALLBACK_HOTSPOTS)
                source_path = FALLBACK_HOTSPOTS

            store.set_hotspots(hotspots)
            st.session_state.hotspot_source = str(source_path)
            st.success(f"Loaded {len(hotspots)} hotspot rows from {source_path.name}")
        st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.get("hotspot_source"):
            st.caption(f"Current source: {st.session_state.hotspot_source}")

    with col2:
        if store.hotspots:
            metric_grid(
                [
                    ("Hotspots", str(len(store.hotspots)), "Priority queue loaded"),
                    ("High priority", str(len([h for h in store.hotspots if h.get('priority') == 'HIGH'])), "Needs attention"),
                    ("With thumbnails", str(len([h for h in store.hotspots if h.get('thumbnail_path')])), "Visual proof available"),
                ]
            )
            st.dataframe(as_table(store.hotspots), use_container_width=True, hide_index=True)
            thumbnail_rows = [row for row in store.hotspots if row.get("thumbnail_path")]
            if thumbnail_rows:
                section_header("Hotspot Thumbnails", "Visual references generated from the YOLO path or the latest hotspots bundle.")
                preview_rows = thumbnail_rows[:3]
                preview_cols = st.columns(len(preview_rows))
                for col, hotspot in zip(preview_cols, preview_rows):
                    thumbnail_path = _thumbnail_to_path(hotspot.get("thumbnail_path"))
                    if thumbnail_path and thumbnail_path.exists():
                        col.image(str(thumbnail_path), caption=f"{hotspot.get('zone', 'Hotspot')} · {hotspot.get('priority', 'LOW')}", use_column_width=True)
                    else:
                        col.info(f"No thumbnail for {hotspot.get('zone', 'hotspot')}")
        else:
            empty_state("No hotspot data loaded yet. Load the fallback bundle now, then switch to realtime YOLO once the sample video is ready.")


def restaurant_panel(store: PHRSStore) -> None:
    section_header("Restaurant Intake", "Capture surplus food quickly and surface an expiry-aware safety score for the kitchen operator.")
    left, right = st.columns([1.1, 1.3], gap="large")

    with left:
        st.markdown('<div class="op-card">', unsafe_allow_html=True)
        st.markdown(pill("Surplus upload", "brand") + " " + pill("Safety score", "good") + " " + pill("Expiry-aware", "cool"), unsafe_allow_html=True)
        with st.form("add_listing"):
            restaurant = st.selectbox("Restaurant", store.restaurants, format_func=lambda r: r["name"])
            food_type = st.selectbox("Food Type", ["Rice", "Chapati", "Curry", "Dal", "Vegetable", "Meat", "Bread"])
            qty = st.number_input("Quantity (plates)", min_value=1, max_value=1000, value=25)
            cooked_minutes_ago = st.slider("Cooked how many minutes ago?", min_value=5, max_value=360, value=60)
            submitted = st.form_submit_button("Add Listing")

            if submitted:
                before_notifications = len(store.notifications)
                cooked_at = datetime.now(timezone.utc) - timedelta(minutes=int(cooked_minutes_ago))
                new_item = store.add_food_listing(
                    restaurant_id=restaurant["id"],
                    food_type=food_type,
                    quantity=int(qty),
                    cooked_at_iso=cooked_at.isoformat(),
                )
                # Sync to Supabase
                synced = sync_to_supabase("food_listing", new_item)
                if CLOUD_WRITE_REQUIRED and not synced:
                    store.food_listings = [f for f in store.food_listings if f.get("id") != new_item.get("id")]
                    del store.notifications[before_notifications:]
                    st.error("Listing blocked: could not write to Supabase cloud.")
                    st.stop()
                sync_new_notifications(before_notifications, store)
                st.success(f"Added {new_item['food_type']} ({new_item['quantity_total']} plates)")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        store.refresh_listing_scores()
        metric_grid(
            [
                ("Active surplus", str(len([f for f in store.food_listings if f['status'] == 'available'])), "Available to dispatch"),
                ("Low safety", str(len([f for f in store.food_listings if f['safety_score'] < 60])), "Needs attention"),
                ("Urgent", str(len([f for f in store.food_listings if f['urgency'] == 'HIGH'])), "Move now"),
            ]
        )
        st.markdown('<div class="op-card">', unsafe_allow_html=True)
        st.markdown("### Active Surplus")
        st.dataframe(as_table(store.food_listings), use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)


def request_panel(store: PHRSStore) -> None:
    section_header("Direct Requests", "Users can request food directly; the app merges requests with YOLO hotspots in one queue.")
    left, right = st.columns([1, 1.3], gap="large")

    with left:
        st.markdown('<div class="op-card">', unsafe_allow_html=True)
        st.markdown(pill("Demand entry", "brand") + " " + pill("User-facing", "cool"), unsafe_allow_html=True)
        with st.form("create_request"):
            requester_name = st.text_input("Requester Name", value="Community User")
            quantity = st.number_input("Quantity Needed", min_value=1, max_value=200, value=15)
            lat = st.number_input("Latitude", value=12.9712, format="%.6f")
            lng = st.number_input("Longitude", value=77.5941, format="%.6f")
            submit_req = st.form_submit_button("Create Request")

            if submit_req:
                before_notifications = len(store.notifications)
                req = store.add_user_request(requester_name, int(quantity), float(lat), float(lng))
                # Sync to Supabase
                synced = sync_to_supabase("user_request", req)
                if CLOUD_WRITE_REQUIRED and not synced:
                    store.user_requests = [r for r in store.user_requests if r.get("id") != req.get("id")]
                    del store.notifications[before_notifications:]
                    st.error("Request blocked: could not write to Supabase cloud.")
                    st.stop()
                sync_new_notifications(before_notifications, store)
                st.success(f"Request created: {req['id']}")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        metric_grid(
            [
                ("Open requests", str(len([r for r in store.user_requests if r['status'] == 'open'])), "Waiting for match"),
                ("Fulfilled", str(len([r for r in store.user_requests if r['status'] == 'fulfilled'])), "Completed jobs"),
                ("Hotspots linked", str(len(store.hotspots)), "Vision demand available"),
            ]
        )
        st.markdown('<div class="op-card">', unsafe_allow_html=True)
        st.markdown("### Open Requests")
        st.dataframe(as_table(store.user_requests), use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)


def matching_panel(store: PHRSStore) -> None:
    section_header("Matching + Dispatch", "This is the mission core: pair urgent food with the best nearby need and verify the handoff.")
    suggestions = store.suggest_matches()
    if not suggestions:
        empty_state("No suggestions available. Add food listings and load hotspots or requests to generate a dispatch queue.")
        return

    metric_grid(
        [
            ("Suggestions", str(len(suggestions)), "Ranked by priority"),
            ("Top priority", suggestions[0]["target_name"], "Best match right now"),
            ("Fastest route", f"{suggestions[0]['distance_km']} km", "Closest viable move"),
        ]
    )

    st.markdown('<div class="op-card">', unsafe_allow_html=True)
    st.dataframe(as_table(suggestions), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

    left, right = st.columns([1.2, 1], gap="large")
    with left:
        selected = st.selectbox(
            "Select suggestion to dispatch",
            suggestions,
            format_func=lambda s: f"{s['restaurant_name']} → {s['target_name']} ({s['suggested_qty']} plates)",
        )
    with right:
        ngo = st.selectbox("Assign NGO", store.ngos, format_func=lambda n: n["name"])

    if st.button("Create Dispatch Job", type="primary"):
        before_notifications = len(store.notifications)
        job = store.create_dispatch(selected, ngo_id=ngo["id"])
        # Sync to Supabase
        synced = sync_to_supabase("dispatch_job", job)
        if CLOUD_WRITE_REQUIRED and not synced:
            store.dispatch_jobs = [j for j in store.dispatch_jobs if j.get("id") != job.get("id")]
            del store.notifications[before_notifications:]
            st.error("Dispatch blocked: could not write to Supabase cloud.")
            st.stop()
        sync_new_notifications(before_notifications, store)
        st.success(f"Dispatch created: {job['id']}")
        st.info(f"Pickup OTP (demo): {job['pickup_otp']}")
        st.info(f"Delivery OTP (demo): {job['delivery_otp']}")

    st.markdown('<div class="op-card">', unsafe_allow_html=True)
    st.markdown("### Dispatch Jobs")
    st.dataframe(as_table(store.dispatch_jobs), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)


def otp_panel(store: PHRSStore) -> None:
    section_header("OTP Verification", "Two-step trust gates keep pickup and delivery auditable for judges and partners.")
    jobs = store.dispatch_jobs
    if not jobs:
        empty_state("No dispatch jobs yet. Create a dispatch first, then verify pickup and delivery here.")
        return

    job = st.selectbox("Dispatch Job", jobs, format_func=lambda j: f"{j['id']} ({j['status']})")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="op-card">', unsafe_allow_html=True)
        st.markdown("### Pickup Confirmation")
        pickup_in = st.text_input("Enter pickup OTP", key="pickup_otp_input")
        if st.button("Verify Pickup"):
            if store.verify_pickup(job["id"], pickup_in):
                # Sync job update to Supabase
                updated_job = store.dispatch_job_by_id(job["id"])
                if updated_job:
                    sync_to_supabase("update_dispatch", updated_job)
                st.success("Pickup verified")
            else:
                st.error("Pickup OTP invalid or expired")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="op-card">', unsafe_allow_html=True)
        st.markdown("### Delivery Confirmation")
        delivery_in = st.text_input("Enter delivery OTP", key="delivery_otp_input")
        if st.button("Verify Delivery"):
            if store.verify_delivery(job["id"], delivery_in):
                # Sync job update, food listing update, and impact entries to Supabase
                updated_job = store.dispatch_job_by_id(job["id"])
                if updated_job:
                    sync_to_supabase("update_dispatch", updated_job)
                # Sync food listing update
                food = store.food_by_id(job.get("suggestion", {}).get("food_id") if isinstance(job.get("suggestion"), dict) else job.get("food_id"))
                if food:
                    sync_to_supabase("update_food", food)
                # Sync impact entries
                for entry in store.impact_ledger:
                    sync_to_supabase("impact_entry", entry)
                st.success("Delivery verified and credits added")
            else:
                st.error("Delivery OTP invalid or expired")
        st.markdown("</div>", unsafe_allow_html=True)


def notification_panel(store: PHRSStore) -> None:
    section_header("NGO Inbox", "New hotel surplus and customer requests land here for the NGO team to act on quickly.")
    unread = [note for note in store.notifications if note.get("recipient_type") == "ngo" and not note.get("is_read")]
    total = [note for note in store.notifications if note.get("recipient_type") == "ngo"]

    metric_grid(
        [
            ("Unread alerts", str(len(unread)), "Fresh NGO notifications"),
            ("Total alerts", str(len(total)), "All incoming actions"),
            ("Request sources", str(len([n for n in total if n.get('source_kind') == 'user_request'])), "Customer demand"),
        ]
    )

    left, right = st.columns([1.15, 0.85], gap="large")
    with left:
        st.markdown('<div class="op-card">', unsafe_allow_html=True)
        st.markdown("### Incoming alerts")
        if unread:
            for note in unread[:8]:
                st.markdown(
                    f'''<div class="op-card" style="margin-bottom:0.7rem; background: rgba(255,255,255,0.92);">
                        <div style="display:flex; justify-content:space-between; gap:1rem; align-items:flex-start;">
                            <div>
                                <div style="font-weight:800; color: var(--op-text);">{note.get('title')}</div>
                                <div style="color: var(--op-muted); margin-top:0.2rem;">{note.get('message')}</div>
                            </div>
                            <div style="text-align:right; color: var(--op-muted); font-size:0.82rem; white-space:nowrap;">{note.get('source_label', '')}</div>
                        </div>
                    </div>''',
                    unsafe_allow_html=True,
                )
        else:
            empty_state("No unread NGO alerts yet. New restaurant surplus and customer requests will appear here.")

        if st.button("Mark NGO inbox as read"):
            changed = store.mark_all_notifications_read("ngo")
            for note in store.notifications:
                if note.get("recipient_type") == "ngo":
                    sync_to_supabase("update_notification", note)
            st.success(f"Marked {changed} notification(s) as read")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="op-card">', unsafe_allow_html=True)
        st.markdown("### What triggers alerts")
        st.write(
            "• Hotel surplus posts create alerts for the NGO team immediately.\n"
            "• Customer requests create alerts for the NGO team immediately.\n"
            "• Dispatch assignment creates a direct alert to the assigned NGO."
        )
        st.markdown("</div>", unsafe_allow_html=True)


def company_panel(store: PHRSStore) -> None:
    section_header("Company Impact Dashboard", "A sponsor view that looks like CSR operations, not a payment screen.")
    company = store.companies[0] if store.companies else {"name": "N/A", "branding_name": "N/A"}
    st.markdown(f'<div class="op-card"><div class="op-section-title">Sponsor: {company["name"]}</div><div class="op-section-subtitle">{company["branding_name"]}</div></div>', unsafe_allow_html=True)

    metric_grid(
        [
            ("Restaurant credits", str(store.total_credits("restaurant")), "Saved waste value"),
            ("NGO credits", str(store.total_credits("ngo")), "Verified handoffs"),
            ("Company credits", str(store.total_credits("company")), "Sponsored impact"),
        ]
    )

    st.markdown('<div class="op-card">', unsafe_allow_html=True)
    st.markdown("### Impact Ledger")
    st.dataframe(as_table(store.impact_ledger), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)


def overview_panel(store: PHRSStore) -> None:
    unread_ngos = len([note for note in store.notifications if note.get("recipient_type") == "ngo" and not note.get("is_read")])
    st.markdown(
        f'''
        <div class="op-topbar">
            <div><strong>Live mode:</strong> Cloud sync on, YOLO ready, NGO inbox active</div>
            <span>{unread_ngos} unread NGO alerts</span>
        </div>
        ''',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'''
        <div class="op-hero">
            <div class="op-title">{APP_NAME}</div>
            <div class="op-subtitle">{APP_TAGLINE}. Built for a fast hackathon demo: clean surplus intake, demand detection, and trust-verified dispatch.</div>
            <div class="op-chip-row">
                {pill('Demo ready', 'good')}
                {pill('Fallback live', 'cool')}
                {pill('YOLO waiting', 'warn')}
                {pill('OTP gated', 'brand')}
            </div>
            <div class="op-kpi-grid">
                <div class="op-kpi"><div class="op-kpi-label">Active listings</div><div class="op-kpi-value">{len([f for f in store.food_listings if f["status"] == "available"])}</div><div class="op-kpi-note">Ready to route</div></div>
                <div class="op-kpi"><div class="op-kpi-label">Open requests</div><div class="op-kpi-value">{len([r for r in store.user_requests if r["status"] == "open"])}</div><div class="op-kpi-note">Direct demand</div></div>
                <div class="op-kpi"><div class="op-kpi-label">Hotspots</div><div class="op-kpi-value">{len(store.hotspots)}</div><div class="op-kpi-note">Vision or fallback</div></div>
            </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.15, 0.85], gap="large")
    with left:
        st.markdown('<div class="op-card">', unsafe_allow_html=True)
        section_header("What the system does", "OnePlate connects restaurants, hotspots, requests, NGOs, and sponsors in one dispatch loop.")
        st.write(
            "Restaurants upload surplus food, the app scores freshness, hotspots or requests become demand targets, and verified pickup/delivery updates the impact ledger."
        )
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown('<div class="op-card">', unsafe_allow_html=True)
        section_header("Live operational status", "The sidebar shows source, counts, and the current execution mode.")
        st.markdown(
            f'''<div class="op-metric-callout">
            <strong>Current hotspot source:</strong> {st.session_state.get("hotspot_source") or _preferred_hotspot_path().name}<br/>
            <strong>Dispatch queue:</strong> {len(store.dispatch_jobs)} jobs<br/>
            <strong>Ledger entries:</strong> {len(store.impact_ledger)} rows
            </div>''',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)


def quick_hotspot_simulator(store: PHRSStore) -> None:
    section_header("Quick Hotspot Simulator", "Useful while the sample video is pending: simulate crowd intensity and persistence to preview scoring.")
    c1, c2, c3 = st.columns(3)
    people = c1.slider("People Count", 0, 20, 6)
    duration = c2.slider("Persistence Minutes", 0, 60, 15)
    zone = c3.selectbox("Zone", ["Zone A", "Zone B", "Zone C"])
    score = need_score(people, duration)
    st.markdown('<div class="op-card">', unsafe_allow_html=True)
    metric_grid(
        [
            ("Need score", str(score), "Based on people + persistence"),
            ("Priority", priority_from_need(score), "Routing label"),
            ("Zone", zone, "Area-level inference"),
        ]
    )
    st.markdown("</div>", unsafe_allow_html=True)


def route_optimization_panel(store: PHRSStore) -> None:
    """Interactive route optimization map showing dispatch assignments and live tracking."""
    section_header("Route Optimization Map", "Real-time food dispatch routing with ETA tracking and priority visualization.")
    
    if not store.dispatch_jobs:
        empty_state("No active dispatch jobs. Create dispatch assignments first to see optimized routes on the map.")
        return
    
    # Build targets from requests and hotspots
    targets = []
    for req in store.user_requests:
        if req.get("status") == "open":
            targets.append({
                "id": req["id"],
                "name": f"Request: {req['requester_name']}",
                "latitude": req.get("latitude", 12.9712),
                "longitude": req.get("longitude", 77.5941),
                "type": "user_request",
            })
    for hotspot in store.hotspots[:5]:  # Limit to 5 hotspots to avoid clutter
        targets.append({
            "id": hotspot["id"],
            "name": f"Hotspot: {hotspot.get('zone', 'Unknown')}",
            "latitude": hotspot.get("latitude", 12.9712),
            "longitude": hotspot.get("longitude", 77.5941),
            "type": "hotspot",
        })
    
    # Run optimization
    assignments = greedy_assignment(store.dispatch_jobs, store.restaurants, store.ngos, targets)
    summary = build_route_summary(assignments)
    
    # Display summary metrics
    metric_grid([
        ("Active routes", str(summary["total_routes"]), "Optimized assignments"),
        ("Total distance", f"{summary['total_distance_km']} km", "All routes combined"),
        ("Avg distance", f"{summary['avg_distance_km']} km", "Per route"),
    ])
    
    # Create folium map centered on Bangalore
    center_lat = 12.9716
    center_lng = 77.5946
    m = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=12,
        tiles="OpenStreetMap",
    )
    
    # Add restaurant markers (green, source points)
    for restaurant in store.restaurants:
        folium.Marker(
            location=[restaurant.get("latitude", 12.9716), restaurant.get("longitude", 77.5946)],
            popup=f"<b>{restaurant['name']}</b><br>Restaurant (Surplus Source)",
            tooltip=restaurant["name"],
            icon=folium.Icon(color="green", icon="info-sign", prefix="glyphicon"),
        ).add_to(m)
    
    # Add NGO markers (blue, operational base)
    for ngo in store.ngos:
        folium.Marker(
            location=[ngo.get("latitude", 12.9712), ngo.get("longitude", 77.5941)],
            popup=f"<b>{ngo['name']}</b><br>NGO Distribution Center",
            tooltip=ngo["name"],
            icon=folium.Icon(color="blue", icon="info-sign", prefix="glyphicon"),
        ).add_to(m)
    
    # Add route lines with priority coloring
    priority_colors = {
        "HIGH": "#c1463b",
        "MEDIUM": "#d68720",
        "LOW": "#2e9b6c",
    }
    
    for assignment in assignments:
        color = priority_colors.get(assignment["priority"], "#999999")
        
        # Draw route line from restaurant to target
        folium.PolyLine(
            locations=[
                [assignment["restaurant_lat"], assignment["restaurant_lng"]],
                [assignment["target_lat"], assignment["target_lng"]],
            ],
            color=color,
            weight=2.5,
            opacity=0.7,
            popup=f"""
            <b>{assignment['restaurant_name']}</b> → <b>{assignment['target_name']}</b><br>
            Distance: {assignment['distance_km']} km<br>
            ETA: {assignment['eta_minutes']} min<br>
            NGO: {assignment['ngo_name']}<br>
            Priority: {assignment['priority']}<br>
            Status: {assignment['status']}
            """,
        ).add_to(m)
        
        # Add target markers (orange for hotspots, red for requests)
        target_color = "orange" if assignment["target_type"] == "hotspot" else "red"
        folium.CircleMarker(
            location=[assignment["target_lat"], assignment["target_lng"]],
            radius=8,
            popup=f"<b>{assignment['target_name']}</b><br>Qty: {assignment['quantity']} plates<br>Priority: {assignment['priority']}",
            color=color,
            fill=True,
            fillColor=target_color,
            fillOpacity=0.7,
            weight=2,
        ).add_to(m)
    
    # Render map
    st.markdown('<div class="op-card">', unsafe_allow_html=True)
    st_folium(m, width=1200, height=500)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Show detailed route table
    st.markdown('<div class="op-card">', unsafe_allow_html=True)
    st.markdown("### Route Details")
    
    if assignments:
        # Build display table
        display_rows = []
        for a in assignments:
            priority_badge = f'<span class="op-route-badge {a["priority"].lower()}">{a["priority"]}</span>'
            display_rows.append({
                "Priority": priority_badge,
                "Restaurant": a["restaurant_name"],
                "Target": a["target_name"],
                "NGO": a["ngo_name"],
                "Distance": f"{a['distance_km']} km",
                "ETA": f"{a['eta_minutes']} min",
                "Status": a["status"],
            })
        
        st.dataframe(
            [{k: (v if k != "Priority" else v) for k, v in row.items()} for row in display_rows],
            use_container_width=True,
            hide_index=True,
        )
        
        # Show raw HTML table for better styling
        html_table = "<table style='width:100%; border-collapse:collapse;'>"
        html_table += "<tr style='background: rgba(255,255,255,0.5); border-bottom: 1px solid var(--op-border);'>"
        html_table += "<th style='padding:0.5rem; text-align:left; font-weight:700;'>Priority</th>"
        html_table += "<th style='padding:0.5rem; text-align:left; font-weight:700;'>Restaurant</th>"
        html_table += "<th style='padding:0.5rem; text-align:left; font-weight:700;'>Target</th>"
        html_table += "<th style='padding:0.5rem; text-align:left; font-weight:700;'>NGO</th>"
        html_table += "<th style='padding:0.5rem; text-align:left; font-weight:700;'>Distance</th>"
        html_table += "<th style='padding:0.5rem; text-align:left; font-weight:700;'>ETA</th>"
        html_table += "<th style='padding:0.5rem; text-align:left; font-weight:700;'>Status</th></tr>"
        
        for a in assignments:
            priority_color = priority_colors.get(a["priority"], "#999999")
            html_table += f"<tr style='border-bottom: 1px solid var(--op-border);'>"
            html_table += f"<td style='padding:0.5rem;'><span class='op-route-badge {a['priority'].lower()}'>{a['priority']}</span></td>"
            html_table += f"<td style='padding:0.5rem;'>{a['restaurant_name']}</td>"
            html_table += f"<td style='padding:0.5rem;'>{a['target_name']}</td>"
            html_table += f"<td style='padding:0.5rem;'>{a['ngo_name']}</td>"
            html_table += f"<td style='padding:0.5rem;'>{a['distance_km']} km</td>"
            html_table += f"<td style='padding:0.5rem;'>{a['eta_minutes']} min</td>"
            html_table += f"<td style='padding:0.5rem; color: {priority_color};'>● {a['status']}</td>"
            html_table += "</tr>"
        
        html_table += "</table>"
        st.markdown(html_table, unsafe_allow_html=True)
    else:
        empty_state("No routes optimized. Assign dispatch jobs first.")
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Summary stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown('<div class="op-card">', unsafe_allow_html=True)
        st.metric("High Priority", summary["high_priority_count"], "Urgent routes")
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="op-card">', unsafe_allow_html=True)
        st.metric("Medium Priority", summary["medium_priority_count"], "Standard routes")
        st.markdown("</div>", unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="op-card">', unsafe_allow_html=True)
        st.metric("Low Priority", summary["low_priority_count"], "Routine routes")
        st.markdown("</div>", unsafe_allow_html=True)
    with col4:
        st.markdown('<div class="op-card">', unsafe_allow_html=True)
        st.metric("Total ETA", f"{summary['total_eta_minutes']} min", "All routes")
        st.markdown("</div>", unsafe_allow_html=True)


def video_upload_panel(store: PHRSStore) -> None:
    """Video upload and zone detection panel with YOLO analysis."""
    section_header("Video Upload & Zone Detection", "Upload videos to detect demand hotspots, crowd zones, and threats using AI vision.")
    
    from app.video_processor import VideoProcessor
    
    st.markdown('<div class="op-card">', unsafe_allow_html=True)
    st.markdown("### 📹 Upload Video")
    
    video_file = st.file_uploader("Choose a video file", type=["mp4", "avi", "mov", "mkv", "flv"])
    
    col1, col2, col3 = st.columns(3)
    with col1:
        fps_sample = st.slider("Frame sampling (every Nth frame)", 1, 10, 2)
    with col2:
        max_frames = st.slider("Max frames to extract", 5, 50, 20)
    with col3:
        model_choice = st.selectbox("YOLO Model", ["yolov8n.pt", "yolov8s.pt", "yolov8m.pt"], index=0)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    if video_file and st.button("🔍 Analyze Video & Detect Zones", type="primary"):
        st.info("Processing video... This may take a minute.")
        progress_bar = st.progress(0)
        
        try:
            # Initialize processor
            processor = VideoProcessor(model_name=model_choice)
            progress_bar.progress(10)
            
            # Extract frames
            st.write("📸 Extracting frames...")
            frames = processor.extract_frames(video_file.getvalue(), fps_sample=fps_sample, max_frames=max_frames)
            progress_bar.progress(40)
            
            if not frames:
                st.error(f"Could not extract frames: {processor.last_error}")
                return
            
            st.success(f"✅ Extracted {len(frames)} frames")
            
            # Detect hotspots
            st.write("🎯 Detecting hotspots from zones...")
            hotspots = processor.detect_hotspots_from_frames(frames)
            progress_bar.progress(70)
            
            if hotspots:
                st.success(f"✅ Detected {len(hotspots)} hotspot zones")
            else:
                st.warning("No significant hotspots detected (try adjusting model or frame count)")
            
            # Upload to Supabase
            st.write("☁️ Uploading to cloud...")
            video_name = video_file.name.replace(".", "_")
            success, error = processor.upload_frames_to_supabase(frames, hotspots, video_name)
            progress_bar.progress(100)
            
            if success:
                st.success("✅ Video analysis uploaded to Supabase!")
            else:
                st.warning(f"Partial upload: {error}")
            
            # Display results
            st.markdown('<div class="op-card">', unsafe_allow_html=True)
            st.markdown(f"### Results: {len(frames)} Frames Analyzed, {len(hotspots)} Hotspots Detected")
            
            # Show frame summaries with zones
            st.markdown("#### Frame Analysis Summary")
            frame_data_display = []
            for frame in frames[:15]:
                frame_data_display.append({
                    "Frame": frame['frame_index'],
                    "Time (ms)": frame['timestamp_ms'],
                    "People": frame['people_count'],
                    "Zones": len(frame['zones']),
                    "Classes": ", ".join(frame['detected_classes']),
                })
            
            if frame_data_display:
                st.dataframe(frame_data_display, use_container_width=True, hide_index=True)
            
            # Hotspot summary
            st.markdown("#### Detected Hotspots (Persistent Zones)")
            hotspot_data = []
            for hs in hotspots[:10]:
                hotspot_data.append({
                    "Hotspot ID": hs['id'][:12] + "...",
                    "People": hs.get('people_detections', 0),
                    "Frames": hs.get('persistence_frames', 0),
                    "Confidence": round(hs.get('avg_confidence', 0), 2),
                    "Classes": ", ".join(hs.get('detected_classes', [])),
                })
            
            if hotspot_data:
                st.dataframe(hotspot_data, use_container_width=True, hide_index=True)
            else:
                st.info("No persistent hotspots detected")
            
            # Load hotspots into store
            if hotspots:
                for hs in hotspots:
                    store.hotspots.append({
                        'id': hs['id'],
                        'zone': f"{hs['id']}",
                        'people_count': hs.get('people_detections', 0),
                        'persistence_minutes': int(hs.get('persistence_frames', 0) / 10),
                        'need_score': int(hs.get('people_detections', 0) * 100),
                        'priority': "HIGH" if hs.get('people_detections', 0) > 5 else "MEDIUM",
                        'lat': 12.9734 + (hs['bbox']['x1'] * 0.01),
                        'lng': 77.5964 + (hs['bbox']['y1'] * 0.01),
                        'time_detected': datetime.now(timezone.utc).isoformat(),
                    })
                
                st.success(f"✅ Loaded {len(hotspots)} hotspots into demand system!")
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        except Exception as e:
            st.error(f"Error processing video: {e}")
            import traceback
            st.text(traceback.format_exc())


def main() -> None:
    st.set_page_config(page_title=f"{APP_NAME} Dashboard", page_icon="🍱", layout="wide")
    inject_styles()

    store = get_store()
    sidebar_rail(store)
    tab = st.sidebar.radio(
        "Navigate",
        [
            "Overview",
            "Restaurant",
            "Demand Hotspots",
            "Video Upload",
            "Requests",
            "NGO Inbox",
            "Matching + Dispatch",
            "Route Map",
            "OTP Verify",
            "Company Dashboard",
            "Simulator",
        ],
    )

    if tab == "Overview":
        overview_panel(store)
    elif tab == "Restaurant":
        restaurant_panel(store)
    elif tab == "Demand Hotspots":
        load_hotspots_ui(store)
    elif tab == "Video Upload":
        video_upload_panel(store)
    elif tab == "Requests":
        request_panel(store)
    elif tab == "NGO Inbox":
        notification_panel(store)
    elif tab == "Matching + Dispatch":
        matching_panel(store)
    elif tab == "Route Map":
        route_optimization_panel(store)
    elif tab == "OTP Verify":
        otp_panel(store)
    elif tab == "Company Dashboard":
        company_panel(store)
    elif tab == "Simulator":
        quick_hotspot_simulator(store)


if __name__ == "__main__":
    main()
