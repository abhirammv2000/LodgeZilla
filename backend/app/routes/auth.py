from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from ..config import settings
from ..db import user_collection
from ..model.user import User

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def create_jwt_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "sub": str(data.get("sub"))})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def get_user(name: str, password: str):
    return user_collection.find_one({"name": name, "password": password})


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
    except JWTError:
        raise credentials_exception
    return user_id


@router.post("/token")
async def login_for_access_token(name: str, password: str):
    user = get_user(name, password)
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
    result = user_collection.insert_one(user_data.dict())
    return {**user_data.dict(), "id": str(result.inserted_id)}
