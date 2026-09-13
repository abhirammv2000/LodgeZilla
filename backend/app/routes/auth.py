from datetime import datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from ..config import settings
from ..db import user_collection
from ..model.user import User

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
_hasher = PasswordHasher()


class LoginRequest(BaseModel):
    name: str
    password: str


def create_jwt_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "sub": str(data.get("sub"))})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _is_hashed(password: str) -> bool:
    """Argon2 hashes always start with this prefix; a legacy plaintext
    password from the original seed data never will."""
    return password.startswith("$argon2")


def get_user(name: str, password: str):
    """Look up a user by name and verify the password.

    Existing seeded accounts store a plaintext password (see
    clean_and_ingest_data.py). Rather than a one-off migration script that
    would need to run before this change could ship, a successful legacy
    login upgrades that account's stored password to an Argon2 hash on the
    spot: verifying the password is already proof the caller knows it, so
    this is the standard lazy-migration pattern, not a new trust decision.
    """
    user = user_collection.find_one({"name": name})
    if user is None:
        return None

    stored = user.get("password", "")
    if _is_hashed(stored):
        try:
            _hasher.verify(stored, password)
        except VerifyMismatchError:
            return None
    else:
        if stored != password:
            return None
        user_collection.update_one(
            {"_id": user["_id"]}, {"$set": {"password": _hasher.hash(password)}}
        )
    return user


def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    return user_id


@router.post("/token")
async def login_for_access_token(credentials: LoginRequest):
    user = get_user(credentials.name, credentials.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_jwt_token(
        {"sub": user["user_id"], "userType": user.get("userType", "")}
    )
    return {"access_token": token, "token_type": "bearer"}


@router.post("/create")
async def create_user(user_data: User):
    payload = user_data.dict()
    if payload.get("password"):
        payload["password"] = _hasher.hash(payload["password"])
    # insert_one mutates its argument, adding a raw ObjectId under "_id".
    # Building the response from a second, untouched .dict() rather than the
    # mutated payload avoids handing that back as if it were JSON-safe.
    result = user_collection.insert_one(payload)
    response = user_data.dict()
    response.pop("password", None)
    return {**response, "id": str(result.inserted_id)}
