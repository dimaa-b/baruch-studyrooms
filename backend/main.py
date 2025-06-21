from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
import json
import re
from datetime import datetime

# --- Flask App Setup ---
app = Flask(__name__)
# This is crucial to allow your frontend (on a different port) to talk to this backend
CORS(app) 

# --- Constants ---
BASE_URL = "https://libraryrooms.baruch.cuny.edu"
LID = 16857
GID = 35704
USER_STATUS_ANSWER = "Current student at Baruch or CUNY SPS"

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


if __name__ == '__main__':
    app.run(debug=True, port=5000)