from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def initialize_database(target_engine=None):
    """Create missing tables and apply backward-compatible schema upgrades."""
    # Import model declarations for explicit migration commands that do not import main.py.
    from app.models import models as _models
    db_engine = target_engine or engine
    Base.metadata.create_all(bind=db_engine)
    upgrades = {
        "income": {"notes": "TEXT NOT NULL DEFAULT ''"},
        "debts": {
            "friend_id": "INTEGER REFERENCES friends(id)",
            "created_at": "TIMESTAMP",
            "updated_at": "TIMESTAMP",
        },
        "debt_repayments": {
            "user_id": "INTEGER REFERENCES users(id)",
            "request_id": "VARCHAR(100)",
            "created_at": "TIMESTAMP",
        },
        "budgets": {
            "year": "INTEGER",
            "description": "VARCHAR(300) NOT NULL DEFAULT ''",
            "created_at": "TIMESTAMP",
            "updated_at": "TIMESTAMP",
        },
        "savings_goals": {
            "opening_balance": "INTEGER NOT NULL DEFAULT 0",
            "description": "VARCHAR(500) NOT NULL DEFAULT ''",
            "category": "VARCHAR(40) NOT NULL DEFAULT 'Other'",
            "priority": "VARCHAR(20) NOT NULL DEFAULT 'medium'",
            "status": "VARCHAR(20) NOT NULL DEFAULT 'active'",
            "created_at": "TIMESTAMP",
            "updated_at": "TIMESTAMP",
        },
        "reminders": {
            "description": "VARCHAR(500) NOT NULL DEFAULT ''",
            "status": "VARCHAR(20) NOT NULL DEFAULT 'upcoming'",
            "schedule_id": "INTEGER REFERENCES recurring_schedules(id) ON DELETE SET NULL",
            "reminder_days": "JSON NOT NULL DEFAULT '[3,1,0]'",
            "paid_at": "DATE",
            "actual_paid_amount": "INTEGER",
            "expense_id": "INTEGER REFERENCES expenses(id) ON DELETE SET NULL",
            "created_at": "TIMESTAMP",
        },
    }
    with db_engine.begin() as connection:
        for table, wanted in upgrades.items():
            columns = {column["name"] for column in inspect(db_engine).get_columns(table)}
            for name, definition in wanted.items():
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
        # Keep old friend names and repayment ownership when migrating existing installations.
        connection.execute(text("UPDATE debt_repayments SET user_id = (SELECT user_id FROM debts WHERE debts.id = debt_repayments.debt_id) WHERE user_id IS NULL"))
        debts = connection.execute(text("SELECT id, user_id, friend_name FROM debts WHERE friend_id IS NULL")).mappings().all()
        for debt in debts:
            friend_id = connection.execute(text("SELECT id FROM friends WHERE user_id = :uid AND name = :name ORDER BY id LIMIT 1"), {"uid": debt["user_id"], "name": debt["friend_name"]}).scalar()
            if friend_id is None:
                friend_id = connection.execute(text("INSERT INTO friends(user_id, name, notes, created_at) VALUES (:uid, :name, '', CURRENT_TIMESTAMP) RETURNING id"), {"uid": debt["user_id"], "name": debt["friend_name"]}).scalar()
            connection.execute(text("UPDATE debts SET friend_id = :fid WHERE id = :did"), {"fid": friend_id, "did": debt["id"]})
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_repayment_user_request ON debt_repayments(user_id, request_id)"))
        connection.execute(text("UPDATE budgets SET year = CAST(substr(month, 1, 4) AS INTEGER) WHERE year IS NULL"))
        connection.execute(text("UPDATE savings_goals SET opening_balance = balance, created_at = COALESCE(created_at, CURRENT_TIMESTAMP), updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP) WHERE created_at IS NULL"))
        connection.execute(text("UPDATE reminders SET status = 'paid' WHERE paid = 1 AND status = 'upcoming'"))
        duplicate_budgets = connection.execute(text("SELECT 1 FROM budgets GROUP BY user_id, category, month HAVING COUNT(*) > 1 LIMIT 1")).first()
        if duplicate_budgets is None:
            connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_budget_user_category_month ON budgets(user_id, category, month)"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_reminder_schedule_occurrence ON reminders(schedule_id, due_date)"))
