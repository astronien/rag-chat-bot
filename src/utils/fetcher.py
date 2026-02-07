"""
Centralized module for fetching promotions from external API.
"""
import os
import uuid
import logging
from typing import Optional, List, Dict, Any

try:
    import httpx
except ImportError:
    httpx = None

# Configuration
LOGIN_URL = "https://api.vrcomseven.com/users/web_login"
PROMOTIONS_URL = "https://api.vrcomseven.com/v1/promotions"
USERNAME = os.environ.get("VR_USERNAME", "25622")
PASSWORD = os.environ.get("VR_PASSWORD", "91544")

logger = logging.getLogger(__name__)

def login() -> Optional[str]:
    """Login via API and return access token."""
    if not httpx:
        logger.error("httpx module not found")
        return None
        
    try:
        response = httpx.post(
            LOGIN_URL,
            json={
                "emp_code": USERNAME,
                "pass": PASSWORD,
                "device_uuid": str(uuid.uuid4()),
                "platform": "web"
            },
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            token_data = data.get("data", {})
            # Handle different key names if API changes
            token = token_data.get("access_token") or token_data.get("accessToken")
            return token
        logger.error(f"Login failed: {response.status_code} {response.text}")
        return None
    except Exception as e:
        logger.error(f"Login exception: {str(e)}")
        return None

def fetch_promotions_data(token: str) -> List[Dict[str, Any]]:
    """Fetch raw promotions data using access token."""
    if not httpx:
        return []
        
    try:
        response = httpx.get(
            f"{PROMOTIONS_URL}?perpage=200&sort_by=updated_at&sort_direction=desc&business_units=Apple",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("data", [])
        logger.error(f"Fetch failed: {response.status_code} {response.text}")
        return []
    except Exception as e:
        logger.error(f"Fetch exception: {str(e)}")
        return []
