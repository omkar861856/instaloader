import requests
import os
from dotenv import load_dotenv

load_dotenv()

FILEFLOWS_URL = os.getenv("FILEFLOWS_URL")

def list_fileflows_media():
    """
    Fetches the recently finished or all library files from FileFlows.
    """
    if not FILEFLOWS_URL:
        return []
    
    try:
        # Try to get recently finished files first
        endpoint = f"{FILEFLOWS_URL.rstrip('/')}/api/library-file/recently-finished"
        response = requests.get(endpoint, timeout=10)
        if response.status_code == 200:
            files = response.json()
            return [{
                "name": f.get("Name"),
                "url": f"{FILEFLOWS_URL.rstrip('/')}/api/library-file/download/{f.get('Uid')}",
                "user": "FileFlows",
                "type": "video" if f.get("RelativePath", "").endswith((".mp4", ".mkv")) else "image"
            } for f in files]
    except Exception as e:
        print(f"FileFlows Error: {e}")
    
    return []

def trigger_fileflows_process(file_url, filename):
    """
    Tells FileFlows to process a new file URL.
    """
    if not FILEFLOWS_URL:
        return None
    
    # We use the specific Library UID found on the server
    library_uid = "f40e8703-086e-417a-b491-30c3e6e092a5"
    
    # The API expects filename in query string
    endpoint = f"{FILEFLOWS_URL.rstrip('/')}/api/library-file/process-file?filename={filename}&libraryUid={library_uid}"
    
    payload = {
        "Path": file_url
    }
    
    try:
        response = requests.post(endpoint, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"FileFlows trigger failed: {response.status_code} - {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"FileFlows connection error: {e}")
        return False
