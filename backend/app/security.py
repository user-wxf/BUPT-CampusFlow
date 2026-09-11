import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .config import load_project_env
from .database import get_db, User

load_project_env()

bearer = HTTPBearer(auto_error=False)


def secret():
    value = os.getenv('JWT_SECRET_KEY', '')
    if len(value) < 32:
        raise RuntimeError('JWT_SECRET_KEY 必须设置为至少32字符的随机字符串')
    return value


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return f'{salt}${digest}'


def verify_password(password, encoded):
    salt, digest = encoded.split('$')
    actual = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return hmac.compare_digest(actual, digest)


def token_for(user):
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': str(user.id), 'iat': now, 'exp': now + timedelta(hours=2),
                       'iss': 'youzhiban'}, secret(), algorithm='HS256')


def current_user(auth: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    error = HTTPException(401, '请登录或重新登录', headers={'WWW-Authenticate': 'Bearer'})
    if not auth:
        raise error
    try:
        payload = jwt.decode(auth.credentials, secret(), algorithms=['HS256'], issuer='youzhiban',
                             options={'require': ['sub', 'exp', 'iat', 'iss']})
        user = db.get(User, int(payload['sub']))
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise error
    if user is None:
        raise error
    return user


def admin_user(user: User = Depends(current_user)):
    if user.role != 'admin':
        raise HTTPException(403, '需要管理员权限')
    return user
