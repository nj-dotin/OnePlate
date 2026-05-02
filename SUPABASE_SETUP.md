# Supabase Backend Setup

## Quick Start

### 1. Get your Supabase API Key

1. Go to your Supabase project: https://app.supabase.com
2. Click on **Settings** → **API**
3. Copy the **`anon` / `public` key** (NOT the service_role key)
4. Copy the **Project URL** (should start with `https://`)

### 2. Create `.env` file in project root

Create a new file named `.env` in the `OnePlate` folder with:

```
SUPABASE_URL=https://tubptfkubqjzuwgcezqi.supabase.co
SUPABASE_KEY=YOUR_ANON_KEY_HERE
```

**Replace `YOUR_ANON_KEY_HERE`** with the key you copied from step 1.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
streamlit run app/streamlit_app.py
```

## Multi-Device Sync Test

Once the app is running with Supabase credentials:

1. **Laptop A**: Open `http://localhost:8501`
2. **Laptop B**: Open the same URL (or deploy to a server)
3. **Laptop A**: Create a food listing or request
4. **Laptop B**: Refresh the page — you should see the new data appear

## How it works

- The app tries to connect to Supabase when it starts
- If credentials are valid, it loads all data from the cloud
- Every action (add listing, create request, verify OTP) syncs to Supabase
- If Supabase is unavailable, the app falls back to in-memory storage (local only)

## Troubleshooting

### "Could not load from Supabase" error
- Check your `.env` file has `SUPABASE_URL` and `SUPABASE_KEY`
- Verify the API key is the **anon key**, not service_role
- Make sure the project is not paused (check Supabase dashboard)

### Changes not appearing on other laptop
- Check both laptops are using the same Supabase project
- Refresh the page on the other laptop (Streamlit doesn't auto-refresh)
- Check browser console for errors (F12)

### "ModuleNotFoundError: No module named 'supabase'"
- Run `pip install supabase python-dotenv`
- Verify `requirements.txt` includes both packages

## Database Schema

The following tables are automatically created in Supabase and used by the app:

- `restaurants` - Food sources
- `ngos` - Delivery partners
- `companies` - Sponsors
- `food_listings` - Surplus food
- `user_requests` - Direct demand
- `hotspots` - Vision-detected demand zones
- `dispatch_jobs` - Routing assignments
- `impact_ledger` - Credits and impact tracking

All data is persistent and shared across devices.
