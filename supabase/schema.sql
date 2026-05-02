-- PHRS MVP Schema (Supabase/Postgres)

create table if not exists restaurants (
  id text primary key,
  name text not null,
  location_lat double precision not null,
  location_lng double precision not null,
  impact_score integer default 0,
  created_at timestamptz default now()
);

create table if not exists ngos (
  id text primary key,
  name text not null,
  location_lat double precision not null,
  location_lng double precision not null,
  reliability_score integer default 0,
  created_at timestamptz default now()
);

create table if not exists companies (
  id text primary key,
  name text not null,
  sponsor_balance numeric default 0,
  branding_name text,
  created_at timestamptz default now()
);

create table if not exists food_listings (
  id text primary key,
  restaurant_id text references restaurants(id),
  restaurant_name text,
  food_type text not null,
  quantity_total integer not null,
  quantity_available integer not null,
  time_cooked timestamptz not null,
  remaining_minutes integer,
  safety_score integer,
  urgency text,
  lat double precision,
  lng double precision,
  status text default 'available',
  created_at timestamptz default now()
);

create table if not exists user_requests (
  id text primary key,
  requester_name text not null,
  quantity_needed integer not null,
  lat double precision not null,
  lng double precision not null,
  status text default 'open',
  created_at timestamptz default now()
);

create table if not exists hotspots (
  id text primary key,
  zone text not null,
  people_count integer default 0,
  persistence_minutes integer default 0,
  need_score numeric default 0,
  priority text,
  lat double precision not null,
  lng double precision not null,
  time_detected timestamptz not null,
  created_at timestamptz default now()
);

create table if not exists dispatch_jobs (
  id text primary key,
  food_id text references food_listings(id),
  assigned_ngo_id text references ngos(id),
  ngo_name text,
  target_kind text not null,
  target_id text not null,
  quantity integer not null,
  suggestion jsonb,
  pickup_otp text,
  delivery_otp text,
  pickup_verified boolean default false,
  delivery_verified boolean default false,
  status text default 'created',
  created_at timestamptz default now()
);

create table if not exists notifications (
  id text primary key,
  recipient_type text not null,
  recipient_id text not null,
  recipient_name text not null,
  title text not null,
  message text not null,
  source_kind text not null,
  source_id text not null,
  source_label text not null,
  is_read boolean default false,
  created_at timestamptz default now()
);

create table if not exists otp_verifications (
  id bigserial primary key,
  dispatch_job_id text references dispatch_jobs(id),
  handover_otp text,
  delivery_otp text,
  handover_status boolean default false,
  delivery_status boolean default false,
  verified_at timestamptz,
  created_at timestamptz default now()
);

create table if not exists impact_ledger (
  id text primary key,
  actor_type text not null,
  actor_id text not null,
  meals_saved integer default 0,
  credits_added integer default 0,
  event_ref text,
  created_at timestamptz default now()
);
