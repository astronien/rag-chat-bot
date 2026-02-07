"""
Script to sync promotions data from API to local JSON file.
Usage: python scripts/sync_promotions.py
"""
import os
import sys
import json
import uuid
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import httpx
except ImportError:
    logger.error("httpx module not found. Please install it with: pip install httpx")
    sys.exit(1)

from api.promotions import process_promotions
from src.utils.fetcher import login, fetch_promotions_data as fetch_promotions

# Configuration
DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/promotions.json")

def main():
    logger.info("Starting promotion sync...")
    
    token = login()
    if not token:
        logger.error("Could not obtain access token. Aborting.")
        return
    
    logger.info("Login successful. Fetching promotions...")
    raw_promotions = fetch_promotions(token)
    
    if not raw_promotions:
        logger.error("No promotions fetched. Aborting.")
        return
    
    logger.info(f"Fetched {len(raw_promotions)} promotions. Processing...")
    processed_data = process_promotions(raw_promotions)
    
    # Save to file
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(processed_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Successfully saved {len(processed_data)} promotions to {DATA_FILE}")
    except Exception as e:
        logger.error(f"Failed to save file: {str(e)}")

if __name__ == "__main__":
    main()
