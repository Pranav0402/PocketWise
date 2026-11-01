from sqlalchemy import create_engine, text

from app.core.database import initialize_database


def test_legacy_debt_schema_is_migrated_without_losing_records():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, email VARCHAR(255) NOT NULL UNIQUE, password_hash VARCHAR(255) NOT NULL, created_at TIMESTAMP)"))
        connection.execute(text("CREATE TABLE debts (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, friend_name VARCHAR(120) NOT NULL, direction VARCHAR(10) NOT NULL, amount INTEGER NOT NULL, date DATE NOT NULL, due_date DATE, description VARCHAR(300))"))
        connection.execute(text("CREATE TABLE debt_repayments (id INTEGER PRIMARY KEY, debt_id INTEGER NOT NULL, amount INTEGER NOT NULL, date DATE NOT NULL, note VARCHAR(300))"))
        connection.execute(text("CREATE TABLE budgets (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, category VARCHAR(60) NOT NULL, amount INTEGER NOT NULL, month VARCHAR(7) NOT NULL)"))
        connection.execute(text("CREATE TABLE savings_goals (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, name VARCHAR(100) NOT NULL, target_amount INTEGER NOT NULL, target_date DATE, balance INTEGER NOT NULL DEFAULT 0)"))
        connection.execute(text("CREATE TABLE reminders (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, title VARCHAR(120) NOT NULL, amount INTEGER NOT NULL, due_date DATE NOT NULL, category VARCHAR(60), recurrence VARCHAR(20), paid BOOLEAN NOT NULL DEFAULT 0)"))
        connection.execute(text("INSERT INTO users(id,name,email,password_hash) VALUES (1,'Legacy','legacy@example.com','hash')"))
        connection.execute(text("INSERT INTO debts(id,user_id,friend_name,direction,amount,date,description) VALUES (7,1,'Rahul','borrowed',10000,'2026-10-01','Old debt')"))
        connection.execute(text("INSERT INTO debt_repayments(id,debt_id,amount,date,note) VALUES (9,7,2500,'2026-10-03','Old repayment')"))
        connection.execute(text("INSERT INTO budgets(id,user_id,category,amount,month) VALUES (11,1,'Food',30000,'2026-10')"))
        connection.execute(text("INSERT INTO savings_goals(id,user_id,name,target_amount,balance) VALUES (13,1,'Old goal',50000,12500)"))
        connection.execute(text("INSERT INTO reminders(id,user_id,title,amount,due_date,category,recurrence,paid) VALUES (17,1,'Legacy rent',80000,'2026-10-01','Rent','once',1)"))

    initialize_database(engine)
    with engine.connect() as connection:
        debt = connection.execute(text("SELECT friend_id, friend_name, amount FROM debts WHERE id=7")).one()
        repayment = connection.execute(text("SELECT user_id, request_id, amount, note FROM debt_repayments WHERE id=9")).one()
        friend = connection.execute(text("SELECT user_id, name FROM friends WHERE id=:id"), {"id":debt.friend_id}).one()
        budget = connection.execute(text("SELECT year, description FROM budgets WHERE id=11")).one()
        goal = connection.execute(text("SELECT opening_balance, description, category, status FROM savings_goals WHERE id=13")).one()
        reminder = connection.execute(text("SELECT status, description, schedule_id, reminder_days FROM reminders WHERE id=17")).one()
        assert debt.friend_id is not None and tuple(debt)[1:] == ("Rahul", 10000)
        assert tuple(repayment) == (1, None, 2500, "Old repayment")
        assert tuple(friend) == (1, "Rahul")
        assert tuple(budget) == (2026, "")
        assert tuple(goal) == (12500, "", "Other", "active")
        assert tuple(reminder) == ("paid", "", None, "[3,1,0]")
        assert "savings_transactions" in {row[0] for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    engine.dispose()
