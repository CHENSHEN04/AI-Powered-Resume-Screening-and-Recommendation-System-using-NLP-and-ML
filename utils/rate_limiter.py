"""
Rate Limiter Module
===================
Implements upload rate limiting to prevent abuse and manage server resources.
"""

from datetime import datetime, timedelta
from collections import defaultdict
from typing import Tuple, Dict
import streamlit as st

# Rate limit configuration
RATE_LIMITS = {
    "anonymous": {
        "uploads_per_hour": 10,
        "uploads_per_day": 30,
        "max_file_size_mb": 10,
    },
    "authenticated": {
        "uploads_per_hour": 30,
        "uploads_per_day": 200,
        "max_file_size_mb": 15,
    }
}


class RateLimiter:
    """
    Simple in-memory rate limiter for upload protection.
    
    Note: This implementation uses session state for simplicity.
    For production, consider Redis or database-backed rate limiting.
    """
    
    def __init__(self):
        """Initialize rate limiter with session state storage."""
        if "rate_limiter_requests" not in st.session_state:
            st.session_state.rate_limiter_requests = defaultdict(list)
    
    def check_rate_limit(self, user_id: str, is_authenticated: bool) -> Tuple[bool, str]:
        """
        Check if user is within rate limits.
        
        Args:
            user_id: Unique identifier for the user (email or session ID)
            is_authenticated: Whether user is logged in
            
        Returns:
            Tuple of (is_allowed, error_message)
            - is_allowed: True if within limits, False otherwise
            - error_message: Empty string if allowed, error message otherwise
        """
        limits = RATE_LIMITS["authenticated" if is_authenticated else "anonymous"]
        now = datetime.now()
        
        # Get user's request history
        user_requests = st.session_state.rate_limiter_requests[user_id]
        
        # Clean up old requests (older than 1 day)
        day_ago = now - timedelta(days=1)
        user_requests = [r for r in user_requests if r > day_ago]
        st.session_state.rate_limiter_requests[user_id] = user_requests
        
        # Check hourly limit
        hour_ago = now - timedelta(hours=1)
        recent_hour = [r for r in user_requests if r > hour_ago]
        
        if len(recent_hour) >= limits["uploads_per_hour"]:
            wait_time = (recent_hour[0] + timedelta(hours=1) - now).seconds //60
            return False, f"⏱️ Hourly limit of {limits['uploads_per_hour']} uploads reached. Try again in {wait_time} minutes."
        
        # Check daily limit
        if len(user_requests) >= limits["uploads_per_day"]:
            next_available = (user_requests[0] + timedelta(days=1)).strftime("%I:%M %p")
            return False, f"📅 Daily limit of {limits['uploads_per_day']} uploads reached. Try again after {next_available}."
        
        # Record this request
        st.session_state.rate_limiter_requests[user_id].append(now)
        return True, ""
    
    def get_file_size_limit(self, is_authenticated: bool) -> int:
        """
        Get maximum allowed file size in bytes.
        
        Args:
            is_authenticated: Whether user is logged in
            
        Returns:
            Maximum file size in bytes
        """
        limit_mb = RATE_LIMITS["authenticated" if is_authenticated else "anonymous"]["max_file_size_mb"]
        return limit_mb * 1024 * 1024  # Convert MB to bytes
    
    def get_remaining_uploads(self, user_id: str, is_authenticated: bool) -> Dict[str, int]:
        """
        Get remaining upload quota for user.
        
        Args:
            user_id: Unique identifier for the user
            is_authenticated: Whether user is logged in
            
        Returns:
            Dictionary with remaining hourly and daily uploads
        """
        limits = RATE_LIMITS["authenticated" if is_authenticated else "anonymous"]
        now = datetime.now()
        
        user_requests = st.session_state.rate_limiter_requests.get(user_id, [])
        
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        recent_hour = [r for r in user_requests if r > hour_ago]
        recent_day = [r for r in user_requests if r > day_ago]
        
        return {
            "hourly_remaining": max(0, limits["uploads_per_hour"] - len(recent_hour)),
            "daily_remaining": max(0, limits["uploads_per_day"] - len(recent_day)),
            "hourly_limit": limits["uploads_per_hour"],
            "daily_limit": limits["uploads_per_day"]
        }
    
    @staticmethod
    def reset_limits():
        """Reset all rate limits (for testing/admin purposes)."""
        if "rate_limiter_requests" in st.session_state:
            st.session_state.rate_limiter_requests = defaultdict(list)


def show_rate_limit_info(user_id: str, is_authenticated: bool):
    """
    Display rate limit information to user.
    
    Args:
        user_id: Unique identifier for the user
        is_authenticated: Whether user is logged in
    """
    limiter = RateLimiter()
    remaining = limiter.get_remaining_uploads(user_id, is_authenticated)
    
    user_type = "Authenticated" if is_authenticated else "Anonymous"
    
    st.caption(
        f"📊 Upload Quota ({user_type}): "
        f"{remaining['hourly_remaining']}/{remaining['hourly_limit']} per hour, "
        f"{remaining['daily_remaining']}/{remaining['daily_limit']} per day"
    )
