#!/usr/bin/env python3
"""
Simple scheduler for monitoring requests.
This script should be run periodically (e.g., every 5 minutes) via cron or similar.

Usage:
    python scheduler.py

Or set up a cron job:
    */5 * * * * /path/to/python /path/to/scheduler.py

Environment Variables:
    BACKEND_URL - Base URL of the backend API (default: http://localhost:5001)
"""

import requests
import os
import time
from datetime import datetime

# Configuration
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:5001')
CHECK_ENDPOINT = f"{BACKEND_URL}/api/monitoring/check-all"

def check_monitoring_requests():
    """
    Check all active monitoring requests and attempt bookings.
    """
    try:
        print(f"[{datetime.now()}] Checking monitoring requests...")
        
        response = requests.post(CHECK_ENDPOINT, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success: {result.get('message', 'Check completed')}")
            print(f"   Checked: {result.get('checked', 0)} requests")
            print(f"   Booked: {result.get('booked', 0)} slots")
            
            if result.get('results'):
                for check_result in result['results']:
                    status = "✅" if check_result.get('booked') else "⏳"
                    print(f"   {status} {check_result.get('request_id', 'Unknown')}: {check_result.get('message', 'No message')}")
        else:
            print(f"❌ Error: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ Error: Request timeout")
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to backend")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def main():
    """
    Main function - can be called directly or in a loop for continuous monitoring.
    """
    print("🔍 Baruch Study Rooms - Monitoring Scheduler")
    print(f"Backend URL: {BACKEND_URL}")
    print("-" * 50)
    
    # For one-time execution (suitable for cron)
    check_monitoring_requests()
    
    # Uncomment below for continuous monitoring (not recommended for production)
    # while True:
    #     check_monitoring_requests()
    #     print(f"Sleeping for 5 minutes...")
    #     time.sleep(300)  # 5 minutes

if __name__ == "__main__":
    main()
