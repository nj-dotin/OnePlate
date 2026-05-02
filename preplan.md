# PHRS — Preplan (Final Combined Idea)

## 1) What we are building

Project name: Proactive Hunger Response System (PHRS)

One-line pitch:
An AI-powered platform that combines surplus food supply, demand hotspot detection, and verified dispatch to reduce food waste and improve last-mile food access.

## 2) Core problem and approach

Most solutions are passive: they wait for requests.
Our system is proactive and trust-based:

- Restaurants upload surplus food with cooked time and quantity.
- System predicts safe consumption window and urgency.
- Demand is discovered in two ways:
  - Direct user request in app.
  - YOLO-based hotspot detection from sample video (zone-level, anonymous).
- Matching engine prioritizes where food should go first.
- Dispatch is OTP-verified to avoid fake claims.

## 3) Roles in the system

- Restaurant
  - Posts surplus food listings.
  - Gets waste reduction analytics, impact score, and verified donation logs.

- NGO
  - Accepts dispatch tasks.
  - Picks up and delivers food.
  - Completes OTP verification.

- Company (onboarding model)
  - No direct tax claims in MVP.
  - Company sponsors verified rescue operations and transport pool.
  - Gets auditable impact dashboard (meals rescued, waste reduced, area coverage).

- Beneficiary/User
  - Can request food via app.
  - Gets matched to nearby available supply through NGO/restaurant network.

## 4) What we removed (important)

- Removed direct tax-reduction implementation claims.
- Replaced with realistic "Impact Credits" + "ESG/CSR reporting" concept.
- Positioning:
  "Credits are measurable social impact units and can be integrated with policy frameworks later."

## 5) Key value proposition for each stakeholder

- Restaurant benefits
  - Reduced waste cost.
  - Higher local reputation via impact leaderboard.
  - Downloadable verified records.
  - Future demand suggestions (optional).

- NGO benefits
  - Prioritized dispatch recommendations.
  - Reduced confusion with clear urgency queue.
  - Trust-proof delivery logs.

- Company benefits
  - Measurable, auditable impact (not vanity CSR).
  - Sponsorship visibility in dashboard.
  - Funds outcomes, not random activity.

- Community benefits
  - Faster identification of need zones.
  - More food routed before expiry.

## 6) Delivery economics (who pays delivery?)

Hackathon-feasible model:

- Primary: Hyperlocal pickup intelligence
  - Prefer nearby NGOs/volunteers already close to source.
- Secondary: Sponsored dispatch pool
  - Company sponsorship covers micro-incentives for urgent deliveries.
- Fallback: Self-collection for eligible nearby requests.

This avoids dependency on a fictional logistics company.

## 7) Standout features (differentiators)

1. Dynamic Food Safety Score (not just timer)
   - Uses food type + cooked time + optional ambient factor.
   - Displays Safe/Medium/Risky bands.

2. Auto Rescue Trigger
   - If expiry risk is high and demand exists, auto-raise urgent alert.

3. Smart Partial Allocation
   - Splits one surplus listing across multiple needs to reduce wastage.

4. OTP Trust Layer (two-step)
   - OTP at handover + OTP at delivery confirmation.

5. Hotspot + Request Fusion
   - YOLO zone demand + direct user requests merged into one priority queue.

6. Impact Credits (non-tax MVP)
   - Example: 5 plates rescued = 10 impact credits.
   - Shown in stakeholder dashboards and leaderboards.

## 8) AI components

### A) Expiry/Safety estimation

RemainingSafeTime = Tsafe(food_type) - (Tnow - Tcooked)

SafetyScore (simple):
SafetyScore = 100 - a * elapsed_minutes - b * food_risk_factor

### B) YOLO hotspot scoring

- Detect only person class.
- Frame split into zones (left/center/right).
- Track persistence by zone.

NeedScore = alpha * people_count + beta * persistence_time

### C) Match priority

Priority = (NeedScore * available_quantity * urgency_weight) / distance

## 9) Supabase schema (MVP)

- restaurants
  - id, name, location_lat, location_lng, contact, impact_score

- ngos
  - id, name, location_lat, location_lng, contact, reliability_score

- companies
  - id, name, sponsor_balance, branding_name

- food_listings
  - id, restaurant_id, food_type, quantity, time_cooked, expiry_minutes, safety_score, status

- user_requests
  - id, requester_name, location_lat, location_lng, quantity_needed, status, created_at

- hotspots
  - id, zone, people_count, persistence_minutes, need_score, priority, lat, lng, time_detected

- dispatch_jobs
  - id, food_id, assigned_ngo_id, target_type(request/hotspot), target_id, status, created_at

- otp_verifications
  - id, dispatch_job_id, handover_otp, delivery_otp, handover_status, delivery_status, verified_at

- impact_ledger
  - id, actor_type(restaurant/ngo/company), actor_id, meals_saved, credits_added, event_ref, created_at

## 10) MVP dashboard modules

1. Restaurant panel
   - Add surplus listing
   - View safety/expiry urgency
   - View impact credits and logs

2. NGO panel
   - See dispatch queue (priority-sorted)
   - Accept task
   - OTP verification actions

3. Company panel
   - Sponsored deliveries count
   - Impact metrics and coverage map
   - Credit ledger summary

4. Operations panel
   - YOLO hotspot alerts
   - Live demand queue (requests + hotspots)
   - Allocation suggestions

## 11) 10-hour execution plan

1. Hour 0–2
   - Restaurant listing + expiry/safety logic + fake seed data.
2. Hour 2–4
   - YOLO detection script + zone persistence + hotspot output.
3. Hour 4–6
   - Request intake + matching engine + partial allocation.
4. Hour 6–8
   - Streamlit multi-role dashboard + dispatch workflow.
5. Hour 8–10
   - OTP trust flow + impact credits + polish + demo run.

## 12) Demo script flow

1. Restaurant uploads food with cooked time.
2. System computes safety score and urgency.
3. Show a hotspot and one direct user request.
4. Matching engine selects best source and split plan.
5. NGO accepts job, enters OTP at pickup and delivery.
6. Restaurant/NGO/company dashboards update with impact credits and verified logs.

## 13) Ethical and feasibility guardrails

- Never label individuals as "beggars".
- Only infer area-level potential need from anonymous visual signals.
- Use recorded sample video, not real traffic-camera claims.
- Be explicit that tax linkage is future integration, not MVP feature.

## 14) Final pitch line

We do not just list surplus food. We use AI to estimate safety, detect unmet-need zones, and route food through OTP-verified dispatch while giving restaurants, NGOs, and sponsoring companies measurable impact value.

