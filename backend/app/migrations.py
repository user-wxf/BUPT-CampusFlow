from sqlalchemy import inspect, text


def _columns(engine, table_name: str) -> set[str]:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def run_migrations(engine) -> None:
    """Apply additive SQLite migrations without rebuilding existing tables."""
    with engine.begin() as connection:
        profile_columns = _columns(engine, "profiles")
        if profile_columns and "email" not in profile_columns:
            connection.execute(text("ALTER TABLE profiles ADD COLUMN email VARCHAR(254) NOT NULL DEFAULT ''"))

        todo_columns = _columns(engine, "todos")
        if todo_columns and "reminder_sent_at" not in todo_columns:
            connection.execute(text("ALTER TABLE todos ADD COLUMN reminder_sent_at DATETIME"))
