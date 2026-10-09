"""
Web Backend Configuration
Settings for FastAPI server, JWT authentication, and CORS.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load root .env
root_dir = Path(__file__).resolve().parent.parent.parent.parent
env_path = root_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# JWT Settings
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "ox_loadout_super_secret_jwt_key_2026_change_in_production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours

# Web Server Settings
API_PREFIX = "/api/v1"
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8005"))

# Default Web Admin Credentials (can also authenticate via Telegram User ID if in admins table)
PANEL_ADMIN_USERNAME = os.getenv("PANEL_ADMIN_USERNAME", "admin")
PANEL_ADMIN_PASSWORD = os.getenv("PANEL_ADMIN_PASSWORD", "admin123")

# CORS Origins
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "*"
]
