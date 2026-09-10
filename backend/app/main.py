import logging
import os
import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, inspect
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from .database import Base, engine, get_db, User, Profile, Affair, Todo, History, AuditLog
from .migrations import run_migrations
from .reminders import check_due_reminders, reminder_scheduler_loop
from .schemas import Credentials, ProfileInput, AffairInput, TodoInput, QueryInput
from .security import current_user, admin_user, hash_password, verify_password, token_for, secret
from . import rag


@asynccontextmanager
async def lifespan(app):
    secret()
    Base.metadata.create_all(engine)
    run_migrations(engine)
    reminder_task = None
    if os.getenv('REMINDER_SCHEDULER_ENABLED', 'true').strip().lower() not in {'0', 'false', 'no', 'off'}:
        reminder_task = asyncio.create_task(reminder_scheduler_loop())
        app.state.reminder_task = reminder_task
    yield
    if reminder_task:
        reminder_task.cancel()
        with suppress(asyncio.CancelledError):
            await reminder_task


app = FastAPI(title='邮智办 · B 后端', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware,
                   allow_origins=os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(','),
                   allow_credentials=False, allow_methods=['GET', 'POST', 'PUT', 'DELETE'],
                   allow_headers=['Authorization', 'Content-Type'])
DB = Annotated[Session, Depends(get_db)]
Student = Annotated[User, Depends(current_user)]
Admin = Annotated[User, Depends(admin_user)]


def row(obj):
    # 明确排除密码哈希，避免错误地返回给客户端。
    return jsonable_encoder({a.key: getattr(obj, a.key) for a in inspect(obj).mapper.column_attrs
                             if a.key != 'password_hash'})


def ok(data=None):
    return {'code': 0, 'message': 'ok', 'data': data}


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse(status_code=exc.status_code, headers=exc.headers,
                        content={'code': exc.status_code, 'message': exc.detail, 'data': None})


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # 不回显 input，防止校验错误泄露密码。
    errors = [{'field': '.'.join(map(str, e['loc'])), 'message': e['msg']} for e in exc.errors()]
    return JSONResponse(status_code=422, content={'code': 422, 'message': '参数校验失败', 'data': errors})


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    logging.error('Database operation failed: %s', type(exc).__name__)
    return JSONResponse(status_code=503, content={'code': 503, 'message': '数据库暂时不可用', 'data': None})


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    logging.error('Unhandled server error: %s', type(exc).__name__)
    return JSONResponse(status_code=500, content={'code': 500, 'message': '服务器内部错误', 'data': None})


def owned(db, model, item_id, user):
    item = db.scalar(select(model).where(model.id == item_id, model.user_id == user.id))
    if item is None:
        raise HTTPException(404, '记录不存在')
    return item


def affair_or_404(db, item_id):
    item = db.get(Affair, item_id)
    if item is None:
        raise HTTPException(404, '事务不存在')
    return item


def paginate(db, statement, offset, limit):
    return [row(x) for x in db.scalars(statement.offset(offset).limit(limit))]


def utc_or_none(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def same_time(left: datetime | None, right: datetime | None) -> bool:
    if left is None or right is None:
        return left is right
    return utc_or_none(left) == utc_or_none(right)


@app.get('/api/health')
def health():
    return ok({'status': 'ok', 'rag_mode': os.getenv('RAG_MODE', 'demo')})


@app.get('/api/sources/evidence')
def source_evidence(user: Student, title: str = Query(..., min_length=1, max_length=300),
                    reference: str = Query(..., min_length=1, max_length=1000)):
    return ok(rag.source_evidence(title, reference))


@app.post('/api/auth/register', status_code=201)
def register(body: Credentials, db: DB):
    user = User(username=body.username, password_hash=hash_password(body.password), role='student')
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '用户名已存在')
    return ok(row(user))


@app.post('/api/auth/login')
def login(body: Credentials, db: DB):
    user = db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, '用户名或密码错误')
    return ok({'access_token': token_for(user), 'token_type': 'bearer', 'expires_in': 7200, 'user': row(user)})


@app.get('/api/auth/me')
def me(user: Student):
    return ok(row(user))


@app.get('/api/profile')
def get_profile(db: DB, user: Student):
    item = db.get(Profile, user.id)
    return ok(row(item) if item else None)


@app.put('/api/profile')
def save_profile(body: ProfileInput, db: DB, user: Student):
    item = db.get(Profile, user.id)
    if item is None:
        item = Profile(user_id=user.id)
        db.add(item)
    for key, value in body.model_dump().items():
        setattr(item, key, value)
    db.commit()
    return ok(row(item))


@app.delete('/api/profile')
def delete_profile(db: DB, user: Student):
    item = db.get(Profile, user.id)
    if item:
        db.delete(item)
        db.commit()
    return ok()


@app.get('/api/affairs')
def affairs(db: DB, user: Student, q: str = Query('', max_length=100),
            offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    statement = select(Affair).order_by(Affair.id.desc())
    if q:
        statement = statement.where(Affair.title.contains(q, autoescape=True))
    return ok(paginate(db, statement, offset, limit))


@app.get('/api/affairs/{item_id}')
def get_affair(item_id: int, db: DB, user: Student):
    return ok(row(affair_or_404(db, item_id)))


def audit(db, user, action, item):
    db.add(AuditLog(user_id=user.id, action=action, affair_id=item.id, snapshot=row(item)))


@app.post('/api/admin/affairs', status_code=201)
def create_affair(body: AffairInput, db: DB, user: Admin):
    item = Affair(**body.model_dump())
    db.add(item)
    db.flush()
    audit(db, user, 'create', item)
    db.commit()
    return ok(row(item))


@app.put('/api/admin/affairs/{item_id}')
def update_affair(item_id: int, body: AffairInput, db: DB, user: Admin):
    item = affair_or_404(db, item_id)
    for key, value in body.model_dump().items():
        setattr(item, key, value)
    db.flush()
    audit(db, user, 'update', item)
    db.commit()
    return ok(row(item))


@app.delete('/api/admin/affairs/{item_id}')
def delete_affair(item_id: int, db: DB, user: Admin):
    item = affair_or_404(db, item_id)
    audit(db, user, 'delete', item)
    db.delete(item)
    db.commit()
    return ok()


@app.get('/api/admin/logs')
def logs(db: DB, user: Admin, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    return ok(paginate(db, select(AuditLog).order_by(AuditLog.id.desc()), offset, limit))


@app.post('/api/todos', status_code=201)
def create_todo(body: TodoInput, db: DB, user: Student):
    data = body.model_dump()
    data['due_at'] = utc_or_none(data['due_at'])
    item = Todo(user_id=user.id, **data)
    db.add(item)
    db.commit()
    return ok(row(item))


@app.get('/api/todos')
def todos(db: DB, user: Student, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    return ok(paginate(db, select(Todo).where(Todo.user_id == user.id).order_by(Todo.id.desc()), offset, limit))


@app.get('/api/todos/{item_id}')
def get_todo(item_id: int, db: DB, user: Student):
    return ok(row(owned(db, Todo, item_id, user)))


@app.put('/api/todos/{item_id}')
def update_todo(item_id: int, body: TodoInput, db: DB, user: Student):
    item = owned(db, Todo, item_id, user)
    data = body.model_dump()
    data['due_at'] = utc_or_none(data['due_at'])
    due_changed = not same_time(item.due_at, data['due_at'])
    for key, value in data.items():
        setattr(item, key, value)
    if due_changed:
        item.reminder_sent_at = None
    db.commit()
    return ok(row(item))


@app.post('/api/reminders/check')
def check_my_reminders(db: DB, user: Student):
    return ok(check_due_reminders(db, user_id=user.id))


@app.delete('/api/todos/{item_id}')
def delete_todo(item_id: int, db: DB, user: Student):
    db.delete(owned(db, Todo, item_id, user))
    db.commit()
    return ok()


@app.get('/api/history')
def history(db: DB, user: Student, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    return ok(paginate(db, select(History).where(History.user_id == user.id).order_by(History.id.desc()), offset, limit))


@app.get('/api/history/{item_id}')
def get_history(item_id: int, db: DB, user: Student):
    return ok(row(owned(db, History, item_id, user)))


@app.delete('/api/history/{item_id}')
def delete_history(item_id: int, db: DB, user: Student):
    db.delete(owned(db, History, item_id, user))
    db.commit()
    return ok()


@app.post('/api/query')
def query(body: QueryInput, db: DB, user: Student):
    stored_profile = db.get(Profile, user.id)
    profile = {k: getattr(stored_profile, k, '') for k in ('college', 'grade', 'education_level', 'campus')}
    if body.affair_id:
        candidates = [affair_or_404(db, body.affair_id)]
    else:
        # 演示模式只做标题/描述匹配；真实语义检索属于 C。
        candidates = list(db.scalars(select(Affair).order_by(Affair.id)))
    eligible = [row(a) for a in candidates if all(not values or profile.get(key) in values
                for key, values in a.eligibility.items())]
    if os.getenv('RAG_MODE', 'demo') == 'demo' and not body.affair_id:
        eligible = [a for a in eligible if a['title'] in body.question or body.question in a['title']
                    or body.question in a['description']]
    # 释放 SQLite 读事务，避免在最长45秒的上游调用期间占用连接。
    db.rollback()
    result = rag.generate(body.question, profile, eligible)
    item = History(user_id=user.id, question=body.question, result=result)
    db.add(item)
    db.commit()
    return ok({'history_id': item.id, **result})
