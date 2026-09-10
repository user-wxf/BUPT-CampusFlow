import os
os.environ['JWT_SECRET_KEY'] = 'test-only-secret-' * 4
os.environ['RAG_MODE'] = 'demo'

import jwt
import httpx
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import Base, get_db, Todo, User
from app import email_service
from app import rag
from app.reminders import check_due_reminders


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    def override_db():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    monkeypatch.chdir(tmp_path)
    with TestClient(app) as c:
        c.sessions = sessions
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def auth(client, name='student', admin=False):
    credentials = {'username': name, 'password': 'secure-password-123'}
    assert client.post('/api/auth/register', json=credentials).status_code == 201
    if admin:
        with client.sessions() as db:
            user = db.scalar(select(User).where(User.username == name))
            user.role = 'admin'
            db.commit()
    result = client.post('/api/auth/login', json=credentials)
    assert result.status_code == 200
    return {'Authorization': 'Bearer ' + result.json()['data']['access_token']}


def test_auth_and_validation(client):
    assert client.get('/api/todos').status_code == 401
    credentials = {'username': 'tester', 'password': 'secure-password-123'}
    r = client.post('/api/auth/register', json=credentials)
    assert r.status_code == 201 and 'password_hash' not in r.text
    assert client.post('/api/auth/register', json=credentials).status_code == 409
    assert client.post('/api/auth/login', json={**credentials, 'password': 'wrong-password'}).status_code == 401
    assert client.post('/api/auth/register', json={**credentials, 'role': 'admin'}).status_code == 422
    r = client.post('/api/auth/register', json={'username': 'abc', 'password': 'short'})
    assert r.status_code == 422 and 'short' not in r.text
    expired = jwt.encode({'sub': '1', 'iss': 'youzhiban', 'iat': datetime.now(timezone.utc) - timedelta(hours=3),
                          'exp': datetime.now(timezone.utc) - timedelta(hours=1)}, os.environ['JWT_SECRET_KEY'], algorithm='HS256')
    assert client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + expired}).status_code == 401


def test_profiles_and_todo_isolation(client):
    a, b = auth(client, 'alice'), auth(client, 'bob')
    profile = client.put('/api/profile', headers=a, json={
        'college': '计算机学院',
        'campus': '沙河',
        'email': 'alice@bupt.edu.cn',
    })
    assert profile.status_code == 200
    assert profile.json()['data']['email'] == 'alice@bupt.edu.cn'
    assert client.put('/api/profile', headers=a, json={'email': 'bad-email'}).status_code == 422
    assert client.get('/api/profile', headers=b).json()['data'] is None
    due_at = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    todo = client.post('/api/todos', headers=a, json={'title': '准备材料', 'due_at': due_at}).json()['data']
    tid = todo['id']
    assert todo['due_at'] is not None and todo['reminder_sent_at'] is None
    assert client.get('/api/todos', headers=b).json()['data'] == []
    for method in ('get', 'put', 'delete'):
        kwargs = {'json': {'title': '越权修改'}} if method == 'put' else {}
        assert getattr(client, method)(f'/api/todos/{tid}', headers=b, **kwargs).status_code == 404
    assert client.put(f'/api/todos/{tid}', headers=a, json={'title': '准备材料', 'completed': True}).json()['data']['completed']
    assert client.delete(f'/api/todos/{tid}', headers=a).status_code == 200
    assert client.delete('/api/profile', headers=a).status_code == 200
    assert client.get('/api/profile', headers=a).json()['data'] is None


def test_due_reminders(client):
    sent = []
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    headers = auth(client, 'remind')
    no_email_headers = auth(client, 'noemail')
    assert client.put('/api/profile', headers=headers, json={'email': 'remind@bupt.edu.cn'}).status_code == 200
    assert client.put('/api/profile', headers=no_email_headers, json={'college': '计算机学院'}).status_code == 200

    due_soon = (now + timedelta(hours=1)).isoformat()
    due_far = (now + timedelta(hours=36)).isoformat()
    client.post('/api/todos', headers=headers, json={'title': '即将到期', 'notes': '来自测试', 'due_at': due_soon})
    client.post('/api/todos', headers=headers, json={'title': '没有DDL'})
    client.post('/api/todos', headers=headers, json={'title': '超过24小时', 'due_at': due_far})
    client.post('/api/todos', headers=headers, json={'title': '已完成', 'completed': True, 'due_at': due_soon})
    client.post('/api/todos', headers=no_email_headers, json={'title': '无邮箱', 'due_at': due_soon})

    def send_ok(**kwargs):
        sent.append(kwargs)

    with client.sessions() as db:
        stats = check_due_reminders(db, now=now, send_email=send_ok)
        assert stats == {'checked': 5, 'eligible': 1, 'sent': 1, 'failed': 0}
        assert sent[0]['to_email'] == 'remind@bupt.edu.cn'
        reminded = db.scalar(select(Todo).where(Todo.title == '即将到期'))
        assert reminded.reminder_sent_at is not None

    with client.sessions() as db:
        assert check_due_reminders(db, now=now + timedelta(minutes=1), send_email=send_ok) == {
            'checked': 5,
            'eligible': 0,
            'sent': 0,
            'failed': 0,
        }

    client.post('/api/todos', headers=headers, json={'title': '发送失败', 'due_at': due_soon})

    def send_fail(**kwargs):
        raise RuntimeError('smtp failed')

    with client.sessions() as db:
        stats = check_due_reminders(db, now=now, send_email=send_fail)
        assert stats == {'checked': 6, 'eligible': 1, 'sent': 0, 'failed': 1}
        failed = db.scalar(select(Todo).where(Todo.title == '发送失败'))
        assert failed.reminder_sent_at is None

    assert client.post('/api/reminders/check').status_code == 401
    manual = client.post('/api/reminders/check', headers=no_email_headers).json()['data']
    assert manual == {'checked': 1, 'eligible': 0, 'sent': 0, 'failed': 0}


def test_email_service_security_modes(monkeypatch):
    events = []

    class FakeSMTP:
        mode = 'plain'

        def __init__(self, host, port, timeout):
            events.append((self.mode, 'connect', host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            events.append((self.mode, 'close'))

        def starttls(self):
            events.append((self.mode, 'starttls'))

        def login(self, username, password):
            events.append((self.mode, 'login', username, password))

        def send_message(self, message):
            events.append((self.mode, 'send', message['From'], message['To'], message['Subject']))

    class FakeSMTPSSL(FakeSMTP):
        mode = 'ssl'

    monkeypatch.setattr(email_service.smtplib, 'SMTP', FakeSMTP)
    monkeypatch.setattr(email_service.smtplib, 'SMTP_SSL', FakeSMTPSSL)
    base_env = {
        'SMTP_HOST': 'smtp.example.com',
        'SMTP_PORT': '587',
        'SMTP_USERNAME': 'sender@example.com',
        'SMTP_PASSWORD': 'test-password',
        'SMTP_FROM': 'noreply@example.com',
    }
    for key, value in base_env.items():
        monkeypatch.setenv(key, value)

    monkeypatch.setenv('SMTP_SECURITY', 'starttls')
    email_service.send_deadline_email(
        to_email='student@example.com',
        title='提交材料',
        due_at=datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc),
        notes='来自测试',
    )
    assert ('plain', 'connect', 'smtp.example.com', 587, 20) in events
    assert ('plain', 'starttls') in events
    assert any(event[:2] == ('plain', 'send') for event in events)

    events.clear()
    monkeypatch.setenv('SMTP_SECURITY', 'ssl')
    monkeypatch.setenv('SMTP_PORT', '465')
    email_service.send_deadline_email(
        to_email='student@example.com',
        title='提交材料',
        due_at=datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc),
    )
    assert ('ssl', 'connect', 'smtp.example.com', 465, 20) in events
    assert ('ssl', 'starttls') not in events
    assert any(event[:2] == ('ssl', 'send') for event in events)

    events.clear()
    monkeypatch.delenv('SMTP_SECURITY')
    monkeypatch.setenv('SMTP_USE_TLS', 'false')
    monkeypatch.setenv('SMTP_PORT', '25')
    email_service.send_deadline_email(
        to_email='student@example.com',
        title='提交材料',
        due_at=datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc),
    )
    assert ('plain', 'connect', 'smtp.example.com', 25, 20) in events
    assert ('plain', 'starttls') not in events


def test_affairs_query_history_and_audit(client):
    student, admin = auth(client), auth(client, 'manager', admin=True)
    data = {'title': '测试事务', 'location': '演示地点', 'steps': ['提交测试材料'],
            'sources': [{'title': '测试来源', 'reference': 'demo:only'}], 'eligibility': {'campus': ['沙河']}}
    assert client.post('/api/admin/affairs', headers=student, json=data).status_code == 403
    aid = client.post('/api/admin/affairs', headers=admin, json=data).json()['data']['id']
    assert client.get(f'/api/affairs/{aid}', headers=student).status_code == 200
    empty = client.post('/api/query', headers=student, json={'question': '如何办理测试事务？', 'affair_id': aid})
    assert empty.json()['data']['plans'] == []
    client.put('/api/profile', headers=student, json={'campus': '沙河'})
    answer = client.post('/api/query', headers=student, json={'question': '如何办理测试事务？'})
    assert answer.status_code == 200
    result = answer.json()['data']
    assert result['mode'] == 'demo' and result['plans'][0]['location'] == '演示地点'
    hid = result['history_id']
    assert client.get(f'/api/history/{hid}', headers=admin).status_code == 404
    assert client.get('/api/history', headers=student).json()['data'][0]['result']['mode'] == 'demo'
    assert client.delete(f'/api/history/{hid}', headers=student).status_code == 200
    assert client.put(f'/api/admin/affairs/{aid}', headers=admin, json={**data, 'room': '101'}).status_code == 200
    assert client.delete(f'/api/admin/affairs/{aid}', headers=admin).status_code == 200
    logs = client.get('/api/admin/logs', headers=admin).json()['data']
    assert [x['action'] for x in logs] == ['delete', 'update', 'create']
    assert client.get('/api/admin/logs', headers=student).status_code == 403


def test_rag_contract_and_failures(client, monkeypatch):
    headers = auth(client)
    monkeypatch.setenv('RAG_MODE', 'http')
    monkeypatch.setenv('RAG_URL', 'http://rag.test/generate')
    original_client = httpx.Client
    def install(handler):
        monkeypatch.setattr(rag.httpx, 'Client', lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))
    def valid(request):
        return httpx.Response(200, json={'answer': '测试答复', 'plans': [], 'sources': [], 'warnings': [], 'mode': 'rag'})
    install(valid)
    assert client.post('/api/query', headers=headers, json={'question': '测试'}).json()['data']['mode'] == 'rag'
    install(lambda req: httpx.Response(200, json={'bad': True}))
    assert client.post('/api/query', headers=headers, json={'question': '测试'}).status_code == 502
    def timeout(request):
        raise httpx.ReadTimeout('timeout', request=request)
    install(timeout)
    assert client.post('/api/query', headers=headers, json={'question': '测试'}).status_code == 504
    assert len(client.get('/api/history', headers=headers).json()['data']) == 1
