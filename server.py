import instaloader
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
import os
import requests
import re
from browser_service import fetch_profile_via_browser
from llm_service import analyze_profile_niche
from fileflows_service import list_fileflows_media, trigger_fileflows_process
import browser_cookie3
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

L = instaloader.Instaloader()
FILEFLOWS_URL = os.getenv("FILEFLOWS_URL")

# Try to load session from local browser to avoid 403s
try:
    cookies = browser_cookie3.chrome(domain_name='instagram.com')
    L.context._session.cookies.update(cookies)
    print("Successfully loaded Instagram cookies from Chrome.")
except Exception as e:
    print(f"Could not load cookies from Chrome: {e}")

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
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
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
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/proxy/download")
async def proxy_download(url: str, filename: str = "instagram_media", is_video: bool = False):
    try:
        session = L.context._session
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        ext = ".mp4" if is_video else ".jpg"
        
        response = session.get(url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        
        def iterfile():
            for chunk in response.iter_content(chunk_size=8192):
                yield chunk
        
        return StreamingResponse(
            iterfile(), 
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}{ext}"',
                "Content-Type": "application/octet-stream",
                "X-Content-Type-Options": "nosniff"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy failed: {str(e)}")

@app.post("/api/download/post/{shortcode}")
async def download_post(shortcode: str):
    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        target_dir = f"ui/downloads/{post.owner_username}"
        os.makedirs(target_dir, exist_ok=True)
        L.download_post(post, target=target_dir)
        return {"message": f"Post {shortcode} downloaded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/downloads/all")
async def list_all_downloads():
    all_files = list_fileflows_media()
    return all_files

# --- FILEFLOWS PROXY ---

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
    uvicorn.run(app, host="0.0.0.0", port=8000)
