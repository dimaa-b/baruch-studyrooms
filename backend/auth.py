"""
Authentication module for Flask app with MongoDB backend
Provides user registration, login, logout, and session management
"""

import bcrypt
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, make_response
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
import re

class AuthManager:
    def __init__(self, mongo_uri, db_name="baruch_studyrooms"):
        """Initialize the authentication manager with MongoDB connection"""
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.client = None
        self.db = None
        self.users = None
        self.sessions = None
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Initialize MongoDB connection and collections"""
        try:
            # Add SSL certificate verification bypass for development
            self.client = MongoClient(
                self.mongo_uri, 
                serverSelectionTimeoutMS=5000,
                tlsAllowInvalidCertificates=True  # For development only
            )
            # Test the connection
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            self.users = self.db.users
            self.sessions = self.db.sessions
            
            # Create indexes for better performance
            self.users.create_index("email", unique=True)
            self.users.create_index("username", unique=True)
            self.sessions.create_index("token", unique=True)
            self.sessions.create_index("expires_at", expireAfterSeconds=0)
            
            print("MongoDB connection established successfully")
        except Exception as e:
            print(f"Warning: MongoDB connection failed: {e}")
            print("Authentication features will be disabled")
    
    def _ensure_connection(self):
        """Ensure MongoDB connection is available"""
        if self.client is None:
            self._initialize_connection()
        if self.client is None:
            raise Exception("MongoDB connection not available")
    
    def validate_email(self, email):
        """Validate email format and ensure it's a Baruch/CUNY email"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@(baruchmail\.cuny\.edu|spsmail\.cuny\.edu)$'
        return re.match(email_pattern, email) is not None
    
    def validate_password(self, password):
        """Validate password strength - simplified for minimal friction"""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        return True, "Password is valid"
    
    def hash_password(self, password):
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt)
    
    def verify_password(self, password, hashed):
        """Verify a password against its hash"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed)
    
    def generate_session_token(self):
        """Generate a secure random session token"""
        return secrets.token_urlsafe(32)
    
    def register_user(self, email, password, first_name, last_name):
        """Register a new user"""
        try:
            self._ensure_connection()
        except Exception as e:
            return {"success": False, "message": f"Database connection error: {str(e)}"}
        
        # Validate email
        if not self.validate_email(email):
            return {"success": False, "message": "Invalid email. Must be a Baruch or CUNY SPS email address."}
        
        # Generate username from email (part before @)
        username = email.split('@')[0]
        
        # Validate password
        is_valid, message = self.validate_password(password)
        if not is_valid:
            return {"success": False, "message": message}
        
        # Check if user already exists
        if self.users.find_one({"email": email}):
            return {"success": False, "message": "User with this email already exists"}
        
        # Check if auto-generated username conflicts (unlikely but possible)
        counter = 1
        original_username = username
        while self.users.find_one({"username": username}):
            username = f"{original_username}{counter}"
            counter += 1
        
        try:
            # Create new user
            user_doc = {
                "email": email,
                "username": username,
                "password": self.hash_password(password),
                "first_name": first_name,
                "last_name": last_name,
                "created_at": datetime.utcnow(),
                "last_login": None,
                "is_active": True
            }
            
            self.users.insert_one(user_doc)
            return {"success": True, "message": "User registered successfully"}
            
        except DuplicateKeyError:
            return {"success": False, "message": "User with this email or username already exists"}
        except Exception as e:
            return {"success": False, "message": f"Registration failed: {str(e)}"}
    
    def login_user(self, email_or_username, password):
        """Authenticate user and create session"""
        try:
            self._ensure_connection()
        except Exception as e:
            return {"success": False, "message": f"Database connection error: {str(e)}"}
        
        # Find user by email or username
        user = self.users.find_one({
            "$or": [
                {"email": email_or_username},
                {"username": email_or_username}
            ]
        })
        
        if not user:
            return {"success": False, "message": "Invalid credentials"}
        
        if not user.get("is_active", False):
            return {"success": False, "message": "Account is disabled"}
        
        # Verify password
        if not self.verify_password(password, user["password"]):
            return {"success": False, "message": "Invalid credentials"}
        
        # Create session
        session_token = self.generate_session_token()
        expires_at = datetime.utcnow() + timedelta(days=7)  # 7 day session
        
        session_doc = {
            "token": session_token,
            "user_id": user["_id"],
            "email": user["email"],
            "username": user["username"],
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
            "last_activity": datetime.utcnow()
        }
        
        self.sessions.insert_one(session_doc)
        
        # Update last login
        self.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"last_login": datetime.utcnow()}}
        )
        
        return {
            "success": True,
            "message": "Login successful",
            "token": session_token,
            "user": {
                "id": str(user["_id"]),
                "email": user["email"],
                "username": user["username"],
                "first_name": user["first_name"],
                "last_name": user["last_name"]
            },
            "expires_at": expires_at.isoformat()
        }
    
    def logout_user(self, session_token):
        """Logout user by invalidating session"""
        try:
            self._ensure_connection()
            result = self.sessions.delete_one({"token": session_token})
            return {"success": result.deleted_count > 0, "message": "Logged out successfully"}
        except Exception as e:
            return {"success": False, "message": f"Logout failed: {str(e)}"}
    
    def get_user_from_session(self, session_token):
        """Get user information from session token"""
        if not session_token:
            return None
        
        try:
            self._ensure_connection()
        except Exception as e:
            print(f"Database connection error: {e}")
            return None
        
        session = self.sessions.find_one({
            "token": session_token,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        if not session:
            return None
        
        # Update last activity
        self.sessions.update_one(
            {"token": session_token},
            {"$set": {"last_activity": datetime.utcnow()}}
        )
        
        # Get full user info
        user = self.users.find_one({"_id": session["user_id"]})
        if not user or not user.get("is_active", False):
            return None
        
        return {
            "id": str(user["_id"]),
            "email": user["email"],
            "username": user["username"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "session_token": session_token
        }
    
    def refresh_session(self, session_token):
        """Refresh session expiration"""
        try:
            self._ensure_connection()
            new_expires_at = datetime.utcnow() + timedelta(days=7)
            result = self.sessions.update_one(
                {"token": session_token, "expires_at": {"$gt": datetime.utcnow()}},
                {"$set": {"expires_at": new_expires_at, "last_activity": datetime.utcnow()}}
            )
            
            if result.modified_count > 0:
                return {"success": True, "expires_at": new_expires_at.isoformat()}
            return {"success": False, "message": "Session not found or expired"}
        except Exception as e:
            return {"success": False, "message": f"Session refresh failed: {str(e)}"}
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions (called automatically by MongoDB TTL)"""
        try:
            self._ensure_connection()
            result = self.sessions.delete_many({"expires_at": {"$lt": datetime.utcnow()}})
            return result.deleted_count
        except Exception as e:
            print(f"Session cleanup failed: {e}")
            return 0

def require_auth(auth_manager):
    """Decorator to require authentication for routes"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check for session token in cookies or headers
            session_token = request.cookies.get('session_token') or request.headers.get('Authorization')
            
            if session_token and session_token.startswith('Bearer '):
                session_token = session_token[7:]  # Remove 'Bearer ' prefix
            
            user = auth_manager.get_user_from_session(session_token)
            if not user:
                return jsonify({"error": "Authentication required", "authenticated": False}), 401
            
            # Add user info to request context
            request.current_user = user
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def optional_auth(auth_manager):
    """Decorator to optionally include user info if authenticated"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check for session token in cookies or headers
            session_token = request.cookies.get('session_token') or request.headers.get('Authorization')
            
            if session_token and session_token.startswith('Bearer '):
                session_token = session_token[7:]  # Remove 'Bearer ' prefix
            
            user = auth_manager.get_user_from_session(session_token)
            request.current_user = user  # Will be None if not authenticated
            return f(*args, **kwargs)
        return decorated_function
    return decorator

class MonitoringManager:
    def __init__(self, mongo_uri, db_name="baruch_studyrooms"):
        """Initialize the monitoring manager with MongoDB connection"""
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.client = None
        self.db = None
        self.monitoring_requests = None
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Initialize MongoDB connection and collections"""
        try:
            self.client = MongoClient(
                self.mongo_uri, 
                serverSelectionTimeoutMS=5000,
                tlsAllowInvalidCertificates=True
            )
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            self.monitoring_requests = self.db.monitoring_requests
            
            # Create indexes for better performance
            self.monitoring_requests.create_index("user_id")
            self.monitoring_requests.create_index("status")
            self.monitoring_requests.create_index("target_date")
            self.monitoring_requests.create_index("created_at")
            self.monitoring_requests.create_index("expires_at", expireAfterSeconds=0)
            
            print("MongoDB monitoring connection established successfully")
        except Exception as e:
            print(f"Warning: MongoDB monitoring connection failed: {e}")
    
    def _ensure_connection(self):
        """Ensure MongoDB connection is available"""
        if self.client is None:
            self._initialize_connection()
        if self.client is None:
            raise Exception("MongoDB connection not available")
    
    def create_monitoring_request(self, user_id, email, first_name, last_name, target_date, start_time, end_time, room_preference=None):
        """Create a new monitoring request"""
        try:
            self._ensure_connection()
        except Exception as e:
            return {"success": False, "message": f"Database connection error: {str(e)}"}
        
        # Generate unique request ID
        request_id = f"{target_date}_{start_time}-{end_time}_{datetime.utcnow().timestamp()}"
        
        # Set expiration (monitoring expires at end of target date)
        target_datetime = datetime.strptime(target_date, "%Y-%m-%d")
        expires_at = target_datetime + timedelta(days=1)  # Expire at end of target date
        
        monitoring_doc = {
            "request_id": request_id,
            "user_id": user_id,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "target_date": target_date,
            "start_time": start_time,
            "end_time": end_time,
            "room_preference": room_preference,
            "status": "active",  # active, completed, stopped, expired, error
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
            "last_check": None,
            "check_count": 0,
            "success_details": None,
            "error_message": None
        }
        
        try:
            self.monitoring_requests.insert_one(monitoring_doc)
            return {
                "success": True,
                "request_id": request_id,
                "message": f"Monitoring request created for {target_date} {start_time}-{end_time}"
            }
        except Exception as e:
            return {"success": False, "message": f"Failed to create monitoring request: {str(e)}"}
    
    def get_monitoring_request(self, request_id):
        """Get a specific monitoring request by ID"""
        try:
            self._ensure_connection()
            request_doc = self.monitoring_requests.find_one({"request_id": request_id})
            if request_doc:
                # Convert ObjectId to string
                request_doc["_id"] = str(request_doc["_id"])
                return request_doc
            return None
        except Exception as e:
            print(f"Error getting monitoring request: {e}")
            return None
    
    def update_monitoring_status(self, request_id, status, success_details=None, error_message=None):
        """Update the status of a monitoring request"""
        try:
            self._ensure_connection()
            update_data = {
                "status": status,
                "last_check": datetime.utcnow()
            }
            
            if success_details:
                update_data["success_details"] = success_details
            if error_message:
                update_data["error_message"] = error_message
            
            result = self.monitoring_requests.update_one(
                {"request_id": request_id},
                {"$set": update_data, "$inc": {"check_count": 1}}
            )
            
            return result.modified_count > 0
        except Exception as e:
            print(f"Error updating monitoring status: {e}")
            return False
    
    def get_active_monitoring_requests(self):
        """Get all active monitoring requests"""
        try:
            self._ensure_connection()
            requests = list(self.monitoring_requests.find({"status": "active"}))
            # Convert ObjectIds to strings
            for req in requests:
                req["_id"] = str(req["_id"])
            return requests
        except Exception as e:
            print(f"Error getting active monitoring requests: {e}")
            return []
    
    def get_user_monitoring_requests(self, user_id):
        """Get all monitoring requests for a specific user"""
        try:
            self._ensure_connection()
            requests = list(self.monitoring_requests.find(
                {"user_id": user_id}
            ).sort("created_at", -1))
            # Convert ObjectIds to strings
            for req in requests:
                req["_id"] = str(req["_id"])
            return requests
        except Exception as e:
            print(f"Error getting user monitoring requests: {e}")
            return []
    
    def stop_monitoring_request(self, request_id, user_id=None):
        """Stop a monitoring request"""
        try:
            self._ensure_connection()
            query = {"request_id": request_id, "status": "active"}
            if user_id:
                query["user_id"] = user_id  # Ensure user can only stop their own requests
            
            result = self.monitoring_requests.update_one(
                query,
                {"$set": {"status": "stopped", "last_check": datetime.utcnow()}}
            )
            
            return result.modified_count > 0
        except Exception as e:
            print(f"Error stopping monitoring request: {e}")
            return False
    
    def cleanup_expired_requests(self):
        """Remove expired monitoring requests (called automatically by MongoDB TTL)"""
        try:
            self._ensure_connection()
            result = self.monitoring_requests.delete_many({"expires_at": {"$lt": datetime.utcnow()}})
            return result.deleted_count
        except Exception as e:
            print(f"Monitoring cleanup failed: {e}")
            return 0
