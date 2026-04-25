import instaloader
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel
import os
import requests
import re
from browser_service import fetch_profile_via_browser
from llm_service import analyze_profile_niche
from fileflows_service import list_fileflows_media, trigger_fileflows_process
from dotenv import load_dotenv

load_dotenv()

from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi import Depends, status
import secrets

app = FastAPI()
security = HTTPBasic()

def authenticate_admin(credentials: HTTPBasicCredentials = Depends(security)):
    is_username_correct = secrets.compare_digest(credentials.username, "admin")
    is_password_correct = secrets.compare_digest(credentials.password, "admin")
    if not (is_username_correct and is_password_correct):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Load Session
L = instaloader.Instaloader()
INSTA_SESSION = os.getenv("INSTAGRAM_SESSION_ID")

try:
    if INSTA_SESSION:
        # Direct injection from .env (The most reliable method)
        L.context._session.cookies.set("sessionid", INSTA_SESSION, domain=".instagram.com")
        print("✅ Success: Using Master Session ID from .env")
    elif os.path.exists("session-admin"):
        L.load_session_from_file("admin", "session-admin")
        print("✅ Success: Instagram session loaded from 'session-admin'.")
    else:
        print("⚠️ Warning: No session found. App is running in Guest mode.")
except Exception as e:
    print(f"❌ Session Load Error: {e}")

FILEFLOWS_URL = os.getenv("FILEFLOWS_URL")

# Allow CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure storage directory exists
os.makedirs("ui/downloads", exist_ok=True)

# --- API ENDPOINTS ---

@app.get("/api/profile/{username}")
async def get_profile(username: str):
    username = username.strip().replace(" ", "")
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        return {
            "username": profile.username,
            "full_name": profile.full_name,
            "biography": profile.biography,
            "profile_pic": profile.profile_pic_url,
            "followers": profile.followers,
            "following": profile.followees,
            "posts_count": profile.mediacount,
            "is_private": profile.is_private
        }
    except Exception as e:
        # Fallback to Browserless if blocked or 404
        print(f"Instaloader failed for {username}, falling back to Browserless: {e}")
        browser_data = fetch_profile_via_browser(username)
        if browser_data:
            return browser_data
        raise HTTPException(status_code=404, detail="Profile not found or blocked")

@app.get("/api/profile/{username}/posts")
async def get_profile_posts(username: str, offset: int = 0, limit: int = 12):
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        posts_iterator = profile.get_posts()
        
        # Simple pagination using islice
        from itertools import islice
        posts = []
        for post in islice(posts_iterator, offset, offset + limit):
            posts.append({
                "shortcode": post.shortcode,
                "display_url": post.url,
                "caption": post.caption,
                "likes": post.likes,
                "comments": post.comments,
                "timestamp": post.date_utc.isoformat(),
                "is_video": post.is_video
            })
        return posts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/scrape/post")
async def scrape_single_post(url: str):
    try:
        match = re.search(r'/(?:p|reels|reel)/([^/?#&]+)', url)
        if not match:
            raise HTTPException(status_code=400, detail="Invalid Instagram URL")
        
        shortcode = match.group(1)
        
        try:
            # Method 1: Fast (Instaloader)
            print(f"--- Scraping Attempt for {shortcode} ---")
            print(f"Using Instaloader with session: {hasattr(L.context, '_session') and L.context._session.cookies.get_dict()}")
            
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            print(f"✅ Instaloader Success for {shortcode}")
            return {
                "shortcode": post.shortcode,
                "display_url": post.url,
                "video_url": post.video_url if post.is_video else None,
                "caption": post.caption,
                "likes": post.likes,
                "comments": post.comments,
                "owner_username": post.owner_username,
                "timestamp": post.date_utc.isoformat(),
                "is_video": post.is_video
            }
        except Exception as e:
            # Method 2: Reliable Fallback (Browserless with Session Injection)
            print(f"⚠️ Instaloader failed ({e}), falling back to Authenticated Browser...")
            
            # Extract cookies from Instaloader session
            cookies = []
            try:
                session_cookies = L.context._session.cookies.get_dict()
                print(f"Found {len(session_cookies)} cookies to inject into Browser.")
                for name, value in session_cookies.items():
                    cookies.append({
                        "name": name,
                        "value": value,
                        "domain": ".instagram.com",
                        "path": "/"
                    })
            except Exception as cookie_err:
                print(f"❌ Failed to extract cookies: {cookie_err}")

            from browser_service import scrape_post_with_browser
            browser_data = await scrape_post_with_browser(url, cookies=cookies)
            
            if browser_data:
                print(f"✅ Browser Fallback Success for {shortcode}")
                return browser_data
            
            print(f"❌ Both methods failed for {shortcode}. Instagram is aggressively blocking this content.")
            raise HTTPException(
                status_code=429, 
                detail="Instagram is blocking this request. Try a different link or wait a few minutes."
            )

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Scrape error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/proxy/download")
async def proxy_download(url: str, filename: str, is_video: bool = False):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Encoding": "identity"
        }
        
        # Inject Master Session if available
        cookies = {}
        if INSTA_SESSION:
            cookies["sessionid"] = INSTA_SESSION

        resp = requests.get(url, headers=headers, cookies=cookies, stream=True, timeout=30)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "video/mp4" if is_video else "image/jpeg")
        
        return StreamingResponse(
            resp.iter_content(chunk_size=1024*1024),
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}.{"mp4" if is_video else "jpg"}"'}
        )
    except Exception as e:
        print(f"Proxy download failed: {e}")
        raise HTTPException(status_code=500, detail="Download failed. Instagram blocked the file access.")

@app.get("/api/proxy/view")
async def proxy_view(url: str):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }
        cookies = {"sessionid": INSTA_SESSION} if INSTA_SESSION else {}
        
        resp = requests.get(url, headers=headers, cookies=cookies, stream=True, timeout=15)
        resp.raise_for_status()
        
        return StreamingResponse(
            resp.iter_content(chunk_size=1024*1024),
            media_type=resp.headers.get("Content-Type", "video/mp4")
        )
    except Exception as e:
        print(f"Proxy view failed: {e}")
        return JSONResponse(status_code=403, content={"detail": "Instagram blocked preview access."})

@app.get("/api/fileflows/status")
async def get_ff_status(username: str = Depends(authenticate_admin)):
    if not FILEFLOWS_URL: return {"error": "Not configured"}
    try:
        response = requests.get(f"{FILEFLOWS_URL.rstrip('/')}/api/status", timeout=10)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/fileflows/flows")
async def get_ff_flows(username: str = Depends(authenticate_admin)):
    if not FILEFLOWS_URL: return []
    try:
        response = requests.get(f"{FILEFLOWS_URL.rstrip('/')}/api/flow/list-all", timeout=10)
        return response.json()
    except:
        return []

@app.post("/api/fileflows/process")
async def ff_process_post(data: dict, username: str = Depends(authenticate_admin)):
    if not FILEFLOWS_URL: return {"status": "error", "message": "FileFlows not configured"}
    
    # We send the direct media URL to FileFlows
    # FileFlows can then download and process it using its own flows
    success = trigger_fileflows_process(
        file_url=data.get("url"),
        filename=f"instagram_{data.get('username')}_{data.get('shortcode')}"
    )
    
    return {"status": "success" if success else "error"}

@app.get("/api/fileflows/nodes")
async def get_ff_nodes(username: str = Depends(authenticate_admin)):
    if not FILEFLOWS_URL: return []
    try:
        response = requests.get(f"{FILEFLOWS_URL.rstrip('/')}/api/node", timeout=10)
        return response.json()
    except:
        return []

@app.get("/api/fileflows/info")
async def get_ff_info(username: str = Depends(authenticate_admin)):
    if not FILEFLOWS_URL: return {"error": "404"}
    try:
        # FileFlows might use different paths for system info depending on version
        response = requests.get(f"{FILEFLOWS_URL.rstrip('/')}/api/system/info", timeout=10)
        if response.status_code == 200: return response.json()
        return {"error": "Unavailable"}
    except:
        return {"error": "Connection failed"}

@app.get("/api/fileflows/libraries")
async def get_ff_libraries(username: str = Depends(authenticate_admin)):
    if not FILEFLOWS_URL: return []
    try:
        response = requests.get(f"{FILEFLOWS_URL.rstrip('/')}/api/library", timeout=10)
        return response.json()
    except:
        return []

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/admin/insta-login")
async def admin_insta_login(req: LoginRequest):
    try:
        # Create a clean Instaloader instance for login
        login_loader = instaloader.Instaloader()
        
        try:
            login_loader.login(req.username, req.password)
            login_loader.save_session_to_file("session-admin")
            
            # Reload the main global 'L' instance with the new session
            global L
            L = instaloader.Instaloader()
            L.load_session_from_file("admin", "session-admin")
            
            return {"status": "success", "message": f"Logged in as {req.username}"}
        except instaloader.TwoFactorAuthRequiredException:
            return JSONResponse(status_code=401, content={"status": "error", "detail": "Two-Factor Authentication is enabled on your account. Please disable it temporarily to link the server."})
        except instaloader.BadCredentialsException:
            return JSONResponse(status_code=401, content={"status": "error", "detail": "Invalid Instagram username or password."})
        except Exception as e:
            return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/fileflows/rescan")
async def ff_rescan(username: str = Depends(authenticate_admin)):
    if not FILEFLOWS_URL: return {"status": "error"}
    try:
        response = requests.put(f"{FILEFLOWS_URL.rstrip('/')}/api/library/rescan", timeout=10)
        return {"status": "success" if response.status_code == 200 else "error"}
    except:
        return {"status": "error"}

@app.post("/api/fileflows/pause")
async def ff_pause(username: str = Depends(authenticate_admin)):
    if not FILEFLOWS_URL: return {"status": "error"}
    try:
        response = requests.post(f"{FILEFLOWS_URL.rstrip('/')}/api/system/pause", timeout=10)
        return {"status": "success"}
    except:
        return {"status": "error"}

# --- OTHER ROUTES ---

@app.get("/admin")
async def serve_admin(username: str = Depends(authenticate_admin)):
    return FileResponse("ui/admin.html")

@app.get("/")
async def serve_home():
    return FileResponse("ui/index.html")

# Serve static files (UI)
if os.path.exists("ui"):
    app.mount("/downloads", StaticFiles(directory="ui/downloads"), name="downloads")
    app.mount("/", StaticFiles(directory="ui", html=True), name="ui")

if __name__ == "__main__":
    import uvicorn
    import sys
    
    port = 5050
    if len(sys.argv) > 2 and sys.argv[1] == "--port":
        port = int(sys.argv[2])
        
    uvicorn.run(app, host="0.0.0.0", port=port)
