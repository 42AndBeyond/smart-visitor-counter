
import base64
import hashlib
import hmac
import re
import secrets
import sqlite3

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator


router = APIRouter(prefix="/auth", tags=["Authentication"])

DB_PATH = Path(__file__).resolve().parent / "smart_visitor_counter.db"

security = HTTPBearer(auto_error=False)

SESSION_DAYS = 7


# --------------------------------------------------
# REQUEST MODELS
# --------------------------------------------------

class RegisterRequest(BaseModel):
    owner_name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    supermarket_name: str = Field(min_length=2, max_length=120)

    @field_validator("owner_name", "supermarket_name")
    @classmethod
    def clean_names(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Must contain at least 2 characters")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address")
        return value


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

def get_connection():
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail="Application database is not available"
        )

    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


# --------------------------------------------------
# PASSWORD SECURITY
# --------------------------------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)

    password_hash = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=64
    )

    return (
        "scrypt$16384$8$1$"
        + base64.urlsafe_b64encode(salt).decode("ascii")
        + "$"
        + base64.urlsafe_b64encode(password_hash).decode("ascii")
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, n, r, p, salt_text, hash_text = stored_hash.split("$")

        if algorithm != "scrypt":
            return False

        salt = base64.urlsafe_b64decode(salt_text)
        expected_hash = base64.urlsafe_b64decode(hash_text)

        actual_hash = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected_hash)
        )

        return hmac.compare_digest(actual_hash, expected_hash)

    except (ValueError, TypeError):
        return False


# --------------------------------------------------
# TOKEN SECURITY
# --------------------------------------------------

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_token():
    return secrets.token_urlsafe(48)


# --------------------------------------------------
# OWNER REGISTRATION
# --------------------------------------------------

@router.post("/register", status_code=201)
def register_owner(data: RegisterRequest):

    password_hash = hash_password(data.password)

    db = get_connection()

    try:
        with db:
            cursor = db.execute(
                """
                INSERT INTO users (owner_name, email, password_hash)
                VALUES (?, ?, ?)
                """,
                (data.owner_name, data.email, password_hash)
            )

            user_id = cursor.lastrowid

            cursor = db.execute(
                """
                INSERT INTO supermarkets (owner_user_id, name)
                VALUES (?, ?)
                """,
                (user_id, data.supermarket_name)
            )

            supermarket_id = cursor.lastrowid

    except sqlite3.IntegrityError as error:
        if "users.email" in str(error):
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists"
            )

        raise HTTPException(
            status_code=400,
            detail="Could not create the owner account"
        )

    finally:
        db.close()

    return {
        "message": "Owner account registered successfully",
        "owner": {
            "id": user_id,
            "name": data.owner_name,
            "email": data.email
        },
        "supermarket": {
            "id": supermarket_id,
            "name": data.supermarket_name
        }
    }


# --------------------------------------------------
# OWNER LOGIN
# --------------------------------------------------

@router.post("/login")
def login_owner(data: LoginRequest):

    db = get_connection()

    try:
        owner = db.execute(
            """
            SELECT
                users.id,
                users.owner_name,
                users.email,
                users.password_hash,
                supermarkets.id AS supermarket_id,
                supermarkets.name AS supermarket_name
            FROM users
            JOIN supermarkets
                ON supermarkets.owner_user_id = users.id
            WHERE users.email = ?
            """,
            (data.email,)
        ).fetchone()

        if owner is None or not verify_password(
            data.password,
            owner["password_hash"]
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )

        token = create_token()
        token_hash = hash_token(token)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=SESSION_DAYS)

        db.execute(
            """
            INSERT INTO auth_sessions
                (user_id, token_hash, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                owner["id"],
                token_hash,
                now.isoformat(),
                expires_at.isoformat()
            )
        )

        db.commit()

        return {
            "message": "Login successful",
            "access_token": token,
            "token_type": "bearer",
            "expires_in": SESSION_DAYS * 24 * 60 * 60,
            "owner": {
                "id": owner["id"],
                "name": owner["owner_name"],
                "email": owner["email"]
            },
            "supermarket": {
                "id": owner["supermarket_id"],
                "name": owner["supermarket_name"]
            }
        }

    finally:
        db.close()


# --------------------------------------------------
# AUTHENTICATION VERIFICATION
# --------------------------------------------------

def get_current_owner(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token_hash = hash_token(credentials.credentials)

    db = get_connection()

    try:
        owner = db.execute(
            """
            SELECT
                users.id,
                users.owner_name,
                users.email,
                supermarkets.id AS supermarket_id,
                supermarkets.name AS supermarket_name,
                auth_sessions.expires_at
            FROM auth_sessions
            JOIN users
                ON users.id = auth_sessions.user_id
            JOIN supermarkets
                ON supermarkets.owner_user_id = users.id
            WHERE auth_sessions.token_hash = ?
              AND auth_sessions.revoked_at IS NULL
            """,
            (token_hash,)
        ).fetchone()

    finally:
        db.close()

    if owner is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired login session",
            headers={"WWW-Authenticate": "Bearer"}
        )

    expiry = datetime.fromisoformat(owner["expires_at"])

    if datetime.now(timezone.utc) >= expiry:
        raise HTTPException(
            status_code=401,
            detail="Login session has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return {
        "id": owner["id"],
        "name": owner["owner_name"],
        "email": owner["email"],
        "supermarket_id": owner["supermarket_id"],
        "supermarket_name": owner["supermarket_name"]
    }


# --------------------------------------------------
# VERIFY CURRENT OWNER
# --------------------------------------------------

@router.get("/me")
def get_my_account(
    owner: dict = Depends(get_current_owner)
):

    return {
        "message": "Authenticated successfully",
        "owner": {
            "id": owner["id"],
            "name": owner["name"],
            "email": owner["email"]
        },
        "supermarket": {
            "id": owner["supermarket_id"],
            "name": owner["supermarket_name"]
        }
    }


# --------------------------------------------------
# OWNER LOGOUT
# --------------------------------------------------

@router.post("/logout")
def logout_owner(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    owner: dict = Depends(get_current_owner)
):

    token_hash = hash_token(credentials.credentials)
    now = datetime.now(timezone.utc).isoformat()

    db = get_connection()

    try:
        db.execute(
            """
            UPDATE auth_sessions
            SET revoked_at = ?
            WHERE token_hash = ?
              AND revoked_at IS NULL
            """,
            (now, token_hash)
        )

        db.commit()

    finally:
        db.close()

    return {
        "message": "Logout successful"
    }
