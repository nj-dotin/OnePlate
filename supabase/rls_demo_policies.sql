-- OnePlate hackathon demo RLS policies
-- Run this in Supabase SQL Editor so anon-key clients can read/write demo data.

alter table public.restaurants enable row level security;
alter table public.ngos enable row level security;
alter table public.companies enable row level security;
alter table public.food_listings enable row level security;
alter table public.user_requests enable row level security;
alter table public.hotspots enable row level security;
alter table public.dispatch_jobs enable row level security;
alter table public.notifications enable row level security;
alter table public.impact_ledger enable row level security;

-- Drop old policies if they exist
DROP POLICY IF EXISTS "demo_select_restaurants" ON public.restaurants;
DROP POLICY IF EXISTS "demo_write_restaurants" ON public.restaurants;
DROP POLICY IF EXISTS "demo_select_ngos" ON public.ngos;
DROP POLICY IF EXISTS "demo_write_ngos" ON public.ngos;
DROP POLICY IF EXISTS "demo_select_companies" ON public.companies;
DROP POLICY IF EXISTS "demo_write_companies" ON public.companies;
DROP POLICY IF EXISTS "demo_select_food_listings" ON public.food_listings;
DROP POLICY IF EXISTS "demo_write_food_listings" ON public.food_listings;
DROP POLICY IF EXISTS "demo_select_user_requests" ON public.user_requests;
DROP POLICY IF EXISTS "demo_write_user_requests" ON public.user_requests;
DROP POLICY IF EXISTS "demo_select_hotspots" ON public.hotspots;
DROP POLICY IF EXISTS "demo_write_hotspots" ON public.hotspots;
DROP POLICY IF EXISTS "demo_select_dispatch_jobs" ON public.dispatch_jobs;
DROP POLICY IF EXISTS "demo_write_dispatch_jobs" ON public.dispatch_jobs;
DROP POLICY IF EXISTS "demo_select_notifications" ON public.notifications;
DROP POLICY IF EXISTS "demo_write_notifications" ON public.notifications;
DROP POLICY IF EXISTS "demo_select_impact_ledger" ON public.impact_ledger;
DROP POLICY IF EXISTS "demo_write_impact_ledger" ON public.impact_ledger;

-- Public read/write policies for hackathon demo
CREATE POLICY "demo_select_restaurants" ON public.restaurants FOR SELECT USING (true);
CREATE POLICY "demo_write_restaurants" ON public.restaurants FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "demo_select_ngos" ON public.ngos FOR SELECT USING (true);
CREATE POLICY "demo_write_ngos" ON public.ngos FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "demo_select_companies" ON public.companies FOR SELECT USING (true);
CREATE POLICY "demo_write_companies" ON public.companies FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "demo_select_food_listings" ON public.food_listings FOR SELECT USING (true);
CREATE POLICY "demo_write_food_listings" ON public.food_listings FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "demo_select_user_requests" ON public.user_requests FOR SELECT USING (true);
CREATE POLICY "demo_write_user_requests" ON public.user_requests FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "demo_select_hotspots" ON public.hotspots FOR SELECT USING (true);
CREATE POLICY "demo_write_hotspots" ON public.hotspots FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "demo_select_dispatch_jobs" ON public.dispatch_jobs FOR SELECT USING (true);
CREATE POLICY "demo_write_dispatch_jobs" ON public.dispatch_jobs FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "demo_select_notifications" ON public.notifications FOR SELECT USING (true);
CREATE POLICY "demo_write_notifications" ON public.notifications FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "demo_select_impact_ledger" ON public.impact_ledger FOR SELECT USING (true);
CREATE POLICY "demo_write_impact_ledger" ON public.impact_ledger FOR ALL USING (true) WITH CHECK (true);
