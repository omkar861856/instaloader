import requests
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

BROWSERLESS_URL = os.getenv("BROWSERLESS_URL")
BROWSERLESS_TOKEN = os.getenv("BROWSERLESS_TOKEN")

def fetch_profile_via_browser(username):
    """
    Uses Browserless to fetch the Instagram profile page and extract metadata.
    This bypasses simple HTTP blocks (403).
    """
    if not BROWSERLESS_URL:
        return None

    # Browserless /chromium/content endpoint with token
    base_url = BROWSERLESS_URL.rstrip('/')
    endpoint = f"{base_url}/chromium/content"
    
    if BROWSERLESS_TOKEN:
        endpoint += f"?token={BROWSERLESS_TOKEN}"
    
    url = f"https://www.instagram.com/{username}/"
    
    payload = {
        "url": url,
        "waitForTimeout": 5000,
        "userAgent": {
            "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
        "bestAttempt": True
    }
    
    try:
        response = requests.post(endpoint, json=payload, timeout=40)
        
        if response.status_code == 401:
            print(f"Browserless returned 401 Unauthorized.")
            return {"username": username, "error": "Invalid Browserless Token.", "status": "Unauthorized"}
            
        response.raise_for_status()
        html = response.text
        
        # Fallback metadata object
        metadata = {
            "username": username,
            "full_name": username,
            "biography": "Metadata extraction failed, but profile was reached.",
            "profile_pic": "https://www.instagram.com/static/images/anonymousUser.jpg/23e032d91a84.jpg",
            "followers": 0,
            "following": 0,
            "posts": 0,
            "is_private": False
        }

        # 1. Try to find the title (usually has name and follower count)
        # Example: "Nike (@nike) • Instagram photos and videos"
        title_match = re.search(r'<title>(.*?)</title>', html)
        if title_match:
            title = title_match.group(1)
            if "@" in title:
                metadata["full_name"] = title.split(" (@")[0]

        # 2. Try LD+JSON (the most reliable source)
        ld_json = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
        if ld_json:
            try:
                data = json.loads(ld_json.group(1))
                if isinstance(data, list): data = data[0]
                
                metadata["full_name"] = data.get("name", metadata["full_name"])
                metadata["biography"] = data.get("description", metadata["biography"])
                metadata["profile_pic"] = data.get("image", metadata["profile_pic"])
                
                main_entity = data.get("mainEntityofPage", {}).get("interactionStatistic", [])
                for stat in main_entity:
                    if stat.get("interactionType") == "http://schema.org/WriteAction":
                        metadata["posts"] = stat.get("userInteractionCount", 0)
                    elif stat.get("interactionType") == "http://schema.org/SubscribeAction":
                        metadata["followers"] = stat.get("userInteractionCount", 0)
                
                return metadata
            except: pass

        # 3. Check for specific "Page Not Found" indicators
        if "Page Not Found" in html or "isn't available" in html:
            return None
            
        # Return what we have
        return metadata
        
    except Exception as e:
        print(f"Browserless error: {e}")
        return None
        
    except Exception as e:
        print(f"Browserless error: {e}")
        return None
