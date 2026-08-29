from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

Role = Literal["phc_admin", "state_official"]
JWT_SECRET = os.getenv("SWASTHYANET_JWT_SECRET", "dev-only-change-this-secret")
TOKEN_TTL_SECONDS = 60 * 60 * 8
security = HTTPBearer(auto_error=False)

@dataclass(frozen=True)
class User:
    username: str
    display_name: str
    role: Role
    phc_id: str | None = None

# Hackathon-only accounts. For production, replace this registry with an identity provider.
USERS = {
    "rajapur.admin": User("rajapur.admin", "Rajapur PHC Administrator", "phc_admin", "phc-rajapur"),
    "state.official": User("state.official", "Maharashtra State Official", "state_official", None),
}
_DEMO_PASSWORDS = {"rajapur.admin": "Rajapur@2026", "state.official": "State@2026"}


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _password_digest(password: str) -> str:
    return hashlib.scrypt(password.encode(), salt=b"swasthyanet-demo-salt", n=2**14, r=8, p=1).hex()


def verify_password(username: str, password: str) -> bool:
    expected = _password_digest(_DEMO_PASSWORDS.get(username, ""))
    return hmac.compare_digest(_password_digest(password), expected) and username in USERS


def issue_token(user: User) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": user.username, "role": user.role, "phc_id": user.phc_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    encoded = f"{_b64(json.dumps(header, separators=(',', ':')).encode())}.{_b64(json.dumps(payload, separators=(',', ':')).encode())}"
    signature = hmac.new(JWT_SECRET.encode(), encoded.encode(), hashlib.sha256).digest()
    return f"{encoded}.{_b64(signature)}"


def decode_token(token: str) -> User:
    try:
        encoded, supplied_signature = token.rsplit(".", 1)
        expected_signature = _b64(hmac.new(JWT_SECRET.encode(), encoded.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError("signature")
        payload = json.loads(_unb64(encoded.split(".")[1]))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError("expired")
        user = USERS[payload["sub"]]
        if user.role != payload["role"]:
            raise ValueError("role")
        return user
    except (KeyError, ValueError, TypeError, IndexError, json.JSONDecodeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> User:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return decode_token(credentials.credentials)


def require_roles(*roles: Role):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This role is not authorized for this action")
        return user
    return dependency


def can_access_phc(user: User, phc_id: str) -> bool:
    return user.role == "state_official" or user.phc_id == phc_id


def public_user(user: User) -> dict:
    return {"username": user.username, "display_name": user.display_name, "role": user.role, "phc_id": user.phc_id}
