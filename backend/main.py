# Serverless-compatible version of main.py
from flask import Flask, request, jsonify, render_template, make_response
from flask_cors import CORS
import requests
from requests.exceptions import JSONDecodeError as RequestsJSONDecodeError
import json
import re
import time as time_module
from datetime import datetime, time
from typing import Dict, Any, List, Optional
from .auth import AuthManager, MonitoringManager, require_auth, optional_auth
import os
from dotenv import load_dotenv
from datetime import timedelta

# Load environment variables
load_dotenv()

# --- Flask App Setup ---
app = Flask(__name__)
# Allow overriding CORS origins for Vercel deployments via env var CORS_ORIGINS (comma-separated)
_allowed_origins_env = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://localhost:5000,http://localhost:5001",
)
allowed_origins = [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
CORS(
    app,
    origins=allowed_origins,
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
ROOM_CATALOG_CACHE_TTL_SECONDS = 60 * 15
_room_catalog_cache: Dict[str, Any] = {
    "updated_at": 0,
    "catalog": None,
}


# --- Helper Functions ---
def is_valid_room_number(room_id):
    """
    Check if a room identifier is a valid positive numeric ID.

    The live Baruch API currently returns 6-digit numeric IDs (e.g., 142254),
    so filtering to 3-4 digit room numbers prevents all bookings.
    
    Args:
        room_id: The room ID to validate (can be int or string)
    
    Returns:
        bool: True if room number is valid, False otherwise
    """
    try:
        room_num = int(room_id)
        return room_num > 0
    except (ValueError, TypeError):
        return False


def determine_slot_availability(slot):
    """
    Determine if a slot is available for booking.

    Slots with a className property are considered unavailable for booking.
    Only slots with essential fields AND no className are considered bookable.

    Args:
        slot (dict): The slot object from the external API

    Returns:
        bool: True if slot is available for booking, False otherwise
    """
    # Check that essential fields exist for booking attempts
    has_essential_fields = all(field in slot for field in ["checksum", "itemId", "start", "end"])
    
    # Slots with className are considered unavailable (e.g., "s-lc-eq-pending")
    has_no_class_name = "className" not in slot or not slot["className"]
    
    return has_essential_fields and has_no_class_name


def normalize_start_time(start_time_raw):
    """
    Normalize client-provided start times to HH:MM.

    Accepts:
    - HH:MM
    - HH:MM:SS
    - YYYY-MM-DD HH:MM:SS
    """
    if not isinstance(start_time_raw, str) or not start_time_raw.strip():
        raise ValueError("Invalid startTime format. Expected HH:MM or HH:MM:SS.")

    start_time = start_time_raw.strip()

    if re.match(r"^\d{2}:\d{2}$", start_time):
        return start_time

    if re.match(r"^\d{2}:\d{2}:\d{2}$", start_time):
        return start_time[:5]

    if re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", start_time):
        return datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S").strftime("%H:%M")

    raise ValueError("Invalid startTime format. Expected HH:MM or HH:MM:SS.")


def _decode_js_escaped_string(value: str) -> str:
    """Decode JS-escaped strings embedded in HTML script blocks."""
    try:
        return bytes(value, "utf-8").decode("unicode_escape")
    except Exception:
        return value


def get_room_catalog(force_refresh: bool = False):
    """
    Fetch room metadata from the public spaces page.

    This provides a deterministic mapping between user-facing room numbers and
    internal equipment IDs (eid/itemId) used by booking APIs.
    """
    now = int(time_module.time())
    cached_catalog = _room_catalog_cache.get("catalog")
    cache_age = now - int(_room_catalog_cache.get("updated_at", 0))

    if (
        not force_refresh
        and cached_catalog is not None
        and cache_age < ROOM_CATALOG_CACHE_TTL_SECONDS
    ):
        return cached_catalog

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/spaces?lid={LID}&gid={GID}",
        }
    )

    response = session.get(f"{BASE_URL}/spaces?lid={LID}&gid={GID}", timeout=30)
    response.raise_for_status()
    html_body = response.text

    resource_pattern = re.compile(
        r'resources\.push\(\{\s*id:\s*"eid_(\d+)".*?title:\s*"([^"]+)".*?capacity:\s*(\d+)',
        re.DOTALL,
    )

    id_to_room: Dict[str, Dict[str, Any]] = {}
    room_number_to_ids: Dict[str, List[str]] = {}

    for match in resource_pattern.finditer(html_body):
        internal_id = match.group(1)
        title_raw = match.group(2)
        capacity = int(match.group(3))
        display_name = _decode_js_escaped_string(title_raw)

        room_number_match = re.search(r"Room\s+(\d+)", display_name, re.IGNORECASE)
        room_number = room_number_match.group(1) if room_number_match else None

        room_entry = {
            "internal_id": internal_id,
            "room_number": room_number,
            "display_name": display_name,
            "capacity": capacity,
        }
        id_to_room[internal_id] = room_entry

        if room_number:
            room_number_to_ids.setdefault(room_number, []).append(internal_id)

    catalog = {
        "rooms": sorted(
            id_to_room.values(),
            key=lambda room: (
                int(room["room_number"]) if room["room_number"] and room["room_number"].isdigit() else 999999,
                room["display_name"],
            ),
        ),
        "id_to_room": id_to_room,
        "room_number_to_ids": room_number_to_ids,
        "fetched_at": datetime.utcnow().isoformat(),
    }

    _room_catalog_cache["updated_at"] = now
    _room_catalog_cache["catalog"] = catalog
    return catalog


def normalize_room_preferences(payload: Dict[str, Any], room_catalog: Dict[str, Any]):
    """Resolve requested room inputs (room number or internal ID) to internal IDs."""
    requested_values: List[str] = []

    room_preferences = payload.get("roomPreferences")
    if isinstance(room_preferences, list):
        requested_values.extend(str(value).strip() for value in room_preferences if str(value).strip())

    room_preference = payload.get("roomPreference")
    if room_preference is not None and str(room_preference).strip():
        requested_values.append(str(room_preference).strip())

    room_numbers = payload.get("roomNumbers")
    if isinstance(room_numbers, list):
        requested_values.extend(str(value).strip() for value in room_numbers if str(value).strip())

    if not requested_values:
        return {
            "resolved_room_ids": [],
            "resolved_labels": [],
            "invalid_inputs": [],
        }

    id_to_room = room_catalog.get("id_to_room", {})
    room_number_to_ids = room_catalog.get("room_number_to_ids", {})

    resolved_room_ids: List[str] = []
    invalid_inputs: List[str] = []

    for raw_value in requested_values:
        if raw_value in id_to_room:
            resolved_room_ids.append(raw_value)
            continue

        if raw_value in room_number_to_ids:
            resolved_room_ids.extend(room_number_to_ids[raw_value])
            continue

        invalid_inputs.append(raw_value)

    # Keep order stable and remove duplicates.
    deduped_room_ids = list(dict.fromkeys(resolved_room_ids))
    resolved_labels = [
        id_to_room[room_id]["display_name"]
        for room_id in deduped_room_ids
        if room_id in id_to_room
    ]

    return {
        "resolved_room_ids": deduped_room_ids,
        "resolved_labels": resolved_labels,
        "invalid_inputs": invalid_inputs,
    }


def get_request_room_preferences(request_doc: Dict[str, Any]):
    """Normalize room preference storage format for old and new monitoring docs."""
    room_preferences = request_doc.get("room_preferences")
    if isinstance(room_preferences, list):
        return [str(room_id) for room_id in room_preferences if str(room_id).strip()]

    room_preference = request_doc.get("room_preference")
    if room_preference is None:
        return []

    room_preference_value = str(room_preference).strip()
    return [room_preference_value] if room_preference_value else []


def get_update_checksum_for_target_end(first_booking: Dict[str, Any], target_end: str):
    """
    Select update checksum by matching the target end time to provided booking options.

    This avoids guessing checksum indices when optionChecksums cardinality varies.
    """
    options = first_booking.get("options") or []
    option_checksums = first_booking.get("optionChecksums") or []

    if not options or not option_checksums:
        return None

    target_no_seconds = target_end[:16]

    for index, option in enumerate(options):
        if index >= len(option_checksums):
            continue

        if isinstance(option, dict):
            end_candidate = str(option.get("end") or option.get("value") or option.get("time") or "")
        else:
            end_candidate = str(option)

        if not end_candidate:
            continue

        if target_end in end_candidate or target_no_seconds in end_candidate:
            return option_checksums[index]

    return None


def find_consecutive_slots(
    slots_by_room, start_time, duration_hours, date_str, preferred_room_ids=None
):
    """
    Find consecutive available slots for the requested time duration.
    Only considers rooms with valid positive numeric IDs.

    Args:
        slots_by_room (dict): Dictionary of room_id -> list of slots
        start_time (str): Start time in HH:MM format
        duration_hours (int): Duration in hours
        date_str (str): Date in YYYY-MM-DD format

        preferred_room_ids (list|None): Optional ordered room IDs to restrict search to

    Returns:
        list: List of consecutive slots, or empty list if none found
    """
    from datetime import datetime, timedelta

    # Parse start time
    start_dt = datetime.strptime(f"{date_str} {start_time}", "%Y-%m-%d %H:%M")

    if duration_hours <= 0:
        return []

    rooms_to_check = list(slots_by_room.items())
    if preferred_room_ids:
        normalized_ids = preferred_room_ids
        if not isinstance(preferred_room_ids, list):
            normalized_ids = [preferred_room_ids]

        filtered_rooms = []
        for preferred_room_id in normalized_ids:
            preferred_room_key = str(preferred_room_id)
            preferred_slots = slots_by_room.get(preferred_room_key)

            # Fallback for integer-key dictionaries (if any)
            if preferred_slots is None:
                try:
                    preferred_slots = slots_by_room.get(int(preferred_room_id))
                except (TypeError, ValueError):
                    preferred_slots = None

            if preferred_slots is not None:
                filtered_rooms.append((preferred_room_key, preferred_slots))

        if not filtered_rooms:
            return []

        rooms_to_check = filtered_rooms

    # Search through candidate rooms for consecutive slots
    for room_id, slots in rooms_to_check:
        # Skip rooms with non-numeric/invalid IDs
        if not is_valid_room_number(room_id):
            continue
            
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

        # Filter out rooms that are fully available (all slots open = likely a data issue)
        filtered_slots_by_room = {}
        for room_id, slots in slots_by_room.items():
            available_count = sum(1 for s in slots if s.get("available", False))
            # If all slots are available, this room is likely not actually bookable
            if available_count < len(slots):
                filtered_slots_by_room[room_id] = slots
        
        return filtered_slots_by_room

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
            max_age=36500 * 24 * 60 * 60,  # Never expire (100 years)
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


@app.route("/api/rooms", methods=["GET"])
def get_rooms_catalog():
    """Return room metadata mapping between internal IDs and display room numbers."""
    try:
        force_refresh = str(request.args.get("refresh", "false")).lower() == "true"
        catalog = get_room_catalog(force_refresh=force_refresh)
        return jsonify(
            {
                "rooms": catalog.get("rooms", []),
                "fetched_at": catalog.get("fetched_at"),
            }
        )
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to fetch rooms catalog: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": f"Failed to parse rooms catalog: {str(e)}"}), 500


@app.route("/api/book", methods=["POST"])
@optional_auth(auth_manager)
def book_room():
    data = request.json
    print(f"Received booking request: {data}")

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

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

    # Resolve requested room inputs (clean room numbers and/or internal room IDs)
    try:
        room_catalog = get_room_catalog()
        room_preferences = normalize_room_preferences(data, room_catalog)
    except Exception as e:
        return jsonify({"error": f"Failed to resolve room preferences: {str(e)}"}), 500

    if room_preferences["invalid_inputs"]:
        return (
            jsonify(
                {
                    "error": "Invalid room preferences provided",
                    "invalid": room_preferences["invalid_inputs"],
                    "hint": "Use room numbers (e.g. 342) or internal IDs from /api/rooms",
                }
            ),
            400,
        )

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
    try:
        start_time = normalize_start_time(data["startTime"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # Calculate end time
    start_dt = datetime.strptime(f"{data['date']} {start_time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(hours=duration_hours)
    end_time = end_dt.strftime("%H:%M")

    # Find consecutive slots for the requested duration
    target_slots = find_consecutive_slots(
        slots_by_room,
        start_time,
        duration_hours,
        data["date"],
        preferred_room_ids=room_preferences["resolved_room_ids"],
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

        update_checksum = get_update_checksum_for_target_end(
            first_booking, second_slot["end"]
        )
        if not update_checksum:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Could not determine update checksum for second-hour extension from booking options.",
                        "details": {
                            "option_checksums_count": len(
                                first_booking.get("optionChecksums") or []
                            ),
                            "options_count": len(first_booking.get("options") or []),
                        },
                    }
                ),
                409,
            )
        
        # Use update URL instead of add URL for the second slot
        update_url = f"{BASE_URL}/spaces/availability/booking/add"
        update_payload = {
            "update[id]": first_booking["id"],
            "update[checksum]": update_checksum,
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
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

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

    try:
        room_catalog = get_room_catalog()
        room_preferences = normalize_room_preferences(data, room_catalog)
    except Exception as e:
        return jsonify({"error": f"Failed to resolve room preferences: {str(e)}"}), 500

    if room_preferences["invalid_inputs"]:
        return (
            jsonify(
                {
                    "error": "Invalid room preferences provided",
                    "invalid": room_preferences["invalid_inputs"],
                    "hint": "Use room numbers (e.g. 342) or internal IDs from /api/rooms",
                }
            ),
            400,
        )

    # Calculate end time from start time and duration
    try:
        start_time = normalize_start_time(data["startTime"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

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
        room_preference=room_preferences["resolved_room_ids"][0]
        if room_preferences["resolved_room_ids"]
        else None,
        room_preferences=room_preferences["resolved_room_ids"],
        room_preference_labels=room_preferences["resolved_labels"],
    )

    if result["success"]:
        return (
            jsonify(
                {
                    "success": True,
                    "request_id": result["request_id"],
                    "room_preferences": room_preferences["resolved_room_ids"],
                    "room_preference_labels": room_preferences["resolved_labels"],
                    "message": f"Monitoring request created for {data['date']} {start_time}-{end_time} ({duration_hours} hours). Use external scheduler to check periodically.",
                }
            ),
            201,
        )
    else:
        return jsonify(result), 500




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
            preferred_room_ids=get_request_room_preferences(request_doc),
        )

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

            update_checksum = get_update_checksum_for_target_end(
                first_booking, second_slot["end"]
            )
            if not update_checksum:
                error_msg = "Could not determine update checksum for second-hour extension from booking options."
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
            
            # Use update URL instead of add URL for the second slot
            update_url = f"{BASE_URL}/spaces/availability/booking/add"
            update_payload = {
                "update[id]": first_booking["id"],
                "update[checksum]": update_checksum,
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


@app.route("/api/monitoring/check-all", methods=["GET"])
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
                preferred_room_ids=get_request_room_preferences(request_doc),
            )

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
                error_msg = f"Invalid response from booking system for first slot. Response: {add_res.text[:500]}"
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
                error_msg = f"No bookings returned for first slot. Response: {add_response_data}"
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

                update_checksum = get_update_checksum_for_target_end(
                    first_booking, second_slot["end"]
                )
                if not update_checksum:
                    error_msg = "Could not determine update checksum for second-hour extension from booking options."
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
                
                # Use update URL instead of add URL for the second slot
                update_url = f"{BASE_URL}/spaces/availability/booking/add"
                update_payload = {
                    "update[id]": first_booking["id"],
                    "update[checksum]": update_checksum,
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
            'statusCode': 500,
            'body': 'serverless-wsgi not installed. Install with: pip install serverless-wsgi'
        }

@app.route("/api/monitoring/test-check", methods=["POST"])
def test_monitoring_check():
    """
    Manually trigger a monitoring check for testing purposes.
    This is useful for testing the monitoring system without waiting for the scheduler.
    """
    try:
        # Call the same function that the scheduler would call
        return check_all_monitoring_requests()
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error during test check: {str(e)}"
        }), 500

if __name__ == "__main__":
    app.run(debug=True, port=5001)
