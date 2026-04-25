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

async def scrape_post_with_browser(url, cookies=None):
    """
    Deep Scrape: Uses Browserless with session injection to bypass login walls.
    """
    if not BROWSERLESS_URL: return None

    base_url = BROWSERLESS_URL.rstrip('/')
    endpoint = f"{base_url}/chromium/content"
    if BROWSERLESS_TOKEN: endpoint += f"?token={BROWSERLESS_TOKEN}"
    
    payload = {
        "url": url,
        "waitForTimeout": 10000,
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "cookies": cookies if cookies else [],
        "stealth": True,
        "actions": [
            {"type": "scroll", "offset": 200},
            {"type": "wait", "duration": 1000},
            {"type": "scroll", "offset": -200}
        ]
    }
    
    try:
        response = requests.post(endpoint, json=payload, timeout=50)
        response.raise_for_status()
        html = response.text
        
        # Extract shortcode
        match = re.search(r'/(?:p|reels|reel)/([^/?#&]+)', url)
        shortcode = match.group(1) if match else "unknown"
        is_reel = "/reels/" in url or "/reel/" in url

        # 1. Try JSON-LD (Best quality)
        ld_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
        if ld_match:
            try:
                data = json.loads(ld_match.group(1))
                if isinstance(data, list): data = data[0]
                
                v_url = data.get("contentUrl")
                t_url = data.get("thumbnailUrl") or data.get("image")
                
                if v_url or t_url:
                    return {
                        "shortcode": shortcode,
                        "display_url": t_url,
                        "video_url": v_url,
                        "caption": data.get("description", ""),
                        "likes": 0,
                        "comments": 0,
                        "owner_username": data.get("author", {}).get("alternateName", "instagram_user"),
                        "timestamp": data.get("uploadDate", ""),
                        "is_video": bool(v_url) or is_reel
                    }
            except: pass

        # 2. Try OG Tags (Fallback)
        v_url = re.search(r'<meta property="og:video" content="(.*?)"', html)
        t_url = re.search(r'<meta property="og:image" content="(.*?)"', html)
        desc = re.search(r'<meta property="og:description" content="(.*?)"', html)
        
        if v_url or t_url:
            return {
                "shortcode": shortcode,
                "display_url": t_url.group(1) if t_url else "",
                "video_url": v_url.group(1) if v_url else None,
                "caption": desc.group(1) if desc else "",
                "likes": 0,
                "comments": 0,
                "owner_username": "instagram_user",
                "timestamp": "",
                "is_video": bool(v_url) or is_reel
            }

        # 3. Final desperation: Look for raw video/image tags in HTML
        if is_reel:
            raw_v = re.search(r'video.*src="(https://[^"]+)"', html)
            if raw_v:
                return {
                    "shortcode": shortcode,
                    "display_url": "",
                    "video_url": raw_v.group(1),
                    "caption": "",
                    "likes": 0,
                    "comments": 0,
                    "owner_username": "instagram_user",
                    "timestamp": "",
                    "is_video": True
                }

        return None
    except Exception as e:
        print(f"Deep Scrape Error: {e}")
        return None
