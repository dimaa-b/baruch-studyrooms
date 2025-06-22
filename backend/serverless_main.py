# Serverless-compatible version of main.py
from flask import Flask, request, jsonify, render_template, make_response
from flask_cors import CORS
import requests
import json
import re
from datetime import datetime, time
from typing import Dict, Any
from auth import AuthManager, MonitoringManager, require_auth, optional_auth
import os

# --- Flask App Setup ---
app = Flask(__name__)
CORS(app, supports_credentials=True)

# --- Authentication Setup ---
MONGO_URI = os.environ.get("MONGODB_URI")
auth_manager = AuthManager(MONGO_URI)
monitoring_manager = MonitoringManager(MONGO_URI)
app.secret_key = 'your-secret-key-change-in-production' 

# --- Constants ---
BASE_URL = "https://libraryrooms.baruch.cuny.edu"
LID = 16857
GID = 35704
USER_STATUS_ANSWER = "Current student at Baruch or CUNY SPS"

# --- Authentication Endpoints (unchanged) ---
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    required_fields = ['email', 'username', 'password', 'firstName', 'lastName']
    for field in required_fields:
        if field not in data or not data[field].strip():
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    result = auth_manager.register_user(
        email=data['email'].strip().lower(),
        username=data['username'].strip(),
        password=data['password'],
        first_name=data['firstName'].strip(),
        last_name=data['lastName'].strip()
    )
    
    if result['success']:
        return jsonify(result), 201
    else:
        return jsonify(result), 400

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    if not data.get('email') or not data.get('password'):
        return jsonify({"error": "Email/username and password are required"}), 400
    
    result = auth_manager.login_user(
        email_or_username=data['email'].strip(),
        password=data['password']
    )
    
    if result['success']:
        response = make_response(jsonify({
            "success": True,
            "message": result['message'],
            "user": result['user'],
            "expires_at": result['expires_at']
        }))
        
        response.set_cookie(
            'session_token',
            result['token'],
            max_age=7*24*60*60,
            httponly=True,
            secure=False,
            samesite='Lax'
        )
        return response, 200
    else:
        return jsonify(result), 401

@app.route('/api/auth/logout', methods=['POST'])
@optional_auth(auth_manager)
def logout():
    session_token = request.cookies.get('session_token')
    if session_token:
        auth_manager.logout_user(session_token)
    
    response = make_response(jsonify({"success": True, "message": "Logged out successfully"}))
    response.set_cookie('session_token', '', expires=0)
    return response

@app.route('/api/auth/me', methods=['GET'])
@require_auth(auth_manager)
def get_current_user():
    return jsonify({
        "authenticated": True,
        "user": {
            "id": request.current_user['id'],
            "email": request.current_user['email'],
            "username": request.current_user['username'],
            "firstName": request.current_user['first_name'],
            "lastName": request.current_user['last_name']
        }
    })

@app.route('/api/auth/check', methods=['GET'])
@optional_auth(auth_manager)
def check_auth():
    if request.current_user:
        return jsonify({
            "authenticated": True,
            "user": {
                "id": request.current_user['id'],
                "email": request.current_user['email'],
                "username": request.current_user['username'],
                "firstName": request.current_user['first_name'],
                "lastName": request.current_user['last_name']
            }
        })
    else:
        return jsonify({"authenticated": False})

# --- Room Booking Endpoints ---
@app.route('/api/availability', methods=['GET'])
def get_availability():
    target_date_str = request.args.get('date')
    if not target_date_str:
        return jsonify({"error": "Date parameter is required"}), 400

    print(f"Fetching availability for {target_date_str}...")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/spaces?lid={LID}&gid={GID}"
    })

    url = f"{BASE_URL}/spaces/availability/grid"
    payload = {
        "lid": LID, "gid": GID, "eid": -1, "seat": 0, "seatId": 0, "zone": 0,
        "start": target_date_str, "end": target_date_str,
        "pageIndex": 0, "pageSize": 18
    }

    try:
        response = session.post(url, data=payload)
        response.raise_for_status()
        
        slots_by_room = {}
        for slot in response.json().get("slots", []):
            room_id = slot['itemId']
            if room_id not in slots_by_room:
                slots_by_room[room_id] = []
            
            slot['displayTime'] = datetime.strptime(slot['start'], "%Y-%m-%d %H:%M:%S").strftime("%-I:%M %p")
            slots_by_room[room_id].append(slot)

        return jsonify(slots_by_room)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/book', methods=['POST'])
@optional_auth(auth_manager)
def book_room():
    data = request.json
    print(f"Received booking request: {data}")

    if request.current_user:
        if not data.get('firstName'):
            data['firstName'] = request.current_user['first_name']
        if not data.get('lastName'):
            data['lastName'] = request.current_user['last_name']
        if not data.get('email'):
            data['email'] = request.current_user['email']

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/spaces?lid={LID}&gid={GID}"
    })
    
    # Get the specific slot checksum
    availability_url = f"{BASE_URL}/spaces/availability/grid"
    availability_payload = {"lid": LID, "gid": GID, "start": data['date'], "end": data['date']}
    availability_res = session.post(availability_url, data=availability_payload)
    target_slot = None
    for slot in availability_res.json().get("slots", []):
        if str(slot['itemId']) == str(data['roomId']) and slot['start'] == f"{data['date']} {data['startTime']}":
            target_slot = slot
            break
    
    if not target_slot:
        return jsonify({"success": False, "message": "Slot is no longer available."}), 409

    # Add to cart
    add_url = f"{BASE_URL}/spaces/availability/booking/add"
    add_payload = {
        "add[eid]": target_slot['itemId'], "add[gid]": GID, "add[lid]": LID,
        "add[start]": target_slot['start'].split(' ')[0] + ' ' + target_slot['start'].split(' ')[1][:5],
        "add[checksum]": target_slot['checksum'],
        "lid": LID, "gid": GID, "start": data['date']
    }
    add_res = session.post(add_url, data=add_payload)
    pending_booking = add_res.json().get("bookings", [])[0]

    # Get session ID
    times_url = f"{BASE_URL}/ajax/space/times"
    times_payload = {
        f"bookings[0][{key}]": val for key, val in pending_booking.items()
    }
    times_payload["method"] = 11
    times_res = session.post(times_url, data=times_payload)
    html_content = times_res.json().get("html", "")
    match = re.search(r'id="session" name="session" value="(\d+)"', html_content)
    session_id = match.group(1)

    # Submit final booking
    book_url = f"{BASE_URL}/ajax/space/book"
    pending_booking['start'] = pending_booking['start'].replace(" ", "T")[:16]
    pending_booking['end'] = pending_booking['end'].replace(" ", "T")[:16]

    final_payload = {
        "session": session_id,
        "fname": data['firstName'],
        "lname": data['lastName'],
        "email": data['email'],
        "q25689": USER_STATUS_ANSWER,
        "bookings": json.dumps([pending_booking]),
        "returnUrl": f"/spaces?lid={LID}&gid={GID}", "pickupHolds": "", "method": 11,
    }
    final_headers = session.headers.copy()
    if 'Content-Type' in final_headers:
        del final_headers['Content-Type']
    
    final_res = session.post(book_url, data=final_payload, headers=final_headers)
    
    if final_res.status_code == 200 and "bookId" in final_res.json():
        return jsonify({"success": True, "message": "Booking is pending! Check your email."})
    else:
        return jsonify({"success": False, "message": "Final booking step failed."}), 500

@app.route('/api/check-and-book-once', methods=['POST'])
@optional_auth(auth_manager)
def check_and_book_once():
    """
    Serverless-friendly version: Check availability once and book if available.
    No continuous monitoring - frontend can call this repeatedly or use external scheduler.
    """
    data = request.json
    
    if request.current_user:
        if not data.get('firstName'):
            data['firstName'] = request.current_user['first_name']
        if not data.get('lastName'):
            data['lastName'] = request.current_user['last_name']
        if not data.get('email'):
            data['email'] = request.current_user['email']
    
    required_fields = ['date', 'startTime', 'endTime', 'firstName', 'lastName', 'email']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    target_date = data['date']
    start_time = data['startTime']
    end_time = data['endTime']
    
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/spaces?lid={LID}&gid={GID}"
        })
        
        # Check availability
        availability_url = f"{BASE_URL}/spaces/availability/grid"
        availability_payload = {
            "lid": LID, "gid": GID, "eid": -1, "seat": 0, "seatId": 0, "zone": 0,
            "start": target_date, "end": target_date,
            "pageIndex": 0, "pageSize": 18
        }
        
        response = session.post(availability_url, data=availability_payload)
        response.raise_for_status()
        
        # Look for available slots in the target timeframe
        slots = response.json().get("slots", [])
        target_slots = []
        
        for slot in slots:
            slot_start = datetime.strptime(slot['start'], "%Y-%m-%d %H:%M:%S")
            slot_time = slot_start.strftime("%H:%M")
            
            if start_time <= slot_time < end_time:
                target_slots.append(slot)
        
        if not target_slots:
            return jsonify({
                "success": False, 
                "available": False,
                "message": f"No available slots found in timeframe {start_time}-{end_time}"
            })
        
        # Found available slot! Try to book it
        slot_to_book = target_slots[0]
        
        # Attempt booking (same logic as regular booking)
        try:
            # Add to cart
            add_url = f"{BASE_URL}/spaces/availability/booking/add"
            add_payload = {
                "add[eid]": slot_to_book['itemId'], 
                "add[gid]": GID, 
                "add[lid]": LID,
                "add[start]": slot_to_book['start'].split(' ')[0] + ' ' + slot_to_book['start'].split(' ')[1][:5],
                "add[checksum]": slot_to_book['checksum'],
                "lid": LID, 
                "gid": GID, 
                "start": target_date
            }
            add_res = session.post(add_url, data=add_payload)
            pending_booking = add_res.json().get("bookings", [])[0]

            # Get session ID
            times_url = f"{BASE_URL}/ajax/space/times"
            times_payload = {
                f"bookings[0][{key}]": val for key, val in pending_booking.items()
            }
            times_payload["method"] = 11
            times_res = session.post(times_url, data=times_payload)
            html_content = times_res.json().get("html", "")
            match = re.search(r'id="session" name="session" value="(\d+)"', html_content)
            session_id = match.group(1)

            # Submit final booking
            book_url = f"{BASE_URL}/ajax/space/book"
            pending_booking['start'] = pending_booking['start'].replace(" ", "T")[:16]
            pending_booking['end'] = pending_booking['end'].replace(" ", "T")[:16]

            final_payload = {
                "session": session_id,
                "fname": data['firstName'],
                "lname": data['lastName'],
                "email": data['email'],
                "q25689": USER_STATUS_ANSWER,
                "bookings": json.dumps([pending_booking]),
                "returnUrl": f"/spaces?lid={LID}&gid={GID}", 
                "pickupHolds": "", "method": 11,
            }
            final_headers = session.headers.copy()
            if 'Content-Type' in final_headers:
                del final_headers['Content-Type']
            
            final_res = session.post(book_url, data=final_payload, headers=final_headers)
            
            if final_res.status_code == 200 and "bookId" in final_res.json():
                return jsonify({"success": True, "message": "Booking is pending! Check your email."})
            else:
                return jsonify({"success": False, "message": "Final booking step failed."}), 500

        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Monitoring Endpoints (Serverless-friendly with MongoDB storage) ---

@app.route('/api/monitoring/create', methods=['POST'])
@optional_auth(auth_manager)
def create_monitoring_request():
    """
    Create a new monitoring request stored in MongoDB.
    This replaces the old background monitoring with database-stored requests.
    """
    data = request.json
    
    # If user is authenticated, use their info and ID
    user_id = None
    if request.current_user:
        user_id = request.current_user['id']
        if not data.get('firstName'):
            data['firstName'] = request.current_user['first_name']
        if not data.get('lastName'):
            data['lastName'] = request.current_user['last_name']
        if not data.get('email'):
            data['email'] = request.current_user['email']
    
    # Validate required fields
    required_fields = ['date', 'startTime', 'endTime', 'firstName', 'lastName', 'email']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    # Create monitoring request in database
    result = monitoring_manager.create_monitoring_request(
        user_id=user_id,
        email=data['email'],
        first_name=data['firstName'],
        last_name=data['lastName'],
        target_date=data['date'],
        start_time=data['startTime'],
        end_time=data['endTime'],
        room_preference=data.get('roomPreference')
    )
    
    if result['success']:
        return jsonify({
            "success": True,
            "request_id": result['request_id'],
            "message": f"Monitoring request created for {data['date']} {data['startTime']}-{data['endTime']}. Use external scheduler to check periodically."
        }), 201
    else:
        return jsonify(result), 500


@app.route('/api/monitoring/<request_id>', methods=['GET'])
def get_monitoring_request(request_id):
    """Get details of a specific monitoring request"""
    request_doc = monitoring_manager.get_monitoring_request(request_id)
    
    if not request_doc:
        return jsonify({"error": "Monitoring request not found"}), 404
    
    return jsonify(request_doc)


@app.route('/api/monitoring/<request_id>/check-and-book', methods=['POST'])
def check_and_book_for_request(request_id):
    """
    Check availability and attempt booking for a specific monitoring request.
    This endpoint is designed to be called by external schedulers (cron, etc.)
    """
    request_doc = monitoring_manager.get_monitoring_request(request_id)
    
    if not request_doc:
        return jsonify({"error": "Monitoring request not found"}), 404
    
    if request_doc['status'] != 'active':
        return jsonify({
            "error": f"Monitoring request is not active (status: {request_doc['status']})"
        }), 400
    
    # Prepare booking data from stored request
    booking_data = {
        'date': request_doc['target_date'],
        'startTime': request_doc['start_time'],
        'endTime': request_doc['end_time'],
        'firstName': request_doc['first_name'],
        'lastName': request_doc['last_name'],
        'email': request_doc['email']
    }
    
    try:
        # Use the same logic as check_and_book_once
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/spaces?lid={LID}&gid={GID}"
        })
        
        # Check availability
        availability_url = f"{BASE_URL}/spaces/availability/grid"
        availability_payload = {
            "lid": LID, "gid": GID, "eid": -1, "seat": 0, "seatId": 0, "zone": 0,
            "start": booking_data['date'], "end": booking_data['date'],
            "pageIndex": 0, "pageSize": 18
        }
        
        response = session.post(availability_url, data=availability_payload)
        response.raise_for_status()
        
        # Look for available slots in the target timeframe
        slots = response.json().get("slots", [])
        target_slots = []
        
        for slot in slots:
            slot_start = datetime.strptime(slot['start'], "%Y-%m-%d %H:%M:%S")
            slot_time = slot_start.strftime("%H:%M")
            
            # Apply room preference filter if specified
            if request_doc.get('room_preference') and str(slot['itemId']) != str(request_doc['room_preference']):
                continue
            
            if booking_data['startTime'] <= slot_time < booking_data['endTime']:
                target_slots.append(slot)
        
        # Update check count
        monitoring_manager.update_monitoring_status(request_id, 'active')
        
        if not target_slots:
            return jsonify({
                "success": False,
                "available": False,
                "message": f"No available slots found in timeframe {booking_data['startTime']}-{booking_data['endTime']}",
                "check_count": request_doc.get('check_count', 0) + 1
            })
        
        # Found available slot! Try to book it
        slot_to_book = target_slots[0]
        
        try:
            # Booking logic (same as in check_and_book_once)
            add_url = f"{BASE_URL}/spaces/availability/booking/add"
            add_payload = {
                "add[eid]": slot_to_book['itemId'], 
                "add[gid]": GID, 
                "add[lid]": LID,
                "add[start]": slot_to_book['start'].split(' ')[0] + ' ' + slot_to_book['start'].split(' ')[1][:5],
                "add[checksum]": slot_to_book['checksum'],
                "lid": LID, 
                "gid": GID, 
                "start": booking_data['date']
            }
            add_res = session.post(add_url, data=add_payload)
            pending_booking = add_res.json().get("bookings", [])[0]

            # Get session ID
            times_url = f"{BASE_URL}/ajax/space/times"
            times_payload = {
                f"bookings[0][{key}]": val for key, val in pending_booking.items()
            }
            times_payload["method"] = 11
            times_res = session.post(times_url, data=times_payload)
            html_content = times_res.json().get("html", "")
            match = re.search(r'id="session" name="session" value="(\d+)"', html_content)
            session_id = match.group(1)

            # Submit final booking
            book_url = f"{BASE_URL}/ajax/space/book"
            pending_booking['start'] = pending_booking['start'].replace(" ", "T")[:16]
            pending_booking['end'] = pending_booking['end'].replace(" ", "T")[:16]

            final_payload = {
                "session": session_id,
                "fname": booking_data['firstName'],
                "lname": booking_data['lastName'],
                "email": booking_data['email'],
                "q25689": USER_STATUS_ANSWER,
                "bookings": json.dumps([pending_booking]),
                "returnUrl": f"/spaces?lid={LID}&gid={GID}", 
                "pickupHolds": "", 
                "method": 11,
            }
            final_headers = session.headers.copy()
            if 'Content-Type' in final_headers:
                del final_headers['Content-Type']
            
            final_res = session.post(book_url, data=final_payload, headers=final_headers)
            
            if final_res.status_code == 200 and "bookId" in final_res.json():
                # Success! Update monitoring request to completed
                success_details = {
                    "slot": slot_to_book,
                    "booking_id": final_res.json().get("bookId"),
                    "booked_at": datetime.utcnow().isoformat()
                }
                monitoring_manager.update_monitoring_status(
                    request_id, 
                    'completed', 
                    success_details=success_details
                )
                
                return jsonify({
                    "success": True,
                    "available": True,
                    "booked": True,
                    "message": f"Successfully booked Room {slot_to_book['itemId']} at {slot_to_book['start']}!",
                    "slot": slot_to_book,
                    "booking_id": final_res.json().get("bookId")
                })
            else:
                error_msg = f"Found available slot but booking failed for Room {slot_to_book['itemId']}"
                monitoring_manager.update_monitoring_status(
                    request_id, 
                    'error', 
                    error_message=error_msg
                )
                return jsonify({
                    "success": False,
                    "available": True,
                    "booked": False,
                    "message": error_msg,
                    "slot": slot_to_book
                })
                
        except Exception as booking_error:
            error_msg = f"Booking error: {str(booking_error)}"
            monitoring_manager.update_monitoring_status(
                request_id, 
                'error', 
                error_message=error_msg
            )
            return jsonify({
                "success": False,
                "available": True,
                "booked": False,
                "message": error_msg,
                "slot": slot_to_book
            })
            
    except Exception as e:
        error_msg = f"Error checking availability: {str(e)}"
        monitoring_manager.update_monitoring_status(
            request_id, 
            'error', 
            error_message=error_msg
        )
        return jsonify({"error": error_msg}), 500


@app.route('/api/monitoring/<request_id>/stop', methods=['POST'])
@optional_auth(auth_manager)
def stop_monitoring_request(request_id):
    """Stop a monitoring request"""
    user_id = request.current_user['id'] if request.current_user else None
    
    success = monitoring_manager.stop_monitoring_request(request_id, user_id)
    
    if success:
        return jsonify({"success": True, "message": "Monitoring request stopped"})
    else:
        return jsonify({"error": "Failed to stop monitoring request or request not found"}), 400


@app.route('/api/monitoring/list', methods=['GET'])
@optional_auth(auth_manager)
def list_monitoring_requests():
    """List monitoring requests (user's own if authenticated, or all if admin)"""
    if request.current_user:
        # Return user's own requests
        requests = monitoring_manager.get_user_monitoring_requests(request.current_user['id'])
        return jsonify({"requests": requests})
    else:
        # For unauthenticated requests, return active requests without user details
        requests = monitoring_manager.get_active_monitoring_requests()
        # Remove sensitive user information
        sanitized_requests = []
        for req in requests:
            sanitized_req = {
                "request_id": req["request_id"],
                "target_date": req["target_date"],
                "start_time": req["start_time"],
                "end_time": req["end_time"],
                "status": req["status"],
                "created_at": req["created_at"],
                "check_count": req.get("check_count", 0)
            }
            sanitized_requests.append(sanitized_req)
        return jsonify({"requests": sanitized_requests})


@app.route('/api/monitoring/active', methods=['GET'])
def get_active_monitoring_requests():
    """Get all active monitoring requests (for external schedulers)"""
    requests = monitoring_manager.get_active_monitoring_requests()
    return jsonify({"requests": requests})

@app.route('/api/monitoring/check-all', methods=['POST'])
def check_all_monitoring_requests():
    """
    Check all active monitoring requests and attempt bookings.
    This endpoint is designed to be called by external schedulers.
    """
    active_requests = monitoring_manager.get_active_monitoring_requests()
    
    if not active_requests:
        return jsonify({
            "success": True,
            "message": "No active monitoring requests to check",
            "checked": 0,
            "results": []
        })
    
    results = []
    checked_count = 0
    booked_count = 0
    
    for request_doc in active_requests:
        request_id = request_doc['request_id']
        checked_count += 1
        
        try:
            # Prepare booking data from stored request
            booking_data = {
                'date': request_doc['target_date'],
                'startTime': request_doc['start_time'],
                'endTime': request_doc['end_time'],
                'firstName': request_doc['first_name'],
                'lastName': request_doc['last_name'],
                'email': request_doc['email']
            }
            
            # Use the same availability checking logic
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": BASE_URL,
                "Referer": f"{BASE_URL}/spaces?lid={LID}&gid={GID}"
            })
            
            # Check availability
            availability_url = f"{BASE_URL}/spaces/availability/grid"
            availability_payload = {
                "lid": LID, "gid": GID, "eid": -1, "seat": 0, "seatId": 0, "zone": 0,
                "start": booking_data['date'], "end": booking_data['date'],
                "pageIndex": 0, "pageSize": 18
            }
            
            response = session.post(availability_url, data=availability_payload)
            response.raise_for_status()
            
            # Look for available slots in the target timeframe
            slots = response.json().get("slots", [])
            target_slots = []
            
            for slot in slots:
                slot_start = datetime.strptime(slot['start'], "%Y-%m-%d %H:%M:%S")
                slot_time = slot_start.strftime("%H:%M")
                
                # Apply room preference filter if specified
                if request_doc.get('room_preference') and str(slot['itemId']) != str(request_doc['room_preference']):
                    continue
                
                if booking_data['startTime'] <= slot_time < booking_data['endTime']:
                    target_slots.append(slot)
            
            # Update check count
            monitoring_manager.update_monitoring_status(request_id, 'active')
            
            if not target_slots:
                # No available slots
                result = {
                    "request_id": request_id,
                    "success": False,
                    "available": False,
                    "booked": False,
                    "message": f"No available slots found in timeframe {booking_data['startTime']}-{booking_data['endTime']}"
                }
                results.append(result)
                continue
            
            # Found available slot! Try to book it
            slot_to_book = target_slots[0]
            
            try:
                # Booking logic
                add_url = f"{BASE_URL}/spaces/availability/booking/add"
                add_payload = {
                    "add[eid]": slot_to_book['itemId'], 
                    "add[gid]": GID, 
                    "add[lid]": LID,
                    "add[start]": slot_to_book['start'].split(' ')[0] + ' ' + slot_to_book['start'].split(' ')[1][:5],
                    "add[checksum]": slot_to_book['checksum'],
                    "lid": LID, 
                    "gid": GID, 
                    "start": booking_data['date']
                }
                add_res = session.post(add_url, data=add_payload)
                pending_booking = add_res.json().get("bookings", [])[0]

                # Get session ID
                times_url = f"{BASE_URL}/ajax/space/times"
                times_payload = {
                    f"bookings[0][{key}]": val for key, val in pending_booking.items()
                }
                times_payload["method"] = 11
                times_res = session.post(times_url, data=times_payload)
                html_content = times_res.json().get("html", "")
                match = re.search(r'id="session" name="session" value="(\d+)"', html_content)
                session_id = match.group(1)

                # Submit final booking
                book_url = f"{BASE_URL}/ajax/space/book"
                pending_booking['start'] = pending_booking['start'].replace(" ", "T")[:16]
                pending_booking['end'] = pending_booking['end'].replace(" ", "T")[:16]

                final_payload = {
                    "session": session_id,
                    "fname": booking_data['firstName'],
                    "lname": booking_data['lastName'],
                    "email": booking_data['email'],
                    "q25689": USER_STATUS_ANSWER,
                    "bookings": json.dumps([pending_booking]),
                    "returnUrl": f"/spaces?lid={LID}&gid={GID}", 
                    "pickupHolds": "", 
                    "method": 11,
                }
                final_headers = session.headers.copy()
                if 'Content-Type' in final_headers:
                    del final_headers['Content-Type']
                
                final_res = session.post(book_url, data=final_payload, headers=final_headers)
                
                if final_res.status_code == 200 and "bookId" in final_res.json():
                    # Success! Update monitoring request to completed
                    success_details = {
                        "slot": slot_to_book,
                        "booking_id": final_res.json().get("bookId"),
                        "booked_at": datetime.utcnow().isoformat()
                    }
                    monitoring_manager.update_monitoring_status(
                        request_id, 
                        'completed', 
                        success_details=success_details
                    )
                    
                    booked_count += 1
                    result = {
                        "request_id": request_id,
                        "success": True,
                        "available": True,
                        "booked": True,
                        "message": f"Successfully booked Room {slot_to_book['itemId']} at {slot_to_book['start']}!",
                        "slot": slot_to_book,
                        "booking_id": final_res.json().get("bookId")
                    }
                    results.append(result)
                else:
                    error_msg = f"Found available slot but booking failed for Room {slot_to_book['itemId']}"
                    monitoring_manager.update_monitoring_status(
                        request_id, 
                        'error', 
                        error_message=error_msg
                    )
                    result = {
                        "request_id": request_id,
                        "success": False,
                        "available": True,
                        "booked": False,
                        "message": error_msg,
                        "slot": slot_to_book
                    }
                    results.append(result)
                    
            except Exception as booking_error:
                error_msg = f"Booking error: {str(booking_error)}"
                monitoring_manager.update_monitoring_status(
                    request_id, 
                    'error', 
                    error_message=error_msg
                )
                result = {
                    "request_id": request_id,
                    "success": False,
                    "available": True,
                    "booked": False,
                    "message": error_msg,
                    "slot": slot_to_book if 'slot_to_book' in locals() else None
                }
                results.append(result)
                
        except Exception as e:
            error_msg = f"Error checking availability: {str(e)}"
            monitoring_manager.update_monitoring_status(
                request_id, 
                'error', 
                error_message=error_msg
            )
            result = {
                "request_id": request_id,
                "success": False,
                "available": False,
                "booked": False,
                "message": error_msg
            }
            results.append(result)
    
    return jsonify({
        "success": True,
        "message": f"Checked {checked_count} monitoring requests, successfully booked {booked_count}",
        "checked": checked_count,
        "booked": booked_count,
        "results": results
    })


# For serverless deployment
def handler(event, context):
    """AWS Lambda handler - install serverless-wsgi with: pip install serverless-wsgi"""
    try:
        from serverless_wsgi import handle_request
        return handle_request(app, event, context)
    except ImportError:
        return {
            'statusCode': 500,
            'body': json.dumps({"error": "serverless-wsgi not installed. Run: pip install serverless-wsgi"})
        }

if __name__ == '__main__':
    app.run(debug=True, port=5001)
