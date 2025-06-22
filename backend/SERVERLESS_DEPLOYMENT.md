# Serverless Deployment Guide

This guide explains how to deploy the serverless-compatible version of the Baruch Study Rooms booking system.

## What Changed for Serverless

### ✅ Removed from Original
- Global in-memory state (`active_booking_attempts`)
- Background threading (`continuous_booking_worker`) 
- Long-running processes

### ✅ Added for Serverless
- **MongoDB-based monitoring**: Monitoring requests are stored in the database
- **One-shot check endpoints**: Check availability and book immediately  
- **External scheduler support**: Designed to work with cron jobs, AWS EventBridge, etc.

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Serverless     │    │    MongoDB      │
│   React App     │◄──►│   Flask API      │◄──►│   Database      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                ▲
                                │
                       ┌──────────────────┐
                       │  External        │
                       │  Scheduler       │
                       │  (Cron/Lambda)   │
                       └──────────────────┘
```

## New Endpoints

### Core Functionality (Same as Original)
- `GET /api/availability` - Get room availability
- `POST /api/book` - Book a room immediately
- All authentication endpoints

### New Monitoring Endpoints
- `POST /api/monitoring/create` - Create monitoring request (stored in DB)
- `GET /api/monitoring/<id>` - Get monitoring request status
- `POST /api/monitoring/<id>/check-and-book` - Check and attempt booking
- `POST /api/monitoring/<id>/stop` - Stop monitoring
- `GET /api/monitoring/list` - List user's monitoring requests
- `GET /api/monitoring/active` - List all active monitoring (for schedulers)

### One-Shot Alternative
- `POST /api/check-and-book-once` - Check availability once and book if available

## Deployment Options

### 1. Vercel (Easiest)

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy from backend directory
cd backend
vercel --prod
```

Create `vercel.json`:
```json
{
  "functions": {
    "serverless_main.py": {
      "runtime": "python3.9"
    }
  },
  "routes": [
    { "src": "/(.*)", "dest": "serverless_main.py" }
  ]
}
```

### 2. AWS Lambda

```bash
# Install dependencies
pip install -r requirements.txt -t .

# Create deployment package
zip -r deployment.zip .

# Upload to AWS Lambda
aws lambda create-function \
  --function-name baruch-studyrooms \
  --runtime python3.9 \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --handler serverless_main.handler \
  --zip-file fileb://deployment.zip
```

### 3. Google Cloud Functions

```bash
gcloud functions deploy baruch-studyrooms \
  --runtime python39 \
  --trigger-http \
  --entry-point handler \
  --source .
```

## Setting Up Monitoring with External Scheduler

### Option 1: AWS EventBridge + Lambda

Create a separate Lambda function that runs every 5 minutes:

```python
import requests
import json

def monitoring_handler(event, context):
    # Get active monitoring requests
    response = requests.get('https://your-api.vercel.app/api/monitoring/active')
    active_requests = response.json()['requests']
    
    for request_data in active_requests:
        request_id = request_data['request_id']
        
        # Check and attempt booking
        check_response = requests.post(
            f'https://your-api.vercel.app/api/monitoring/{request_id}/check-and-book'
        )
        
        result = check_response.json()
        if result.get('booked'):
            print(f"SUCCESS: Booked for request {request_id}")
        elif result.get('available') == False:
            print(f"No slots available for request {request_id}")
        
    return {'statusCode': 200, 'body': 'Monitoring check completed'}
```

### Option 2: Cron Job on Server

```bash
# Add to crontab (runs every 5 minutes)
*/5 * * * * curl -X POST https://your-api.vercel.app/api/monitoring/check-all
```

### Option 3: GitHub Actions (Free)

Create `.github/workflows/monitor.yml`:
```yaml
name: Room Monitoring
on:
  schedule:
    - cron: '*/5 * * * *'  # Every 5 minutes
  workflow_dispatch:

jobs:
  monitor:
    runs-on: ubuntu-latest
    steps:
      - name: Check Active Monitoring Requests
        run: |
          # Get active requests
          REQUESTS=$(curl -s "https://your-api.vercel.app/api/monitoring/active")
          echo "$REQUESTS" | jq -r '.requests[].request_id' | while read request_id; do
            echo "Checking request: $request_id"
            curl -X POST "https://your-api.vercel.app/api/monitoring/$request_id/check-and-book"
          done
```

## Frontend Integration

The frontend can now:

1. **Create monitoring requests** instead of background processes:
```javascript
const response = await fetch('/api/monitoring/create', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    date: '2025-06-24',
    startTime: '13:00',
    endTime: '14:00',
    firstName: 'John',
    lastName: 'Doe',
    email: 'john@baruchmail.cuny.edu'
  })
});
```

2. **Check monitoring status**:
```javascript
const status = await fetch(`/api/monitoring/${requestId}`);
```

3. **List user's monitoring requests**:
```javascript
const requests = await fetch('/api/monitoring/list');
```

## Benefits of This Approach

### ✅ Serverless Compatible
- No global state or background processes
- Each request is stateless
- Scales automatically

### ✅ Persistent Monitoring  
- Monitoring requests survive server restarts
- Historical tracking of attempts
- User can see all their monitoring requests

### ✅ Flexible Scheduling
- Use any external scheduler (cron, AWS EventBridge, GitHub Actions)
- Adjust monitoring frequency as needed
- Multiple monitoring strategies possible

### ✅ Cost Effective
- Only pay for actual API calls
- No always-running server costs
- Free tier options available

## Environment Variables

Set these in your serverless platform:

```bash
MONGO_URI=mongodb+srv://...
FLASK_SECRET_KEY=your-production-secret-key
```

## Database Collections

The system uses these MongoDB collections:

- `users` - User accounts and authentication
- `sessions` - User login sessions  
- `monitoring_requests` - Active and completed monitoring requests

## Monitoring Request Document Structure

```json
{
  "request_id": "2025-06-24_13:00-14:00_1719234567.123",
  "user_id": "user123",
  "email": "john@baruchmail.cuny.edu",
  "first_name": "John",
  "last_name": "Doe",
  "target_date": "2025-06-24",
  "start_time": "13:00",
  "end_time": "14:00",
  "room_preference": null,
  "status": "active",
  "created_at": "2025-06-22T10:00:00Z",
  "expires_at": "2025-06-25T00:00:00Z",
  "last_check": "2025-06-22T10:05:00Z",
  "check_count": 3,
  "success_details": null,
  "error_message": null
}
```

## Status Values

- `active` - Monitoring is running
- `completed` - Successfully booked
- `stopped` - Manually stopped by user
- `expired` - Monitoring period ended
- `error` - Error occurred during booking attempt
