import requests
import re
import os
import json
import asyncio
from dotenv import load_dotenv

load_dotenv()

BROWSERLESS_URL = os.getenv("BROWSERLESS_URL")
BROWSERLESS_TOKEN = os.getenv("BROWSERLESS_TOKEN")

async def fetch_profile_via_browser(username):
    """
    Scrapes profile metadata using Browserless.
    """
    if not BROWSERLESS_URL: return None

    base_url = BROWSERLESS_URL.rstrip('/')
    endpoint = f"{base_url}/chromium/content"
    if BROWSERLESS_TOKEN: endpoint += f"?token={BROWSERLESS_TOKEN}"
    
    payload = {
        "url": f"https://www.instagram.com/{username}/",
        "waitForTimeout": 5000,
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "stealth": True
    }
    
    try:
        response = requests.post(endpoint, json=payload, timeout=30)
        response.raise_for_status()
        html = response.text
        
        # Look for the sharedData JSON in the HTML
        match = re.search(r'window\._sharedData\s*=\s*({.*?});', html)
        if match:
            return json.loads(match.group(1))
        
        # Alternative: look for the profile data in script tags
        match = re.search(r'"user":({.*?})', html)
        if match:
            return json.loads(match.group(1))
            
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
                        "caption": data.get("articleBody") or data.get("description") or "No caption",
                        "is_video": bool(v_url),
                        "owner_username": data.get("author", {}).get("name", "instagram_user")
                    }
            except: pass

        # 2. Try OG Tags Fallback
        v_tag = re.search(r'property="og:video" content="([^"]+)"', html)
        t_tag = re.search(r'property="og:image" content="([^"]+)"', html)
        if v_tag or t_tag:
            return {
                "shortcode": shortcode,
                "display_url": t_tag.group(1) if t_tag else None,
                "video_url": v_tag.group(1) if v_tag else None,
                "caption": "Post Media",
                "is_video": bool(v_tag),
                "owner_username": "instagram_user"
            }
            
        # 3. Final Fallback: SEO Meta Tags (via requests)
        return await scrape_via_og_tags(url)

    except Exception as e:
        print(f"Deep Scrape Error: {e}")
        return await scrape_via_og_tags(url)

async def scrape_via_og_tags(url):
    """
    Method 3: Extracts media from OpenGraph/SEO meta tags.
    """
    print("🔄 Attempting SEO Meta-Scraping fallback...")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Accept-Language": "en-US,en;q=0.9"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        html = resp.text
        
        video_match = re.search(r'property="og:video" content="([^"]+)"', html)
        image_match = re.search(r'property="og:image" content="([^"]+)"', html)
        caption_match = re.search(r'property="og:description" content="([^"]+)"', html)
        
        if video_match or image_match:
            print("✅ SEO Meta-Scraping Success!")
            return {
                "shortcode": url.split("/")[-2] if "/" in url else "post",
                "display_url": image_match.group(1) if image_match else None,
                "video_url": video_match.group(1) if video_match else None,
                "caption": caption_match.group(1) if caption_match else "No caption",
                "is_video": bool(video_match),
                "owner_username": "instagram_user"
            }
    except Exception as e:
        print(f"SEO Meta-Scraping failed: {e}")
    return None
