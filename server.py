from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from fileflows_service import ff_service
from instagram_service import ig_service
from dotenv import load_dotenv

load_dotenv()

from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FlowDash")

app = FastAPI(title="EcoInstagram", description="Premium Instagram & FileFlows Dashboard")
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

# Allow CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- FILEFLOWS API ENDPOINTS ---

@app.get("/api/fileflows/status")
async def get_ff_status():
    return ff_service.get_status()

@app.get("/api/fileflows/executing")
async def get_ff_executing():
    return ff_service.get_executing()

@app.get("/api/fileflows/upcoming")
async def get_ff_upcoming():
    return ff_service.get_upcoming()

@app.get("/api/fileflows/recently-finished")
async def get_ff_recent():
    return ff_service.get_recently_finished()

@app.get("/api/fileflows/nodes")
async def get_ff_nodes():
    return ff_service.get_nodes()

@app.get("/api/fileflows/flows")
async def get_ff_flows():
    logger.info("Fetching flows from FileFlows...")
    flows = ff_service.get_flows()
    logger.info(f"Retrieved {len(flows)} flows")
    return flows

@app.get("/api/fileflows/flow-templates")
async def get_ff_templates():
    return ff_service.get_flow_templates()

@app.get("/api/fileflows/library-files")
async def get_ff_library_files(page: int = 0, pageSize: int = 50):
    return ff_service.get_library_files(page, pageSize)

@app.get("/api/fileflows/export-flow/{uid}")
async def export_ff_flow(uid: str):
    data = ff_service.export_flow(uid)
    if not data:
        raise HTTPException(status_code=404, detail="Flow not found")
    return data

@app.post("/api/fileflows/trigger")
async def ff_trigger(data: dict, username: str = Depends(authenticate_admin)):
    url = data.get("url")
    flow_uid = data.get("flow_uid")
    if not url or not flow_uid:
        raise HTTPException(status_code=400, detail="URL and Flow UID are required")
    
    # We use a default library UID or one associated with URLs
    # For now, let's assume a generic library UID if not provided
    library_uid = data.get("library_uid", "00000000-0000-0000-0000-000000000000")
    
    success = ff_service.trigger_process(
        path=url,
        filename=f"URL_{int(os.path.getmtime(__file__))}", # Dummy unique name
        library_uid=library_uid
    )
    return {"status": "success" if success else "error"}

@app.get("/api/fileflows/info")
async def get_ff_info():
    return ff_service.get_system_info()

@app.post("/api/fileflows/rescan")
async def ff_rescan(username: str = Depends(authenticate_admin)):
    success = ff_service.rescan_libraries()
    return {"status": "success" if success else "error"}

# --- INSTAGRAM API ENDPOINTS ---

@app.get("/api/instagram/user/{username}")
async def get_ig_user(username: str):
    info = await ig_service.get_user_info(username)
    if not info:
        raise HTTPException(status_code=404, detail="User not found or private")
    return info.dict()

@app.get("/api/instagram/medias/{username}")
async def get_ig_medias(username: str, amount: int = 10):
    medias = await ig_service.get_user_medias(username, amount)
    return [m.dict() for m in medias]

@app.post("/api/instagram/download")
async def download_ig_media(data: dict):
    url = data.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    path = await ig_service.download_media(url)
    if not path:
        raise HTTPException(status_code=500, detail="Download failed")
        
    return {"status": "success", "path": str(path)}

# --- OTHER ROUTES ---

@app.get("/")
async def serve_home():
    return FileResponse("ui/index.html")

# Serve static files (UI)
if os.path.exists("ui"):
    app.mount("/", StaticFiles(directory="ui", html=True), name="ui")

if __name__ == "__main__":
    import uvicorn
    import sys
    
    port = 5050
    if len(sys.argv) > 2 and sys.argv[1] == "--port":
        port = int(sys.argv[2])
        
    uvicorn.run(app, host="0.0.0.0", port=port)
