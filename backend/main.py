# Serverless-compatible version of main.py
from flask import Flask, request, jsonify, render_template, make_response
from flask_cors import CORS
import requests
from requests.exceptions import JSONDecodeError as RequestsJSONDecodeError
import json
import re
from datetime import datetime, time
from typing import Dict, Any
from auth import AuthManager, MonitoringManager, require_auth, optional_auth
import os
from dotenv import load_dotenv
from datetime import timedelta

# Load environment variables
load_dotenv()

# --- Flask App Setup ---
app = Flask(__name__)
CORS(
    app,
    origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)

# --- Authentication Setup ---
MONGO_URI = os.environ.get("MONGODB_URI")
if MONGO_URI:
    auth_manager = AuthManager(MONGO_URI)
    monitoring_manager = MonitoringManager(MONGO_URI)
else:
    print("Warning: MONGODB_URI not set. Authentication features will be disabled.")
    auth_manager = None
    monitoring_manager = None

app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

# --- Constants ---
BASE_URL = "https://libraryrooms.baruch.cuny.edu"
LID = 16857
GID = 35704
USER_STATUS_ANSWER = "Current student at Baruch or CUNY SPS"


# --- Helper Functions ---
def determine_slot_availability(slot):
    """
    Determine if a slot is available for booking.

    A slot is considered unavailable if:
    1. It has a className field (usually indicates booked/unavailable status)
    2. The className contains certain keywords that indicate unavailability

    Args:
        slot (dict): The slot object from the external API

    Returns:
        bool: True if available, False if unavailable
    """
    # Check if slot has className field
    if "className" in slot:
        class_name = slot["className"].lower()
        return False

    # If no className or no unavailable keywords found, slot is available
    # Also check that essential fields exist
    return all(field in slot for field in ["checksum", "itemId", "start", "end"])


def find_consecutive_slots(slots_by_room, start_time, duration_hours, date_str):
    """
    Find consecutive available slots for the requested time duration.

    Args:
        slots_by_room (dict): Dictionary of room_id -> list of slots
        start_time (str): Start time in HH:MM format
        duration_hours (int): Duration in hours
        date_str (str): Date in YYYY-MM-DD format

    Returns:
        list: List of consecutive slots, or empty list if none found
    """
    from datetime import datetime, timedelta

    # Parse start time
    start_dt = datetime.strptime(f"{date_str} {start_time}", "%Y-%m-%d %H:%M")

    if duration_hours <= 0:
        return []

    # Search through all rooms for consecutive slots
    for room_id, slots in slots_by_room.items():
        # Filter available slots and sort by start time
        available_slots = [slot for slot in slots if slot.get("available", False)]
        available_slots.sort(
            key=lambda x: datetime.strptime(x["start"], "%Y-%m-%d %H:%M:%S")
        )

        # Look for consecutive slots starting at or after the requested start time
        for i in range(len(available_slots) - duration_hours + 1):
            potential_slots = []
            current_time = start_dt

            # Check if we can build a consecutive sequence
            for j in range(duration_hours):
                slot = available_slots[i + j]
                slot_start = datetime.strptime(slot["start"], "%Y-%m-%d %H:%M:%S")

                # Check if this slot starts at the expected time
                if slot_start == current_time:
                    potential_slots.append(slot)
                    current_time += timedelta(hours=1)
                else:
                    # Not consecutive, break
                    break

            # If we found the required number of consecutive slots
            if len(potential_slots) == duration_hours:
                return potential_slots

    return []


def get_room_availability(target_date_str):
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/spaces?lid={LID}&gid={GID}",
        }
    )

    url = f"{BASE_URL}/spaces/availability/grid"
    try:
        start_date = datetime.strptime(target_date_str, "%Y-%m-%d")
        end_date = start_date + timedelta(days=1)
        end_date_str = end_date.strftime("%Y-%m-%d")
    except Exception as e:
        return jsonify({"error": f"Invalid date format: {e}"}), 400

    payload = {
        "lid": LID,
        "gid": GID,
        "eid": -1,
        "seat": 0,
        "seatId": 0,
        "zone": 0,
        "start": target_date_str,
        "end": end_date_str,
        "pageIndex": 0,
        "pageSize": 18,
    }

    try:
        response = session.post(url, data=payload)
        response.raise_for_status()

        slots_by_room = {}
        for slot in response.json().get("slots", []):
            room_id = slot["itemId"]
            if room_id not in slots_by_room:
                slots_by_room[room_id] = []

            # Add display time
            slot["displayTime"] = datetime.strptime(
                slot["start"], "%Y-%m-%d %H:%M:%S"
            ).strftime("%-I:%M %p")

            slot["available"] = determine_slot_availability(slot)

            slots_by_room[room_id].append(slot)

        return slots_by_room

    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


# --- Authentication Endpoints ---
@app.route("/api/auth/register", methods=["POST"])
def register():
    if not auth_manager:
        return (
            jsonify(
                {
                    "error": "Authentication service not available. Please configure MongoDB."
                }
            ),
            503,
        )

    data = request.json
    required_fields = ["email", "password", "firstName", "lastName"]
    for field in required_fields:
        if field not in data or not data[field].strip():
            return jsonify({"error": f"Missing required field: {field}"}), 400

    result = auth_manager.register_user(
        email=data["email"].strip().lower(),
        password=data["password"],
        first_name=data["firstName"].strip(),
        last_name=data["lastName"].strip(),
    )

    if result["success"]:
        return jsonify(result), 201
    else:
        return jsonify(result), 400


@app.route("/api/auth/login", methods=["POST"])
def login():
    if not auth_manager:
        return (
            jsonify(
                {
                    "error": "Authentication service not available. Please configure MongoDB."
                }
            ),
            503,
        )

    data = request.json
    if not data.get("email") or not data.get("password"):
        return jsonify({"error": "Email/username and password are required"}), 400

    result = auth_manager.login_user(
        email_or_username=data["email"].strip(), password=data["password"]
    )

    if result["success"]:
        response = make_response(
            jsonify(
                {
                    "success": True,
                    "message": result["message"],
                    "user": result["user"],
                    "expires_at": result["expires_at"],
                }
            )
        )

        response.set_cookie(
            "session_token",
            result["token"],
            max_age=7 * 24 * 60 * 60,
            httponly=True,
            secure=False,
            samesite="Lax",
        )
        return response, 200
    else:
        return jsonify(result), 401


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    if not auth_manager:
        return jsonify({"success": True, "message": "Logged out successfully"})

    session_token = request.cookies.get("session_token")
    if session_token:
        auth_manager.logout_user(session_token)

    response = make_response(
        jsonify({"success": True, "message": "Logged out successfully"})
    )
    response.set_cookie("session_token", "", expires=0)
    return response


@app.route("/api/auth/me", methods=["GET"])
def get_current_user():
    if not auth_manager:
        return jsonify({"error": "Authentication service not available"}), 503

    session_token = request.cookies.get("session_token") or request.headers.get(
        "Authorization"
    )
    if session_token and session_token.startswith("Bearer "):
        session_token = session_token[7:]

    user = auth_manager.get_user_from_session(session_token)
    if not user:
        return (
            jsonify({"error": "Authentication required", "authenticated": False}),
            401,
        )

    return jsonify(
        {
            "authenticated": True,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "username": user["username"],
                "firstName": user["first_name"],
                "lastName": user["last_name"],
            },
        }
    )


@app.route("/api/auth/check", methods=["GET"])
def check_auth():
    if not auth_manager:
        return jsonify({"authenticated": False})

    session_token = request.cookies.get("session_token") or request.headers.get(
        "Authorization"
    )
    if session_token and session_token.startswith("Bearer "):
        session_token = session_token[7:]

    user = auth_manager.get_user_from_session(session_token)
    if user:
        return jsonify(
            {
                "authenticated": True,
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "username": user["username"],
                    "firstName": user["first_name"],
                    "lastName": user["last_name"],
                },
            }
        )
    else:
        return jsonify({"authenticated": False})


# --- Room Booking Endpoints ---
@app.route("/api/availability", methods=["GET"])
def get_availability():
    target_date_str = request.args.get("date")
    if not target_date_str:
        return jsonify({"error": "Date parameter is required"}), 400

    response = get_room_availability(target_date_str)
    return jsonify(response)


@app.route("/api/book", methods=["POST"])
@optional_auth(auth_manager)
def book_room():
    data = request.json
    print(f"Received booking request: {data}")

    if request.current_user:
        if not data.get("firstName"):
            data["firstName"] = request.current_user["first_name"]
        if not data.get("lastName"):
            data["lastName"] = request.current_user["last_name"]
        if not data.get("email"):
            data["email"] = request.current_user["email"]

    # Validate required fields
    required_fields = [
        "date",
        "startTime",
        "duration",
        "firstName",
        "lastName",
        "email",
    ]
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    # Validate duration is a positive integer and limit to 1-2 hours
    try:
        duration_hours = int(data["duration"])
        if duration_hours <= 0:
            return (
                jsonify({"error": "Duration must be a positive integer (hours)"}),
                400,
            )
        if duration_hours > 2:
            return (
                jsonify({"error": "Duration must be 1 or 2 hours only"}),
                400,
            )
    except (ValueError, TypeError):
        return jsonify({"error": "Duration must be a positive integer (hours)"}), 400

    # Get room availability using the existing function
    slots_by_room = get_room_availability(data["date"])

    # Check if there's an error in the availability response
    if isinstance(slots_by_room, dict) and "error" in slots_by_room:
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Failed to check availability: {slots_by_room['error']}",
                }
            ),
            500,
        )

    # Calculate end time from start time and duration
    start_time = data["startTime"]

    # Extract just the time part if full datetime strings are provided
    if len(start_time) > 5:  # If it's a full datetime string
        start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S").strftime(
            "%H:%M"
        )

    # Calculate end time
    start_dt = datetime.strptime(f"{data['date']} {start_time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(hours=duration_hours)
    end_time = end_dt.strftime("%H:%M")

    # Find consecutive slots for the requested duration
    target_slots = find_consecutive_slots(
        slots_by_room, start_time, duration_hours, data["date"]
    )

    if not target_slots:
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"No {duration_hours}-hour consecutive slots available starting from {start_time}",
                }
            ),
            409,
        )

    # Set up session for booking API calls
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/spaces?lid={LID}&gid={GID}",
        }
    )

    target_slot = target_slots[0]
    # send the first booking request (for the first hour)
    add_url = f"{BASE_URL}/spaces/availability/booking/add"
    add_payload = {
        "add[eid]": target_slot["itemId"],
        "add[gid]": GID,
        "add[lid]": LID,
        "add[start]": target_slot["start"].split(" ")[0]
        + " "
        + target_slot["start"].split(" ")[1][:5],
        "add[end]": target_slot["end"].split(" ")[0]
        + " "
        + target_slot["end"].split(" ")[1][:5],
        "add[checksum]": target_slot["checksum"],
        "lid": LID,
        "gid": GID,
        "start": data["date"],
        "end": data["date"],
    }

    add_res = session.post(add_url, data=add_payload)
    
    # Check first booking response
    if add_res.status_code != 200:
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Failed to add first hour to cart. Status: {add_res.status_code}",
                }
            ),
            500,
        )

    try:
        add_response_data = add_res.json()
        print(f"Add first slot to cart response: {add_response_data}")
    except RequestsJSONDecodeError:
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Invalid response from booking system for first slot.",
                }
            ),
            500,
        )

    if "bookings" not in add_response_data or not add_response_data["bookings"]:
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"No bookings returned for first slot.",
                }
            ),
            500,
        )

    # Initialize all_bookings with the first booking
    all_bookings = [add_response_data["bookings"][0]]

    # If we need a 2-hour booking, update the booking to extend to the second slot
    if duration_hours > 1:
        second_slot = target_slots[1]
        first_booking = all_bookings[0]
        
        # Use update URL instead of add URL for the second slot
        update_url = f"{BASE_URL}/spaces/availability/booking/add"
        update_payload = {
            "update[id]": first_booking["id"],
            "update[checksum]": first_booking['optionChecksums'][1],
            "update[end]": second_slot["end"].split(" ")[0] + " " + second_slot["end"].split(" ")[1][:8],  # Include seconds
            "lid": LID,
            "gid": GID,
            "start": data["date"],
            "end": data["date"],
            # Include the existing booking information
            f"bookings[0][id]": first_booking["id"],
            f"bookings[0][eid]": first_booking["eid"],
            f"bookings[0][seat_id]": 0,
            f"bookings[0][gid]": GID,
            f"bookings[0][lid]": LID,
            f"bookings[0][start]": target_slot["start"].split(" ")[0] + " " + target_slot["start"].split(" ")[1][:5],
            f"bookings[0][end]": target_slot["end"].split(" ")[0] + " " + target_slot["end"].split(" ")[1][:5],
            f"bookings[0][checksum]": first_booking["checksum"]
        }

        second_add_res = session.post(update_url, data=update_payload)
        
        if second_add_res.status_code != 200:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Failed to extend booking to second hour. Status: {second_add_res.status_code}",
                    }
                ),
                500,
            )

        try:
            second_add_response_data = second_add_res.json()
            print(f"Update booking to second slot response: {second_add_response_data}")
        except RequestsJSONDecodeError:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Invalid response from booking system for second slot.",
                    }
                ),
                500,
            )

        if "bookings" not in second_add_response_data or not second_add_response_data["bookings"]:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"No bookings returned for second slot.",
                    }
                ),
                500,
            )

        # Update the booking with the extended time
        all_bookings = [second_add_response_data["bookings"][0]]

    # Submit final booking with all slots
    book_url = f"{BASE_URL}/ajax/space/book"

    # Format booking object to match the expected structure
    formatted_bookings = []
    
    # For 2-hour bookings, we have one extended booking
    # For 1-hour bookings, we have one regular booking
    pending_booking = all_bookings[0]
    first_slot = target_slots[0]
    last_slot = target_slots[-1] if len(target_slots) > 1 else target_slots[0]
    
    formatted_booking = {
        "id": 1,
        "eid": pending_booking.get('eid', first_slot['itemId']),
        "seat_id": 0,
        "gid": GID,
        "lid": LID,
        "start": first_slot['start'].split(' ')[0] + ' ' + first_slot['start'].split(' ')[1][:5],
        "end": last_slot['end'].split(' ')[0] + ' ' + last_slot['end'].split(' ')[1][:5],
        "checksum": pending_booking['checksum']
    }
    formatted_bookings.append(formatted_booking)

    final_payload = {
        "fname": data['firstName'],
        "lname": data['lastName'],
        "email": data['email'],
        "q25689": USER_STATUS_ANSWER,
        "bookings": json.dumps(formatted_bookings),
        "returnUrl": f"/spaces?lid={LID}&gid={GID}",
        "pickupHolds": "",
        "method": 11,
    }
    
    final_headers = session.headers.copy()
    if 'Content-Type' in final_headers:
        del final_headers['Content-Type']

    final_res = session.post(book_url, data=final_payload, headers=final_headers)

    # Check final booking response
    if final_res.status_code != 200:
        return jsonify({
            "success": False,
            "message": f"Final booking failed. Status: {final_res.status_code}, Response: {final_res.text[:500]}"
        }), 500

    try:
        final_response_data = final_res.json()
    except RequestsJSONDecodeError:
        return jsonify({
            "success": False,
            "message": f"Invalid response from final booking. Response: {final_res.text[:500]}"
        }), 500

    if "bookId" in final_response_data:
        # Create booking summary for multiple slots
        first_slot = target_slots[0]
        last_slot = target_slots[-1]
        room_id = first_slot['itemId']

        # Calculate total duration
        start_display = datetime.strptime(first_slot['start'], "%Y-%m-%d %H:%M:%S").strftime("%-I:%M %p")
        end_display = datetime.strptime(last_slot['end'], "%Y-%m-%d %H:%M:%S").strftime("%-I:%M %p")

        return jsonify({
            "success": True,
            "message": f"Successfully booked {len(target_slots)} consecutive slots in Room {room_id} from {start_display} to {end_display}! Check your email for confirmation.",
            "booking": {
                "room_id": room_id,
                "start_time": first_slot['start'],
                "end_time": last_slot['end'],
                "display_time": f"{start_display} - {end_display}",
                "slot_count": len(target_slots),
                "booking_id": final_response_data.get("bookId"),
                "slots": [{"start": slot['start'], "end": slot['end']} for slot in target_slots]
            }
        })
    else:
        return jsonify({
            "success": False,
            "message": f"Final booking step failed - no booking ID returned. Response: {final_response_data}"
        }), 500

@app.route("/api/monitoring/create", methods=["POST"])
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
        user_id = request.current_user["id"]
        if not data.get("firstName"):
            data["firstName"] = request.current_user["first_name"]
        if not data.get("lastName"):
            data["lastName"] = request.current_user["last_name"]
        if not data.get("email"):
            data["email"] = request.current_user["email"]

    # Validate required fields
    required_fields = [
        "date",
        "startTime",
        "duration",
        "firstName",
        "lastName",
        "email",
    ]
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    # Validate duration is a positive integer and limit to 1-2 hours
    try:
        duration_hours = int(data["duration"])
        if duration_hours <= 0:
            return (
                jsonify({"error": "Duration must be a positive integer (hours)"}),
                400,
            )
        if duration_hours > 2:
            return (
                jsonify({"error": "Duration must be 1 or 2 hours only"}),
                400,
            )
    except (ValueError, TypeError):
        return jsonify({"error": "Duration must be a positive integer (hours)"}), 400

    # Calculate end time from start time and duration
    start_time = data["startTime"]
    if len(start_time) > 5:  # If it's a full datetime string
        start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S").strftime(
            "%H:%M"
        )

    start_dt = datetime.strptime(f"{data['date']} {start_time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(hours=duration_hours)
    end_time = end_dt.strftime("%H:%M")

    # Create monitoring request in database
    result = monitoring_manager.create_monitoring_request(
        user_id=user_id,
        email=data["email"],
        first_name=data["firstName"],
        last_name=data["lastName"],
        target_date=data["date"],
        start_time=start_time,
        end_time=end_time,
        duration_hours=duration_hours,
        room_preference=data.get("roomPreference"),
    )

    if result["success"]:
        return (
            jsonify(
                {
                    "success": True,
                    "request_id": result["request_id"],
                    "message": f"Monitoring request created for {data['date']} {start_time}-{end_time} ({duration_hours} hours). Use external scheduler to check periodically.",
                }
            ),
            201,
        )
    else:
        return jsonify(result), 500


@app.route("/api/monitoring/<request_id>", methods=["GET"])
def get_monitoring_request(request_id):
    """Get details of a specific monitoring request"""
    request_doc = monitoring_manager.get_monitoring_request(request_id)

    if not request_doc:
        return jsonify({"error": "Monitoring request not found"}), 404

    return jsonify(request_doc)


@app.route("/api/monitoring/<request_id>/check-and-book", methods=["POST"])
def check_and_book_for_request(request_id):
    """
    Check availability and attempt booking for a specific monitoring request.
    This endpoint is designed to be called by external schedulers (cron, etc.)
    """
    request_doc = monitoring_manager.get_monitoring_request(request_id)

    if not request_doc:
        return jsonify({"error": "Monitoring request not found"}), 404

    if request_doc["status"] != "active":
        return (
            jsonify(
                {
                    "error": f"Monitoring request is not active (status: {request_doc['status']})"
                }
            ),
            400,
        )

    # Prepare booking data from stored request
    booking_data = {
        "date": request_doc["target_date"],
        "startTime": request_doc["start_time"],
        "duration": request_doc["duration_hours"],
        "firstName": request_doc["first_name"],
        "lastName": request_doc["last_name"],
        "email": request_doc["email"],
    }

    try:
        # Use the same logic as book_room function
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": BASE_URL,
                "Referer": f"{BASE_URL}/spaces?lid={LID}&gid={GID}",
            }
        )

        # Check availability using the existing function
        slots_by_room = get_room_availability(booking_data["date"])

        # Check if there's an error in the availability response
        if isinstance(slots_by_room, dict) and "error" in slots_by_room:
            return jsonify(
                {
                    "success": False,
                    "available": False,
                    "message": f"Failed to check availability: {slots_by_room['error']}",
                }
            )

        # Find consecutive slots for the requested duration
        target_slots = find_consecutive_slots(
            slots_by_room,
            booking_data["startTime"],
            booking_data["duration"],
            booking_data["date"],
        )

        # Apply room preference filter if specified
        if request_doc.get("room_preference") and target_slots:
            target_slots = [
                slot
                for slot in target_slots
                if str(slot["itemId"]) == str(request_doc["room_preference"])
            ]

        # Update check count
        monitoring_manager.update_monitoring_status(request_id, "active")

        if not target_slots:
            return jsonify(
                {
                    "success": False,
                    "available": False,
                    "message": f"No {booking_data['duration']}-hour consecutive slots available starting from {booking_data['startTime']}",
                    "check_count": request_doc.get("check_count", 0) + 1,
                }
            )

        # Found consecutive slots! Try to book them using the same logic as book_room

        target_slot = target_slots[0]
        duration_hours = booking_data["duration"]
        
        # send the first booking request (for the first hour)
        add_url = f"{BASE_URL}/spaces/availability/booking/add"
        add_payload = {
            "add[eid]": target_slot["itemId"],
            "add[gid]": GID,
            "add[lid]": LID,
            "add[start]": target_slot["start"].split(" ")[0]
            + " "
            + target_slot["start"].split(" ")[1][:5],
            "add[end]": target_slot["end"].split(" ")[0]
            + " "
            + target_slot["end"].split(" ")[1][:5],
            "add[checksum]": target_slot["checksum"],
            "lid": LID,
            "gid": GID,
            "start": booking_data["date"],
            "end": booking_data["date"],
        }

        add_res = session.post(add_url, data=add_payload)
        
        # Check first booking response
        if add_res.status_code != 200:
            error_msg = f"Failed to add first hour to cart. Status: {add_res.status_code}"
            monitoring_manager.update_monitoring_status(
                request_id, "error", error_message=error_msg
            )
            return jsonify(
                {
                    "success": False,
                    "available": True,
                    "booked": False,
                    "message": error_msg,
                }
            )

        try:
            add_response_data = add_res.json()
            print(f"Add first slot to cart response: {add_response_data}")
        except RequestsJSONDecodeError:
            error_msg = "Invalid response from booking system for first slot."
            monitoring_manager.update_monitoring_status(
                request_id, "error", error_message=error_msg
            )
            return jsonify(
                {
                    "success": False,
                    "available": True,
                    "booked": False,
                    "message": error_msg,
                }
            )

        if "bookings" not in add_response_data or not add_response_data["bookings"]:
            error_msg = "No bookings returned for first slot."
            monitoring_manager.update_monitoring_status(
                request_id, "error", error_message=error_msg
            )
            return jsonify(
                {
                    "success": False,
                    "available": True,
                    "booked": False,
                    "message": error_msg,
                }
            )

        # Initialize all_bookings with the first booking
        all_bookings = [add_response_data["bookings"][0]]

        # If we need a 2-hour booking, update the booking to extend to the second slot
        if duration_hours > 1:
            second_slot = target_slots[1]
            first_booking = all_bookings[0]
            
            # Use update URL instead of add URL for the second slot
            update_url = f"{BASE_URL}/spaces/availability/booking/add"
            update_payload = {
                "update[id]": first_booking["id"],
                "update[checksum]": first_booking['optionChecksums'][1],
                "update[end]": second_slot["end"].split(" ")[0] + " " + second_slot["end"].split(" ")[1][:8],  # Include seconds
                "lid": LID,
                "gid": GID,
                "start": booking_data["date"],
                "end": booking_data["date"],
                # Include the existing booking information
                f"bookings[0][id]": first_booking["id"],
                f"bookings[0][eid]": first_booking["eid"],
                f"bookings[0][seat_id]": 0,
                f"bookings[0][gid]": GID,
                f"bookings[0][lid]": LID,
                f"bookings[0][start]": target_slot["start"].split(" ")[0] + " " + target_slot["start"].split(" ")[1][:5],
                f"bookings[0][end]": target_slot["end"].split(" ")[0] + " " + target_slot["end"].split(" ")[1][:5],
                f"bookings[0][checksum]": first_booking["checksum"]
            }

            second_add_res = session.post(update_url, data=update_payload)
            
            if second_add_res.status_code != 200:
                error_msg = f"Failed to extend booking to second hour. Status: {second_add_res.status_code}"
                monitoring_manager.update_monitoring_status(
                    request_id, "error", error_message=error_msg
                )
                return jsonify(
                    {
                        "success": False,
                        "available": True,
                        "booked": False,
                        "message": error_msg,
                    }
                )

            try:
                second_add_response_data = second_add_res.json()
                print(f"Update booking to second slot response: {second_add_response_data}")
            except RequestsJSONDecodeError:
                error_msg = "Invalid response from booking system for second slot."
                monitoring_manager.update_monitoring_status(
                    request_id, "error", error_message=error_msg
                )
                return jsonify(
                    {
                        "success": False,
                        "available": True,
                        "booked": False,
                        "message": error_msg,
                    }
                )

            if "bookings" not in second_add_response_data or not second_add_response_data["bookings"]:
                error_msg = "No bookings returned for second slot."
                monitoring_manager.update_monitoring_status(
                    request_id, "error", error_message=error_msg
                )
                return jsonify(
                    {
                        "success": False,
                        "available": True,
                        "booked": False,
                        "message": error_msg,
                    }
                )

            # Update the booking with the extended time
            all_bookings = [second_add_response_data["bookings"][0]]

        # Submit final booking with all slots
        book_url = f"{BASE_URL}/ajax/space/book"

        # Format booking object to match the expected structure
        formatted_bookings = []
        
        # For 2-hour bookings, we have one extended booking
        # For 1-hour bookings, we have one regular booking
        pending_booking = all_bookings[0]
        first_slot = target_slots[0]
        last_slot = target_slots[-1] if len(target_slots) > 1 else target_slots[0]
        
        formatted_booking = {
            "id": 1,
            "eid": pending_booking.get('eid', first_slot['itemId']),
            "seat_id": 0,
            "gid": GID,
            "lid": LID,
            "start": first_slot['start'].split(' ')[0] + ' ' + first_slot['start'].split(' ')[1][:5],
            "end": last_slot['end'].split(' ')[0] + ' ' + last_slot['end'].split(' ')[1][:5],
            "checksum": pending_booking['checksum']
        }
        formatted_bookings.append(formatted_booking)

        final_payload = {
            "fname": booking_data['firstName'],
            "lname": booking_data['lastName'],
            "email": booking_data['email'],
            "q25689": USER_STATUS_ANSWER,
            "bookings": json.dumps(formatted_bookings),
            "returnUrl": f"/spaces?lid={LID}&gid={GID}",
            "pickupHolds": "",
            "method": 11,
        }
        
        final_headers = session.headers.copy()
        if 'Content-Type' in final_headers:
            del final_headers['Content-Type']

        final_res = session.post(book_url, data=final_payload, headers=final_headers)

        # Check final booking response
        if final_res.status_code != 200:
            error_msg = f"Final booking failed. Status: {final_res.status_code}, Response: {final_res.text[:500]}"
            monitoring_manager.update_monitoring_status(
                request_id, "error", error_message=error_msg
            )
            return jsonify({
                "success": False,
                "available": True,
                "booked": False,
                "message": error_msg
            })

        try:
            final_response_data = final_res.json()
        except RequestsJSONDecodeError:
            error_msg = f"Invalid response from final booking. Response: {final_res.text[:500]}"
            monitoring_manager.update_monitoring_status(
                request_id, "error", error_message=error_msg
            )
            return jsonify({
                "success": False,
                "available": True,
                "booked": False,
                "message": error_msg
            })

        if "bookId" in final_response_data:
            # Success! Update monitoring request to completed
            first_slot = target_slots[0]
            last_slot = target_slots[-1]
            room_id = first_slot["itemId"]
            start_display = datetime.strptime(
                first_slot["start"], "%Y-%m-%d %H:%M:%S"
            ).strftime("%-I:%M %p")
            end_display = datetime.strptime(
                last_slot["end"], "%Y-%m-%d %H:%M:%S"
            ).strftime("%-I:%M %p")

            success_details = {
                "slots": target_slots,
                "booking_id": final_response_data.get("bookId"),
                "booked_at": datetime.utcnow().isoformat(),
                "slot_count": len(target_slots),
            }
            monitoring_manager.update_monitoring_status(
                request_id, "completed", success_details=success_details
            )

            return jsonify(
                {
                    "success": True,
                    "available": True,
                    "booked": True,
                    "message": f"Successfully booked {len(target_slots)} consecutive slots in Room {room_id} from {start_display} to {end_display}!",
                    "slots": target_slots,
                    "booking_id": final_response_data.get("bookId"),
                }
            )
        else:
            error_msg = f"Final booking step failed - no booking ID returned. Response: {final_response_data}"
            monitoring_manager.update_monitoring_status(
                request_id, "error", error_message=error_msg
            )
            return jsonify({
                "success": False,
                "available": True,
                "booked": False,
                "message": error_msg
            })

    except Exception as e:
        error_msg = f"Error checking availability: {str(e)}"
        monitoring_manager.update_monitoring_status(
            request_id, "error", error_message=error_msg
        )
        return jsonify({"error": error_msg}), 500


@app.route("/api/monitoring/<request_id>/stop", methods=["POST"])
@optional_auth(auth_manager)
def stop_monitoring_request(request_id):
    """Stop a monitoring request"""
    user_id = request.current_user["id"] if request.current_user else None

    success = monitoring_manager.stop_monitoring_request(request_id, user_id)

    if success:
        return jsonify({"success": True, "message": "Monitoring request stopped"})
    else:
        return (
            jsonify(
                {"error": "Failed to stop monitoring request or request not found"}
            ),
            400,
        )


@app.route("/api/monitoring/list", methods=["GET"])
@optional_auth(auth_manager)
def list_monitoring_requests():
    """List monitoring requests (user's own if authenticated, or all if admin)"""
    if request.current_user:
        # Return user's own requests
        requests = monitoring_manager.get_user_monitoring_requests(
            request.current_user["id"]
        )
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
                "check_count": req.get("check_count", 0),
            }
            sanitized_requests.append(sanitized_req)
        return jsonify({"requests": sanitized_requests})


@app.route("/api/monitoring/active", methods=["GET"])
def get_active_monitoring_requests():
    """Get all active monitoring requests (for external schedulers)"""
    requests = monitoring_manager.get_active_monitoring_requests()
    return jsonify({"requests": requests})


@app.route("/api/monitoring/check-all", methods=["POST"])
def check_all_monitoring_requests():
    """
    Check all active monitoring requests and attempt bookings.
    This endpoint is designed to be called by external schedulers.
    """
    active_requests = monitoring_manager.get_active_monitoring_requests()

    if not active_requests:
        return jsonify(
            {
                "success": True,
                "message": "No active monitoring requests to check",
                "checked": 0,
                "results": [],
            }
        )

    results = []
    checked_count = 0
    booked_count = 0

    for request_doc in active_requests:
        request_id = request_doc["request_id"]
        checked_count += 1

        try:
            # Prepare booking data from stored request
            booking_data = {
                "date": request_doc["target_date"],
                "startTime": request_doc["start_time"],
                "duration": request_doc["duration_hours"],
                "firstName": request_doc["first_name"],
                "lastName": request_doc["last_name"],
                "email": request_doc["email"],
            }

            # Use the same logic as book_room function
            session = requests.Session()
            session.headers.update(
                {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": BASE_URL,
                    "Referer": f"{BASE_URL}/spaces?lid={LID}&gid={GID}",
                }
            )

            # Check availability using the existing function
            slots_by_room = get_room_availability(booking_data["date"])

            # Check if there's an error in the availability response
            if isinstance(slots_by_room, dict) and "error" in slots_by_room:
                result = {
                    "request_id": request_id,
                    "success": False,
                    "available": False,
                    "booked": False,
                    "message": f"Failed to check availability: {slots_by_room['error']}",
                }
                results.append(result)
                continue

            # Find consecutive slots for the requested duration
            target_slots = find_consecutive_slots(
                slots_by_room,
                booking_data["startTime"],
                booking_data["duration"],
                booking_data["date"],
            )

            # Apply room preference filter if specified
            if request_doc.get("room_preference") and target_slots:
                target_slots = [
                    slot
                    for slot in target_slots
                    if str(slot["itemId"]) == str(request_doc["room_preference"])
                ]

            # Update check count
            monitoring_manager.update_monitoring_status(request_id, "active")

            if not target_slots:
                result = {
                    "request_id": request_id,
                    "success": False,
                    "available": False,
                    "booked": False,
                    "message": f"No {booking_data['duration']}-hour consecutive slots available starting from {booking_data['startTime']}",
                }
                results.append(result)
                continue

            # Found consecutive slots! Try to book them using the same logic as book_room

            target_slot = target_slots[0]
            duration_hours = booking_data["duration"]
            
            # send the first booking request (for the first hour)
            add_url = f"{BASE_URL}/spaces/availability/booking/add"
            add_payload = {
                "add[eid]": target_slot["itemId"],
                "add[gid]": GID,
                "add[lid]": LID,
                "add[start]": target_slot["start"].split(" ")[0]
                + " "
                + target_slot["start"].split(" ")[1][:5],
                "add[end]": target_slot["end"].split(" ")[0]
                + " "
                + target_slot["end"].split(" ")[1][:5],
                "add[checksum]": target_slot["checksum"],
                "lid": LID,
                "gid": GID,
                "start": booking_data["date"],
                "end": booking_data["date"],
            }

            add_res = session.post(add_url, data=add_payload)
            
            # Check first booking response
            if add_res.status_code != 200:
                error_msg = f"Failed to add first hour to cart. Status: {add_res.status_code}"
                monitoring_manager.update_monitoring_status(
                    request_id, "error", error_message=error_msg
                )
                result = {
                    "request_id": request_id,
                    "success": False,
                    "available": True,
                    "booked": False,
                    "message": error_msg,
                }
                results.append(result)
                continue

            try:
                add_response_data = add_res.json()
                print(f"Add first slot to cart response: {add_response_data}")
            except RequestsJSONDecodeError:
                error_msg = "Invalid response from booking system for first slot."
                monitoring_manager.update_monitoring_status(
                    request_id, "error", error_message=error_msg
                )
                result = {
                    "request_id": request_id,
                    "success": False,
                    "available": True,
                    "booked": False,
                    "message": error_msg,
                }
                results.append(result)
                continue

            if "bookings" not in add_response_data or not add_response_data["bookings"]:
                error_msg = "No bookings returned for first slot."
                monitoring_manager.update_monitoring_status(
                    request_id, "error", error_message=error_msg
                )
                result = {
                    "request_id": request_id,
                    "success": False,
                    "available": True,
                    "booked": False,
                    "message": error_msg,
                }
                results.append(result)
                continue

            # Initialize all_bookings with the first booking
            all_bookings = [add_response_data["bookings"][0]]

            # If we need a 2-hour booking, update the booking to extend to the second slot
            if duration_hours > 1:
                second_slot = target_slots[1]
                first_booking = all_bookings[0]
                
                # Use update URL instead of add URL for the second slot
                update_url = f"{BASE_URL}/spaces/availability/booking/add"
                update_payload = {
                    "update[id]": first_booking["id"],
                    "update[checksum]": first_booking['optionChecksums'][1],
                    "update[end]": second_slot["end"].split(" ")[0] + " " + second_slot["end"].split(" ")[1][:8],  # Include seconds
                    "lid": LID,
                    "gid": GID,
                    "start": booking_data["date"],
                    "end": booking_data["date"],
                    # Include the existing booking information
                    f"bookings[0][id]": first_booking["id"],
                    f"bookings[0][eid]": first_booking["eid"],
                    f"bookings[0][seat_id]": 0,
                    f"bookings[0][gid]": GID,
                    f"bookings[0][lid]": LID,
                    f"bookings[0][start]": target_slot["start"].split(" ")[0] + " " + target_slot["start"].split(" ")[1][:5],
                    f"bookings[0][end]": target_slot["end"].split(" ")[0] + " " + target_slot["end"].split(" ")[1][:5],
                    f"bookings[0][checksum]": first_booking["checksum"]
                }

                second_add_res = session.post(update_url, data=update_payload)
                
                if second_add_res.status_code != 200:
                    error_msg = f"Failed to extend booking to second hour. Status: {second_add_res.status_code}"
                    monitoring_manager.update_monitoring_status(
                        request_id, "error", error_message=error_msg
                    )
                    result = {
                        "request_id": request_id,
                        "success": False,
                        "available": True,
                        "booked": False,
                        "message": error_msg,
                    }
                    results.append(result)
                    continue

                try:
                    second_add_response_data = second_add_res.json()
                    print(f"Update booking to second slot response: {second_add_response_data}")
                except RequestsJSONDecodeError:
                    error_msg = "Invalid response from booking system for second slot."
                    monitoring_manager.update_monitoring_status(
                        request_id, "error", error_message=error_msg
                    )
                    result = {
                        "request_id": request_id,
                        "success": False,
                        "available": True,
                        "booked": False,
                        "message": error_msg,
                    }
                    results.append(result)
                    continue

                if "bookings" not in second_add_response_data or not second_add_response_data["bookings"]:
                    error_msg = "No bookings returned for second slot."
                    monitoring_manager.update_monitoring_status(
                        request_id, "error", error_message=error_msg
                    )
                    result = {
                        "request_id": request_id,
                        "success": False,
                        "available": True,
                        "booked": False,
                        "message": error_msg,
                    }
                    results.append(result)
                    continue

                # Update the booking with the extended time
                all_bookings = [second_add_response_data["bookings"][0]]

            # Submit final booking with all slots
            book_url = f"{BASE_URL}/ajax/space/book"

            # Format booking object to match the expected structure
            formatted_bookings = []
            
            # For 2-hour bookings, we have one extended booking
            # For 1-hour bookings, we have one regular booking
            pending_booking = all_bookings[0]
            first_slot = target_slots[0]
            last_slot = target_slots[-1] if len(target_slots) > 1 else target_slots[0]
            
            formatted_booking = {
                "id": 1,
                "eid": pending_booking.get('eid', first_slot['itemId']),
                "seat_id": 0,
                "gid": GID,
                "lid": LID,
                "start": first_slot['start'].split(' ')[0] + ' ' + first_slot['start'].split(' ')[1][:5],
                "end": last_slot['end'].split(' ')[0] + ' ' + last_slot['end'].split(' ')[1][:5],
                "checksum": pending_booking['checksum']
            }
            formatted_bookings.append(formatted_booking)

            final_payload = {
                "fname": booking_data['firstName'],
                "lname": booking_data['lastName'],
                "email": booking_data['email'],
                "q25689": USER_STATUS_ANSWER,
                "bookings": json.dumps(formatted_bookings),
                "returnUrl": f"/spaces?lid={LID}&gid={GID}",
                "pickupHolds": "",
                "method": 11,
            }
            
            final_headers = session.headers.copy()
            if 'Content-Type' in final_headers:
                del final_headers['Content-Type']

            final_res = session.post(book_url, data=final_payload, headers=final_headers)

            # Check final booking response
            if final_res.status_code != 200:
                error_msg = f"Final booking failed. Status: {final_res.status_code}, Response: {final_res.text[:500]}"
                monitoring_manager.update_monitoring_status(
                    request_id, "error", error_message=error_msg
                )
                result = {
                    "request_id": request_id,
                    "success": False,
                    "available": True,
                    "booked": False,  
                    "message": error_msg,
                }
                results.append(result)
                continue

            try:
                final_response_data = final_res.json()
            except RequestsJSONDecodeError:
                error_msg = f"Invalid response from final booking. Response: {final_res.text[:500]}"
                monitoring_manager.update_monitoring_status(
                    request_id, "error", error_message=error_msg
                )
                result = {
                    "request_id": request_id,
                    "success": False,
                    "available": True,
                    "booked": False,
                    "message": error_msg,
                }
                results.append(result)
                continue

            if "bookId" in final_response_data:
                # Success! Update monitoring request to completed
                first_slot = target_slots[0]
                last_slot = target_slots[-1]
                room_id = first_slot["itemId"]
                start_display = datetime.strptime(
                    first_slot["start"], "%Y-%m-%d %H:%M:%S"
                ).strftime("%-I:%M %p")
                end_display = datetime.strptime(
                    last_slot["end"], "%Y-%m-%d %H:%M:%S"
                ).strftime("%-I:%M %p")

                success_details = {
                    "slots": target_slots,
                    "booking_id": final_response_data.get("bookId"),
                    "booked_at": datetime.utcnow().isoformat(),
                    "slot_count": len(target_slots),
                }
                monitoring_manager.update_monitoring_status(
                    request_id, "completed", success_details=success_details
                )

                booked_count += 1
                result = {
                    "request_id": request_id,
                    "success": True,
                    "available": True,
                    "booked": True,
                    "message": f"Successfully booked {len(target_slots)} consecutive slots in Room {room_id} from {start_display} to {end_display}!",
                    "slots": target_slots,
                    "booking_id": final_response_data.get("bookId"),
                }
                results.append(result)
            else:
                error_msg = f"Final booking step failed - no booking ID returned. Response: {final_response_data}"
                monitoring_manager.update_monitoring_status(
                    request_id, "error", error_message=error_msg
                )
                result = {
                    "request_id": request_id,
                    "success": False,
                    "available": True,
                    "booked": False,
                    "message": error_msg,
                }
                results.append(result)

        except Exception as e:
            error_msg = f"Error checking availability: {str(e)}"
            monitoring_manager.update_monitoring_status(
                request_id, "error", error_message=error_msg
            )
            result = {
                "request_id": request_id,
                "success": False,
                "available": False,
                "booked": False,
                "message": error_msg,
            }
            results.append(result)

    return jsonify(
        {
            "success": True,
            "message": f"Checked {checked_count} monitoring requests, successfully booked {booked_count}",
            "checked": checked_count,
            "booked": booked_count,
            "results": results,
        }
    )


# For serverless deployment
def handler(event, context):
    """AWS Lambda handler - install serverless-wsgi with: pip install serverless-wsgi"""
    try:
        from serverless_wsgi import handle_request

        return handle_request(app, event, context)
    except ImportError:
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": "serverless-wsgi not installed. Run: pip install serverless-wsgi"
                }
            ),
        }


if __name__ == "__main__":
    app.run(debug=True, port=5001)
