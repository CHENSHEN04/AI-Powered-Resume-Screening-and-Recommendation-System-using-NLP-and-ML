
"""
Backend utility: Supabase Auth Token Verification
"""
from fastapi import HTTPException, Header
from typing import Optional
import os

# We need the supabase client for server-side auth verification
try:
    from supabase import create_client, Client
    import streamlit as st
    
    def _get_supabase() -> Optional[Client]:
        try:
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["anon_key"]
            return create_client(url, key)
        except Exception:
            # Fallback to env vars  
            url = os.getenv("SUPABASE_URL", "")
            key = os.getenv("SUPABASE_ANON_KEY", "")
            if url and key:
                return create_client(url, key)
            return None
except ImportError:
    def _get_supabase():
        return None


async def get_user_from_token(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """
    Extract user info from Supabase JWT token.
    Returns user dict or None if not authenticated.
    Does NOT raise — endpoints can work for both auth'd and anonymous users.
    """
    if not authorization:
        return None
    
    try:
        token = authorization.replace("Bearer ", "")
        client = _get_supabase()
        if not client:
            return None
        
        # Verify token with Supabase
        user_response = client.auth.get_user(token)
        if user_response and user_response.user:
            return {
                "id": user_response.user.id,
                "email": user_response.user.email,
            }
        return None
    except Exception:
        return None


async def require_auth(authorization: Optional[str] = Header(None)) -> dict:
    """
    Require valid auth token. Raises 401 if not authenticated.
    """
    user = await get_user_from_token(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user
