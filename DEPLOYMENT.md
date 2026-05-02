# OnePlate Deployment Guide

OnePlate is now ready for online deployment with real-time data, APIs, and multi-system integration.

## Quick Start Options

### Option 1: Streamlit Cloud (Easiest)

1. **Push to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial OnePlate deployment"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/oneplate.git
   git push -u origin main
   ```

2. **Deploy to Streamlit Cloud:**
   - Go to https://share.streamlit.io
   - Click "New app"
   - Select your GitHub repo
   - Select branch: main
   - Select file path: app/streamlit_app.py
   - Click Deploy

3. **Configure secrets in Streamlit Cloud:**
   - Go to your app settings → Secrets
   - Add:
     ```
     SUPABASE_URL = "https://tubptfkubqjzuwgcezqi.supabase.co"
     SUPABASE_KEY = "your_anon_key"
     ```

✅ **Your Streamlit dashboard will be live at:** `https://yourname-oneplate.streamlit.app`


### Option 2: Railway (Best for Full Stack)

1. **Connect Railway to your GitHub:**
   - Go to https://railway.app
   - Click "New Project" → "Deploy from GitHub"
   - Authorize and select your oneplate repo

2. **Add environment variables:**
   - Go to Variables tab
   - Add all variables from `.env.production`

3. **Configure services:**
   - Railway will auto-detect from Procfile
   - Streamlit will run on port 8501
   - FastAPI will run on port 8000

✅ **Your services will be live at:**
- Dashboard: `https://oneplate-abc123.railway.app:8501`
- API: `https://oneplate-abc123.railway.app:8000`


### Option 3: Docker + Heroku

1. **Build Docker image locally:**
   ```bash
   docker build -t oneplate:latest .
   ```

2. **Test locally:**
   ```bash
   docker run -p 8501:8501 -p 8000:8000 \
     -e SUPABASE_URL="your_url" \
     -e SUPABASE_KEY="your_key" \
     oneplate:latest
   ```

3. **Deploy to Heroku:**
   ```bash
   # Install Heroku CLI and login
   heroku login
   heroku create oneplate-app
   heroku container:push web -a oneplate-app
   heroku container:release web -a oneplate-app
   ```

✅ **Your app will be live at:** `https://oneplate-app.herokuapp.com`


### Option 4: AWS Deployment

#### Using Elastic Beanstalk:
```bash
# Install EB CLI
pip install awsebcli

# Initialize
eb init -p python-3.11 oneplate --region ap-south-1

# Create environment
eb create oneplate-prod

# Deploy
eb deploy
```

#### Using ECS + Fargate:
1. Push Docker image to ECR
2. Create ECS task definition
3. Create ECS service with load balancer
4. Configure CloudWatch for monitoring

✅ **Your app will be live at:** `https://oneplate-alb.amazonaws.com`


## Real-Time Data Sync

### Feature: WebSocket Live Updates
- **Endpoint:** `wss://your-domain/ws/live`
- **Connection:** Automatically connects clients to receive:
  - Food listing updates
  - Dispatch job creation
  - Pickup/delivery verification
  - Route optimization updates
  - NGO notifications

### Python Client Example:
```python
import asyncio
import websockets
import json

async def listen_to_updates():
    uri = "wss://your-domain/ws/live"
    async with websockets.connect(uri) as websocket:
        print("Connected to OnePlate live updates")
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            print(f"Event: {data['event']}")
            print(f"Data: {data['data']}")

asyncio.run(listen_to_updates())
```


## API Integration

### REST API Endpoints

#### 1. Create Food Listing
```bash
POST /api/v1/food-listings
Content-Type: application/json

{
  "restaurant_id": "r1",
  "food_type": "Rice",
  "quantity": 50,
  "cooked_minutes_ago": 30
}
```

#### 2. Create User Request
```bash
POST /api/v1/requests
{
  "requester_name": "Community Center",
  "quantity": 25,
  "latitude": 12.9712,
  "longitude": 77.5941
}
```

#### 3. Create Dispatch Job (Auto-matching)
```bash
POST /api/v1/dispatch-jobs
```

#### 4. Get Optimized Routes
```bash
GET /api/v1/routes/optimization
```

#### 5. Verify Pickup
```bash
POST /api/v1/dispatch-jobs/{job_id}/verify-pickup
{
  "otp_code": "123456"
}
```

#### 6. Verify Delivery
```bash
POST /api/v1/dispatch-jobs/{job_id}/verify-delivery
{
  "otp_code": "789012"
}
```

### JavaScript/Node.js Integration:
```javascript
const API_BASE = 'https://your-domain/api/v1';

// Create food listing
async function createFoodListing() {
  const response = await fetch(`${API_BASE}/food-listings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      restaurant_id: 'r1',
      food_type: 'Rice',
      quantity: 50,
      cooked_minutes_ago: 30
    })
  });
  return response.json();
}

// Get optimized routes
async function getRoutes() {
  const response = await fetch(`${API_BASE}/routes/optimization`);
  return response.json();
}

// Listen to real-time updates
function listenToUpdates() {
  const ws = new WebSocket('wss://your-domain/ws/live');
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Update:', data.event, data.data);
  };
}
```


## Third-Party System Integration

### 1. Restaurant POS System
- **Integrate with:** Your existing restaurant management system
- **Action:** When chef marks food as "ready for pickup", call:
  ```bash
  POST https://your-domain/api/v1/food-listings
  ```

### 2. Mobile App (User-facing)
- **Integrate with:** Your mobile app for food requests
- **Action:** When user requests food, call:
  ```bash
  POST https://your-domain/api/v1/requests
  ```
- **Listen to:** WebSocket updates for dispatch status

### 3. NGO Dispatch System
- **Get assignments via:** `GET /api/v1/dispatch-jobs`
- **Verify pickup:** `POST /api/v1/dispatch-jobs/{id}/verify-pickup`
- **Verify delivery:** `POST /api/v1/dispatch-jobs/{id}/verify-delivery`

### 4. Analytics Dashboard
- **Get impact metrics:** `GET /api/v1/impact-ledger`
- **Get system status:** `GET /api/v1/status`
- **Subscribe to:** WebSocket for real-time changes


## Monitoring & Health Checks

### Health Check Endpoint
```bash
GET https://your-domain/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2026-05-02T04:15:00Z",
  "version": "1.0.0"
}
```

### System Status
```bash
GET https://your-domain/api/v1/status
```

Response includes:
- Number of restaurants, NGOs, listings, requests
- Active dispatch jobs
- System operational status


## Running Tests Locally

Before deploying, run the comprehensive test suite:

```bash
# Install test dependencies
pip install -r requirements.txt
pip install httpx websockets

# Run all tests
python test_suite.py
```

Expected output:
```
============================================================
ONEPLATE COMPREHENSIVE TEST SUITE
============================================================

Basic Functionality:
✓ Data Store Initialization
✓ Food Listing Creation
✓ User Request Creation
✓ Dispatch Creation

Notification System:
✓ NGO Notification System

Routing & Optimization:
✓ Route Optimization

... (more tests)

============================================================
TEST SUMMARY: 11/11 passed
============================================================
```


## Production Checklist

Before going live:

- [ ] Set all environment variables in `.env.production`
- [ ] Update Supabase URLs and keys
- [ ] Run test suite locally
- [ ] Test with real data in Supabase
- [ ] Enable HTTPS (auto-configured by most platforms)
- [ ] Set up monitoring/alerts
- [ ] Configure backup strategy
- [ ] Document API endpoints for partners
- [ ] Set up logging and error tracking
- [ ] Test real-time updates with multiple clients
- [ ] Load test the system
- [ ] Prepare runbook for incidents


## Support & Documentation

- **API Docs:** `https://your-domain/docs` (auto-generated by FastAPI)
- **Dashboard UI:** Available at main domain with all features
- **Webhooks:** Register webhook URLs to receive event notifications
- **WebSocket:** Real-time live dispatch tracking


## Troubleshooting

### Dashboard not loading:
- Check Streamlit server logs
- Verify environment variables
- Clear browser cache

### API returning 503:
- Store not initialized - check startup logs
- Supabase connection failed - verify credentials

### Real-time updates not working:
- Check WebSocket connection in browser DevTools
- Verify CORS configuration
- Check firewall/proxy settings

### Routes not optimizing:
- Ensure dispatch jobs exist
- Check target locations are valid
- Verify restaurant/NGO data is loaded


## Next Steps

1. Choose deployment platform above
2. Update environment variables
3. Run test suite
4. Deploy!
5. Monitor system performance
6. Integrate with your systems

Questions? Check the API documentation or create an issue on GitHub.
