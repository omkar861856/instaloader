import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

LLM_URL = os.getenv("LLM_URL")

def analyze_profile_niche(username, biography, posts_captions):
    """
    Uses the local LLM to analyze an Instagram profile's niche and content style.
    """
    if not LLM_URL:
        return "LLM Service not configured."

    endpoint = f"{LLM_URL.rstrip('/')}/api/generate"
    
    prompt = f"""
    Analyze the following Instagram profile and provide a brief (2-3 sentences) summary of their niche, content style, and target audience.
    
    Username: @{username}
    Biography: {biography}
    Recent Captions: {', '.join(posts_captions[:5])}
    
    Summary:
    """
    
    # Try models available on the server
    available_models = ["phi3:latest", "qwen2.5-coder:1.5b", "tinyllama:latest"]
    
    for model in available_models:
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False
            }
            response = requests.post(endpoint, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "Could not generate analysis.").strip()
        except Exception as e:
            print(f"Model {model} failed: {e}")
            continue

    return "Analysis unavailable: No compatible AI models responded."
