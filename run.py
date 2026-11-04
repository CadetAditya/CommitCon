"""
run.py - Production server entry-point for Render, Railway, Docker, and local execution.
Automatically binds to cloud-assigned $PORT (defaults to 8000 or 10000).
"""
import os
import sys

if __name__ == "__main__":
    # Render sets $PORT (usually 10000), Heroku/Railway sets $PORT, local defaults to 8000
    port_env = os.environ.get("PORT", "8000").strip()
    try:
        port = int(port_env)
    except (ValueError, TypeError):
        # Fallback if $PORT was passed as literal '$PORT' or invalid string
        port = 10000 if "RENDER" in os.environ else 8000

    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Starting CommitCon Driver Portal on {host}:{port} ...")
    
    import uvicorn
    uvicorn.run("phase5_api:app", host=host, port=port, log_level="info")

