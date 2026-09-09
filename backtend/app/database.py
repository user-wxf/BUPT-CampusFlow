import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, event, ForeignKey, JSON, String, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


engine = create_engine(os.getenv('DATABASE_URL', 'sqlite:///./youzhiban.db'),
                       connect_args={'check_same_thread': False, 'timeout': 15})


@event.listens_for(engine, 'connect')
def sqlite_settings(connection, _):
    connection.execute('PRAGMA foreign_keys=ON')


SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as session:
        yield session


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20), default='student')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Profile(Base):
    __tablename__ = 'profiles'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    college: Mapped[str] = mapped_column(String(100), default='')
    grade: Mapped[str] = mapped_column(String(30), default='')
    education_level: Mapped[str] = mapped_column(String(30), default='')
    campus: Mapped[str] = mapped_column(String(100), default='')


class Affair(Base):
    __tablename__ = 'affairs'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default='')
    location: Mapped[str] = mapped_column(String(200), default='')
    room: Mapped[str] = mapped_column(String(100), default='')
    contact: Mapped[str] = mapped_column(String(100), default='')
    office_hours: Mapped[str] = mapped_column(String(200), default='')
    materials: Mapped[list] = mapped_column(JSON, default=list)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    eligibility: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Todo(Base):
    __tablename__ = 'todos'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str] = mapped_column(Text, default='')
    completed: Mapped[bool] = mapped_column(default=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class History(Base):
    __tablename__ = 'query_history'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    question: Mapped[str] = mapped_column(Text)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    action: Mapped[str] = mapped_column(String(30))
    affair_id: Mapped[int] = mapped_column()
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
