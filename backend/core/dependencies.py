import os
import re
import jwt
import secrets
import urllib.parse
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from dotenv import load_dotenv
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

load_dotenv()

# P1.5: Insecure defaults fix
if not os.environ.get("SECRET_KEY") or os.environ.get("SECRET_KEY") == "change-me":
    os.environ["SECRET_KEY"] = secrets.token_hex(32)
    print("WARNING: SECRET_KEY not set in .env. Generated a random secure key for this session.")

if not os.environ.get("ADMIN_PASS") or os.environ.get("ADMIN_PASS") == "navjeevan":
    print("CRITICAL WARNING: ADMIN_PASS is using insecure default 'navjeevan'. Please set a strong password in .env file.")

SECRET_KEY = os.environ.get("SECRET_KEY")
ALGORITHM = "HS256"
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "navjeevan")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

# P1.3: Hardened validate_target
def validate_target(t: str):
    if not t:
        raise HTTPException(status_code=400, detail="Target cannot be empty")
    
    # Reject if starts with hyphen (flag injection prevention)
    if t.startswith("-"):
        raise HTTPException(status_code=400, detail="Invalid target: Target cannot start with a hyphen.")

    parsed = urllib.parse.urlparse(t)
    hostname = parsed.hostname or t
    
    # Basic hostname/IP validation regex
    hostname_regex = re.compile(
        r'^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9\-]*[A-Za-z0-9])$'
        r'|^(\d{1,3}\.){3}\d{1,3}$'
        r'|^\[?[a-fA-F0-9:]+\]?$'
    )
    
    if not hostname_regex.match(hostname):
        raise HTTPException(status_code=400, detail=f"Invalid target format: {hostname}. Must be a valid domain, IP, or URL.")

# P1.4: JWT expiry handling
def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired. Please login again.")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")