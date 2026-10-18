"""
SYNQ Credential Validator
Tests all API keys in your .env file and reports what's working.
"""

import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

# Load .env from backend/
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

PASS = "[OK]   "
FAIL = "[FAIL] "
SKIP = "[SKIP] "

results = []

def check(name, status, detail=""):
    icon = PASS if status == "ok" else (SKIP if status == "skip" else FAIL)
    msg = f"  {icon} {name:<25} {detail}"
    results.append((status, msg))
    print(msg)


print("")
print("=" * 60)
print("  SYNQ -- Credential & Dependency Validator")
print("=" * 60)
print("")


# --- 1. Hugging Face ------------------------------------------
print("[ Hugging Face ]")
hf_token = os.getenv("HF_TOKEN", "")
if not hf_token or "PASTE" in hf_token or hf_token == "":
    check("HF_TOKEN", "fail", "Not set in .env")
else:
    try:
        import urllib.request, json
        req = urllib.request.Request(
            "https://huggingface.co/api/whoami",
            headers={"Authorization": f"Bearer {hf_token}"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        username = data.get("name", "unknown")
        check("HF_TOKEN", "ok", f"Valid -- logged in as '{username}'")
    except Exception as e:
        check("HF_TOKEN", "fail", f"Invalid or expired -- {e}")

# --- 2. Gemini ------------------------------------------------
print("")
print("[ Google Gemini ]")
gemini_key = os.getenv("GEMINI_API_KEY", "")
if not gemini_key or "PASTE" in gemini_key or gemini_key == "":
    check("GEMINI_API_KEY", "fail", "Not set in .env")
else:
    try:
        import urllib.request, json
        # Use models list endpoint - works for both AIza and AQ. format keys
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}"
        with urllib.request.urlopen(list_url, timeout=10) as r:
            data = json.loads(r.read())
        model_names = [m.get("name","") for m in data.get("models", [])[:3]]
        # Now test actual generation with gemini-2.5-flash
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={gemini_key}"
        payload = json.dumps({"contents":[{"parts":[{"text":"say hi"}]}]}).encode()
        req = urllib.request.Request(gen_url, data=payload, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=20) as r2:
            resp = json.loads(r2.read())
            reply = resp["candidates"][0]["content"]["parts"][0]["text"][:60]
        check("GEMINI_API_KEY", "ok", f"Valid -- gemini-2.5-flash replied: {reply.strip()!r}")
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode())
        msg = body.get("error", {}).get("message", "")[:120]
        check("GEMINI_API_KEY", "fail", f"Error {e.code}: {msg}")
    except Exception as e:
        check("GEMINI_API_KEY", "fail", f"Error -- {e}")


# --- 3. Tavily ------------------------------------------------
print("")
print("[ Tavily Search ]")
tavily_key = os.getenv("TAVILY_API_KEY", "")
if not tavily_key or "PASTE" in tavily_key or tavily_key == "":
    check("TAVILY_API_KEY", "fail", "Not set in .env")
else:
    try:
        import urllib.request, json
        payload = json.dumps({"api_key": tavily_key, "query": "test", "max_results": 1}).encode()
        req = urllib.request.Request(
            "https://api.tavily.com/search",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        check("TAVILY_API_KEY", "ok", "Valid -- search API responding")
    except Exception as e:
        check("TAVILY_API_KEY", "fail", f"Invalid or network error -- {e}")

# --- 4. FalkorDB ----------------------------------------------
print("")
print("[ FalkorDB (Graph Memory) ]")
try:
    import socket
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    sock = socket.create_connection((host, port), timeout=3)
    sock.close()
    check("FalkorDB", "ok", f"Running at {host}:{port}")
except Exception:
    check("FalkorDB", "fail", "Not running -- start with: docker compose up -d")

# --- 5. Python packages ---------------------------------------
print("")
print("[ Python Packages ]")
packages = [
    ("fastapi",             "fastapi"),
    ("uvicorn",             "uvicorn"),
    ("sqlalchemy",          "sqlalchemy"),
    ("aiosqlite",           "aiosqlite"),
    ("google-genai",        "google.genai"),
    ("falkordb",            "falkordb"),
    ("python-dotenv",       "dotenv"),
    ("httpx",               "httpx"),
]
for pkg_name, import_name in packages:
    try:
        __import__(import_name)
        check(pkg_name, "ok", "Installed")
    except ImportError:
        check(pkg_name, "fail", f"Missing -- run: pip install {pkg_name}")

# --- Summary --------------------------------------------------
print("")
print("=" * 60)
ok    = sum(1 for s, _ in results if s == "ok")
fail  = sum(1 for s, _ in results if s == "fail")
skip  = sum(1 for s, _ in results if s == "skip")
print(f"  Results: {ok} passed  |  {fail} failed  |  {skip} skipped")
print("=" * 60)
print("")

if fail > 0:
    print("  Fix the [FAIL] items above, then re-run this script.\n")
else:
    print("  All checks passed! SYNQ is ready to run.\n")

sys.exit(0 if fail == 0 else 1)
