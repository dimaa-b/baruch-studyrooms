from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
import json
import re
from datetime import datetime, time
import threading
import time as time_module
from typing import Dict, Any

# --- Flask App Setup ---
app = Flask(__name__)
# This is crucial to allow your frontend (on a different port) to talk to this backend
CORS(app) 

# --- Constants ---
BASE_URL = "https://libraryrooms.baruch.cuny.edu"
LID = 16857
GID = 35704
USER_STATUS_ANSWER = "Current student at Baruch or CUNY SPS"

# --- Global tracking for continuous booking attempts ---
active_booking_attempts: Dict[str, Dict[str, Any]] = {}

# --- API Endpoint to Get Availability ---
@app.route('/api/availability', methods=['GET'])
def get_availability():
    """
    Frontend calls this to get room availability for a given date.
    Example: /api/availability?date=2025-06-24
    """
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
        
        # Process the raw data into a clean format for the frontend
        # Group slots by room (itemId)
        slots_by_room = {}
        for slot in response.json().get("slots", []):
            room_id = slot['itemId']
            if room_id not in slots_by_room:
                slots_by_room[room_id] = []
            
            # Add a simpler time format for display
            slot['displayTime'] = datetime.strptime(slot['start'], "%Y-%m-%d %H:%M:%S").strftime("%-I:%M %p")
            slots_by_room[room_id].append(slot)

        return jsonify(slots_by_room)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

# --- API Endpoint to Make a Booking ---
@app.route('/api/book', methods=['POST'])
def book_room():
    """
    Frontend calls this with all the details to execute the full booking sequence.
    """
    data = request.json
    print(f"Received booking request: {data}")

    # Step 1-4 logic is now encapsulated here on the server
    # 1. Get the specific slot checksum (we refetch to ensure it's fresh)
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/spaces?lid={LID}&gid={GID}"
    })
    
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

    # 2. Add to cart
    add_url = f"{BASE_URL}/spaces/availability/booking/add"
    add_payload = {
        "add[eid]": target_slot['itemId'], "add[gid]": GID, "add[lid]": LID,
        "add[start]": target_slot['start'].split(' ')[0] + ' ' + target_slot['start'].split(' ')[1][:5],
        "add[checksum]": target_slot['checksum'],
        "lid": LID, "gid": GID, "start": data['date']
    }
    add_res = session.post(add_url, data=add_payload)
    pending_booking = add_res.json().get("bookings", [])[0]

    # 3. Get session ID
    times_url = f"{BASE_URL}/ajax/space/times"
    times_payload = {
        f"bookings[0][{key}]": val for key, val in pending_booking.items()
    }
    times_payload["method"] = 11
    times_res = session.post(times_url, data=times_payload)
    html_content = times_res.json().get("html", "")
    match = re.search(r'id="session" name="session" value="(\d+)"', html_content)
    session_id = match.group(1)

    # 4. Submit final booking
    book_url = f"{BASE_URL}/ajax/space/book"
    # Update pending_booking start/end times to match the required format
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
        del final_headers['Content-Type'] # Let requests set the multipart boundary
    
    final_res = session.post(book_url, data=final_payload, headers=final_headers)
    
    if final_res.status_code == 200 and "bookId" in final_res.json():
        return jsonify({"success": True, "message": "Booking is pending! Check your email."})
    else:
        return jsonify({"success": False, "message": "Final booking step failed."}), 500


def continuous_booking_worker(attempt_id: str, booking_data: Dict[str, Any]):
    """
    Worker function that monitors availability and books when a slot becomes available.
    This will watch for cancellations or newly available slots in the target timeframe.
    """
    attempt_info = active_booking_attempts[attempt_id]
    target_date = booking_data['date']
    start_time = booking_data['startTime']
    end_time = booking_data['endTime']
    
    print(f"Starting availability monitor {attempt_id} for {target_date} {start_time}-{end_time}")
    print(f"Watching for cancellations or newly available slots...")
    
    while attempt_info['status'] == 'running':
        try:
            # Check availability for the target timeframe
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": BASE_URL,
                "Referer": f"{BASE_URL}/spaces?lid={LID}&gid={GID}"
            })
            
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
                
                # Check if this slot falls within our target timeframe
                if start_time <= slot_time < end_time:
                    target_slots.append(slot)
            
            if target_slots:
                # Found available slot(s)! Someone must have cancelled or new slots opened
                slot_to_book = target_slots[0]
                print(f"SLOT AVAILABLE! Room {slot_to_book['itemId']} at {slot_to_book['start']} - attempting to book immediately")
                
                # Attempt to book this slot immediately
                try:
                    # Add to cart
                    add_url = f"{BASE_URL}/spaces/availability/booking/add"
                    add_payload = {
                        "add[eid]": slot_to_book['itemId'], "add[gid]": GID, "add[lid]": LID,
                        "add[start]": slot_to_book['start'].split(' ')[0] + ' ' + slot_to_book['start'].split(' ')[1][:5],
                        "add[checksum]": slot_to_book['checksum'],
                        "lid": LID, "gid": GID, "start": target_date
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
                        "returnUrl": f"/spaces?lid={LID}&gid={GID}", "pickupHolds": "", "method": 11,
                    }
                    final_headers = session.headers.copy()
                    if 'Content-Type' in final_headers:
                        del final_headers['Content-Type']
                    
                    final_res = session.post(book_url, data=final_payload, headers=final_headers)
                    
                    if final_res.status_code == 200 and "bookId" in final_res.json():
                        # Success! Update status and stop monitoring
                        attempt_info['status'] = 'success'
                        attempt_info['message'] = f"Successfully booked Room {slot_to_book['itemId']} at {slot_to_book['start']}! A slot became available and was automatically booked."
                        attempt_info['booked_slot'] = slot_to_book
                        print(f"SUCCESS: Automatically booked room for attempt {attempt_id}")
                        return
                    else:
                        print(f"Booking failed for attempt {attempt_id} - slot may have been taken by someone else, continuing to monitor...")
                        
                except Exception as booking_error:
                    print(f"Error during booking attempt {attempt_id}: {str(booking_error)}")
                    print("Continuing to monitor for other available slots...")
                    # Continue monitoring
                    
            else:
                # No available slots found, continue monitoring for cancellations
                attempt_info['last_check'] = datetime.now().isoformat()
                attempt_info['attempts'] += 1
                print(f"Monitor check #{attempt_info['attempts']}: No available slots in timeframe {start_time}-{end_time}")
                
            # Wait before next check (avoid overwhelming the server)
            time_module.sleep(30)  # Check every 30 seconds for cancellations
            
        except Exception as e:
            print(f"Error in continuous booking worker {attempt_id}: {str(e)}")
            attempt_info['status'] = 'error'
            attempt_info['message'] = f"Error occurred: {str(e)}"
            return
    
    # If we get here, the monitoring was stopped
    if attempt_info['status'] == 'running':
        attempt_info['status'] = 'stopped'
        attempt_info['message'] = "Availability monitoring was stopped by user"


@app.route('/api/monitor-and-book', methods=['POST'])
def start_availability_monitor():
    """
    Start monitoring availability for a specific timeframe and automatically book when a slot becomes available.
    This is perfect for catching cancellations or newly opened slots.
    
    Expected payload:
    {
        "date": "2025-06-24",
        "startTime": "13:00",  // 1:00 PM
        "endTime": "14:00",    // 2:00 PM
        "firstName": "John",
        "lastName": "Doe",
        "email": "john@example.com"
    }
    """
    data = request.json
    
    # Validate required fields
    required_fields = ['date', 'startTime', 'endTime', 'firstName', 'lastName', 'email']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    # Generate unique attempt ID
    attempt_id = f"{data['date']}_{data['startTime']}-{data['endTime']}_{datetime.now().timestamp()}"
    
    # Initialize attempt tracking
    active_booking_attempts[attempt_id] = {
        'status': 'running',
        'message': 'Starting availability monitoring...',
        'start_time': datetime.now().isoformat(),
        'attempts': 0,
        'last_check': None,
        'booking_data': data
    }
    
    # Start the monitoring thread
    thread = threading.Thread(
        target=continuous_booking_worker,
        args=(attempt_id, data),
        daemon=True
    )
    thread.start()
    
    return jsonify({
        "success": True,
        "attempt_id": attempt_id,
        "message": f"Started monitoring availability for {data['date']} {data['startTime']}-{data['endTime']}. Will auto-book when a slot becomes available!"
    })


@app.route('/api/monitor-and-book/<attempt_id>/status', methods=['GET'])
def get_monitor_status(attempt_id):
    """
    Get the status of an availability monitoring attempt.
    """
    if attempt_id not in active_booking_attempts:
        return jsonify({"error": "Monitor not found"}), 404
    
    return jsonify(active_booking_attempts[attempt_id])


@app.route('/api/monitor-and-book/<attempt_id>/stop', methods=['POST'])
def stop_availability_monitor(attempt_id):
    """
    Stop monitoring availability.
    """
    if attempt_id not in active_booking_attempts:
        return jsonify({"error": "Monitor not found"}), 404
    
    attempt_info = active_booking_attempts[attempt_id]
    if attempt_info['status'] == 'running':
        attempt_info['status'] = 'stopping'
        return jsonify({"success": True, "message": "Stopping availability monitor..."})
    else:
        return jsonify({"success": False, "message": f"Monitor is already {attempt_info['status']}"})


@app.route('/api/monitor-and-book/list', methods=['GET'])
def list_active_monitors():
    """
    List all active availability monitors.
    """
    return jsonify(active_booking_attempts)


if __name__ == '__main__':
    app.run(debug=True, port=5000)