from datetime import date, timedelta
import calendar
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from io import StringIO
import csv
import json
from zoneinfo import ZoneInfo
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, extract, or_, func, update, case
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.core.database import get_db, initialize_database
from app.core.security import create_token, hash_password, token_user_id, verify_password
from app.models.models import User, Income, Expense, Budget, SavingsGoal, SavingsTransaction, Friend, Debt, DebtRepayment, Reminder, RecurringSchedule, ReminderPayment, Notification, NotificationPreference
from app.schemas.schemas import (Register, Login, IncomeCreate, ExpenseCreate, BudgetCreate,
    GoalCreate, Contribution, FriendCreate, DebtCreate, RepaymentCreate, ReminderCreate, ReminderPaymentCreate, NotificationPreferenceUpdate, AssistantChat, AffordabilityCheck)
from app.assistant_engine import DISCLAIMER as ASSISTANT_DISCLAIMER, question_range as assistant_question_range, answer_question as assistant_rule_answer, affordability_result, rupees as assistant_rupees
from app.assistant_provider import OllamaProvider

if settings.auto_migrate:
    initialize_database()
app = FastAPI(title="PocketWise API", version="1.0.0")
allowed_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()]
if settings.app_environment.casefold() == "production" and (not allowed_origins or "*" in allowed_origins):
    raise RuntimeError("Production requires explicit CORS_ORIGINS")
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins,
                   allow_credentials=False, allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                   allow_headers=["Authorization", "Content-Type"])
bearer = HTTPBearer(auto_error=False)


def kolkata_today():
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


def to_paise(amount: float) -> int:
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def to_rupees(amount: int) -> float:
    return amount / 100


class SafeCSVWriter:
    """Escape cells that spreadsheet applications may interpret as formulas."""
    def __init__(self, stream):
        self.writer=csv.writer(stream)

    @staticmethod
    def safe_cell(value):
        if isinstance(value, str) and value.lstrip(" \t\r\n\v\x00")[:1] in ("=", "+", "-", "@"):
            return "'" + value
        return value

    def writerow(self, row):
        self.writer.writerow([self.safe_cell(value) for value in row])

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    if not credentials:
        raise HTTPException(401, "Authentication required")
    try:
        uid = token_user_id(credentials.credentials)
    except ValueError:
        raise HTTPException(401, "Invalid or expired token")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "User not found")
    return user


def record(row, **extra):
    out = {k: v for k, v in row.__dict__.items() if not k.startswith("_")}
    if "amount" in out: out["amount"] = to_rupees(out["amount"])
    if "target_amount" in out: out["target_amount"] = to_rupees(out["target_amount"])
    if "balance" in out: out["balance"] = to_rupees(out["balance"])
    if "opening_balance" in out: out["opening_balance"] = to_rupees(out["opening_balance"])
    out.update(extra)
    return out


@app.middleware("http")
async def hardening_headers(request, call_next):
    content_length=request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > 1_048_576:
                return Response(content=json.dumps({"detail":"Request body is too large"}), status_code=413, media_type="application/json")
        except ValueError:
            return Response(content=json.dumps({"detail":"Invalid content length"}), status_code=400, media_type="application/json")
    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"]="no-store"
    if request.url.scheme == "https": response.headers["Strict-Transport-Security"]="max-age=31536000; includeSubDomains"
    return response


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(select(1))
    except Exception:
        raise HTTPException(503, "Service temporarily unavailable")
    return {"status": "ok", "app": "PocketWise"}


@app.post("/api/auth/register", status_code=201)
def register(payload: Register, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(name=payload.name.strip(), email=email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists") from exc
    db.refresh(user)
    return {"access_token": create_token(user.id), "token_type": "bearer", "user": {"id": user.id, "name": user.name, "email": user.email}}


@app.post("/api/auth/login")
def login(payload: Login, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect")
    return {"access_token": create_token(user.id), "token_type": "bearer", "user": {"id": user.id, "name": user.name, "email": user.email}}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "name": user.name, "email": user.email}


@app.put("/api/auth/me")
def update_me(payload: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    name = payload.get("name")
    if not isinstance(name, str) or not 2 <= len(name.strip()) <= 80:
        raise HTTPException(422, "Display name must be between 2 and 80 characters")
    user.name = name.strip()
    db.commit()
    db.refresh(user)
    return {"id": user.id, "name": user.name, "email": user.email}


def crud_routes(path, model, create_schema, amount_fields=("amount",)):
    @app.get(f"/api/{path}")
    def listing(user: User = Depends(current_user), db: Session = Depends(get_db), limit: int = Query(100, ge=1, le=500),
                search: str | None = None, source: str | None = None, category: str | None = None,
                date_from: date | None = None, date_to: date | None = None,
                sort_by: str | None = None, sort_order: str = Query("desc", pattern="^(asc|desc)$")):
        if date_from and date_to and date_from > date_to:
            raise HTTPException(422, "date_from must be on or before date_to")
        if sort_by and sort_by not in ("date", "amount"):
            raise HTTPException(422, "sort_by must be date or amount")
        query = select(model).where(model.user_id == user.id)
        if source and hasattr(model, "source"):
            query = query.where(model.source == source)
        if category and hasattr(model, "category"):
            query = query.where(model.category == category)
        if date_from and hasattr(model, "date"):
            query = query.where(model.date >= date_from)
        if date_to and hasattr(model, "date"):
            query = query.where(model.date <= date_to)
        if search:
            searchable = [getattr(model, field) for field in ("source", "category", "description", "notes", "payment_method") if hasattr(model, field)]
            if searchable:
                query = query.where(or_(*(field.ilike(f"%{search.strip()}%") for field in searchable)))
        if sort_by in ("date", "amount") and hasattr(model, sort_by):
            column = getattr(model, sort_by)
            query = query.order_by(column.asc() if sort_order == "asc" else column.desc())
        else:
            query = query.order_by(model.id.desc())
        rows = db.scalars(query.limit(limit)).all()
        return [record(row) for row in rows]

    @app.post(f"/api/{path}", status_code=201)
    def create(payload: create_schema, user: User = Depends(current_user), db: Session = Depends(get_db)):
        data = payload.model_dump()
        for field in amount_fields:
            if field in data and data[field] is not None: data[field] = to_paise(data[field])
        row = model(user_id=user.id, **data)
        db.add(row); db.commit(); db.refresh(row)
        return record(row)

    @app.put(f"/api/{path}/{{item_id}}")
    def update(item_id: int, payload: create_schema, user: User = Depends(current_user), db: Session = Depends(get_db)):
        row = db.scalar(select(model).where(model.id == item_id, model.user_id == user.id))
        if not row: raise HTTPException(404, "Record not found")
        for key, value in payload.model_dump().items(): setattr(row, key, to_paise(value) if key in amount_fields else value)
        db.commit(); db.refresh(row)
        return record(row)

    @app.delete(f"/api/{path}/{{item_id}}", status_code=204)
    def delete(item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
        row = db.scalar(select(model).where(model.id == item_id, model.user_id == user.id))
        if not row: raise HTTPException(404, "Record not found")
        db.delete(row); db.commit()


crud_routes("income", Income, IncomeCreate)
crud_routes("expenses", Expense, ExpenseCreate)


def budget_month(month=None, year=None):
    if month:
        try:
            parsed = datetime.strptime(month, "%Y-%m")
            return parsed.strftime("%Y-%m"), parsed.year, parsed.month
        except ValueError:
            raise HTTPException(422, "Month must be a valid YYYY-MM value")
    if year:
        if year < 1900 or year > 2200: raise HTTPException(422, "Year must be between 1900 and 2200")
        return None, year, None
    current = kolkata_today()
    return current.strftime("%Y-%m"), current.year, current.month


def budget_status_code(spent, limit):
    if not limit: return "normal"
    return "exceeded" if spent > limit else "critical" if spent * 10 >= limit * 9 else "warning" if spent * 4 >= limit * 3 else "normal"


def budget_summary_data(user_id, db, month=None, year=None):
    month, resolved_year, month_num = budget_month(month, year)
    query = select(Budget).where(Budget.user_id == user_id)
    expenses_query = select(Expense).where(Expense.user_id == user_id)
    if month:
        query = query.where(Budget.month == month)
        expenses_query = expenses_query.where(extract("year", Expense.date) == resolved_year, extract("month", Expense.date) == month_num)
    else:
        query = query.where(Budget.year == resolved_year)
        expenses_query = expenses_query.where(extract("year", Expense.date) == resolved_year)
    rows = db.scalars(query.order_by(Budget.category)).all()
    expenses = db.scalars(expenses_query).all()
    limits, actuals = {}, {}
    for row in rows: limits[row.category] = limits.get(row.category, 0) + row.amount
    for item in expenses: actuals[item.category] = actuals.get(item.category, 0) + item.amount
    details, alerts = [], []
    for category in sorted(set(limits) | set(actuals)):
        limit, spent = limits.get(category), actuals.get(category, 0)
        if limit is None:
            details.append({"category": category, "budgeted": False, "amount": None, "spent": to_rupees(spent), "remaining": None, "utilization": None, "status": "unbudgeted", "alert": None})
            continue
        utilization = spent * 100 / limit
        state = budget_status_code(spent, limit)
        alert = f"You have spent {utilization:.0f}% of your {category.lower()} budget." if state != "normal" else None
        if alert: alerts.append({"category": category, "status": state, "utilization": utilization, "message": alert})
        details.append({"category": category, "budgeted": True, "amount": to_rupees(limit), "spent": to_rupees(spent), "remaining": to_rupees(limit-spent), "utilization": utilization, "status": state, "alert": alert})
    total_budget = sum(limits.values())
    total_spent = sum(actuals.values())
    budgeted_spent = sum(actuals.get(category, 0) for category in limits)
    return {"month": month, "year": resolved_year, "total_budget": to_rupees(total_budget), "total_spent": to_rupees(total_spent),
            "budgeted_spent": to_rupees(budgeted_spent), "remaining": to_rupees(total_budget-total_spent),
            "utilization": budgeted_spent * 100 / total_budget if total_budget else None,
            "within_budget_count": sum(item["budgeted"] and item["status"] != "exceeded" for item in details),
            "exceeded_count": sum(item["status"] == "exceeded" for item in details),
            "unbudgeted_categories": [item for item in details if not item["budgeted"]],
            "categories": details, "alerts": alerts}


@app.get("/api/budgets")
def list_budgets(month: str | None = None, year: int | None = Query(None, ge=1900, le=2200), category: str | None = None,
                 search: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Budget).where(Budget.user_id == user.id)
    if month:
        budget_month(month)
        query = query.where(Budget.month == month)
    elif year: query = query.where(Budget.year == year)
    if category: query = query.where(Budget.category == category)
    if search and search.strip(): query = query.where(or_(Budget.category.ilike(f"%{search.strip()}%"), Budget.description.ilike(f"%{search.strip()}%")))
    rows = db.scalars(query.order_by(Budget.month.desc(), Budget.category).limit(500)).all()
    result = []
    for row in rows:
        spent = db.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.user_id == user.id, Expense.category == row.category, extract("year", Expense.date) == row.year, extract("month", Expense.date) == int(row.month[5:]))) or 0
        result.append(record(row, spent=to_rupees(spent), remaining=to_rupees(row.amount-spent), utilization=spent*100/row.amount,
                             status="exceeded" if spent>row.amount else "critical" if spent*10>=row.amount*9 else "warning" if spent*4>=row.amount*3 else "normal"))
    return result


@app.post("/api/budgets", status_code=201)
def create_budget(payload: BudgetCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    duplicate = db.scalar(select(Budget.id).where(Budget.user_id == user.id, Budget.category == payload.category, Budget.month == payload.month))
    if duplicate: raise HTTPException(409, "A budget already exists for this category and month")
    row = Budget(user_id=user.id, category=payload.category, amount=to_paise(payload.amount), month=payload.month,
                 year=int(payload.month[:4]), description=payload.description.strip())
    db.add(row)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "A budget already exists for this category and month")
    db.refresh(row)
    return record(row)


@app.get("/api/budgets/summary")
def get_budget_summary(month: str | None = None, year: int | None = Query(None, ge=1900, le=2200), user: User = Depends(current_user), db: Session = Depends(get_db)):
    return budget_summary_data(user.id, db, month, year)


@app.get("/api/budgets/history")
def budget_history(year: int | None = Query(None, ge=1900, le=2200), user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Budget.month).where(Budget.user_id == user.id).distinct()
    if year: query = query.where(Budget.year == year)
    months = db.scalars(query.order_by(Budget.month.desc())).all()
    return [budget_summary_data(user.id, db, month=month) for month in months]


@app.get("/api/budgets/{budget_id:int}")
def get_budget(budget_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(Budget).where(Budget.id == budget_id, Budget.user_id == user.id))
    if not row: raise HTTPException(404, "Budget not found")
    summary = budget_summary_data(user.id, db, row.month)
    category = next(item for item in summary["categories"] if item["category"] == row.category)
    return record(row, spent=category["spent"], remaining=category["remaining"], utilization=category["utilization"], status=category["status"])


@app.put("/api/budgets/{budget_id:int}")
def update_budget(budget_id: int, payload: BudgetCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(Budget).where(Budget.id == budget_id, Budget.user_id == user.id))
    if not row: raise HTTPException(404, "Budget not found")
    duplicate = db.scalar(select(Budget.id).where(Budget.user_id == user.id, Budget.category == payload.category, Budget.month == payload.month, Budget.id != row.id))
    if duplicate: raise HTTPException(409, "A budget already exists for this category and month")
    row.category, row.amount, row.month, row.year, row.description = payload.category, to_paise(payload.amount), payload.month, int(payload.month[:4]), payload.description.strip()
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "A budget already exists for this category and month")
    db.refresh(row)
    summary = budget_summary_data(user.id, db, row.month)
    category = next(item for item in summary["categories"] if item["category"] == row.category)
    return record(row, spent=category["spent"], remaining=category["remaining"], utilization=category["utilization"], status=category["status"])


@app.delete("/api/budgets/{budget_id:int}", status_code=204)
def delete_budget(budget_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(Budget).where(Budget.id == budget_id, Budget.user_id == user.id))
    if not row: raise HTTPException(404, "Budget not found")
    db.delete(row); db.commit()


def savings_balance(goal_id, user_id, db):
    goal = db.scalar(select(SavingsGoal).where(SavingsGoal.id == goal_id, SavingsGoal.user_id == user_id))
    if not goal: return None
    signed = func.coalesce(func.sum(case((SavingsTransaction.transaction_type == "contribution", SavingsTransaction.amount), else_=-SavingsTransaction.amount)), 0)
    amount = db.scalar(select(signed).where(SavingsTransaction.goal_id == goal_id, SavingsTransaction.user_id == user_id)) or 0
    return goal.opening_balance + amount


def savings_goal_record(goal, db):
    balance = savings_balance(goal.id, goal.user_id, db) or 0
    remaining = max(0, goal.target_amount - balance)
    today = kolkata_today()
    days = (goal.target_date - today).days if goal.target_date else None
    months = max(1, (goal.target_date.year-today.year)*12 + goal.target_date.month-today.month + (1 if goal.target_date.day >= today.day else 0)) if goal.target_date and days >= 0 else None
    weekly = max(1, (days + 6)//7) if days is not None and days >= 0 else None
    average = db.scalar(select(func.avg(SavingsTransaction.amount)).where(SavingsTransaction.goal_id == goal.id, SavingsTransaction.transaction_type == "contribution"))
    estimated = goal.target_date.isoformat() if goal.target_date and days is not None and days >= 0 else None
    out = record(goal, balance=to_rupees(balance), remaining=to_rupees(remaining), progress=min(100, round(balance*100/goal.target_amount, 1)) if goal.target_amount else 0,
                 overdue=bool(goal.target_date and goal.target_date < today and remaining), months_remaining=months, weeks_remaining=weekly,
                 monthly_target=to_rupees((remaining+months-1)//months) if months else None,
                 weekly_target=to_rupees((remaining+max(1,weekly)-1)//max(1,weekly)) if weekly else None,
                 estimated_completion_date=estimated)
    return out


@app.get("/api/savings")
def list_savings(search: str | None = None, category: str | None = None, status: str | None = None,
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(SavingsGoal).where(SavingsGoal.user_id == user.id).order_by(SavingsGoal.created_at.desc(), SavingsGoal.id.desc())
    if category: query = query.where(SavingsGoal.category == category)
    if status: query = query.where(SavingsGoal.status == status)
    goals = db.scalars(query).all()
    if search: goals = [g for g in goals if search.casefold() in f"{g.name} {g.description} {g.category}".casefold()]
    return [savings_goal_record(g, db) for g in goals]


@app.post("/api/savings", status_code=201)
def create_savings(payload: GoalCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["target_amount"] = to_paise(data["target_amount"])
    data["opening_balance"] = data["balance"] = 0
    data["name"] = data["name"].strip()
    goal = SavingsGoal(user_id=user.id, **data)
    db.add(goal); db.commit(); db.refresh(goal)
    return savings_goal_record(goal, db)


@app.get("/api/savings/summary")
def savings_summary(month: str | None = None, year: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    period, resolved_year, month_num = budget_month(month, year)
    goals = db.scalars(select(SavingsGoal).where(SavingsGoal.user_id == user.id).order_by(SavingsGoal.id)).all()
    transactions = db.scalars(select(SavingsTransaction).where(SavingsTransaction.user_id == user.id)).all()
    if period: chosen = [x for x in transactions if x.date.year == resolved_year and x.date.month == month_num]
    else: chosen = [x for x in transactions if x.date.year == resolved_year]
    balances = {g.id: savings_balance(g.id, user.id, db) or 0 for g in goals}
    by_goal = [{"id": g.id, "name": g.name, "category": g.category, "balance": to_rupees(balances[g.id]), "target_amount": to_rupees(g.target_amount)} for g in goals]
    monthly_expenses = db.scalars(select(Expense).where(Expense.user_id == user.id, Expense.date >= date(resolved_year, 1, 1), Expense.date <= date(resolved_year, 12, 31))).all()
    exp_by_month = {}
    for e in monthly_expenses: exp_by_month[e.date.month] = exp_by_month.get(e.date.month, 0) + e.amount
    avg_exp = sum(exp_by_month.values()) / max(1, len(exp_by_month))
    activity_months = range(1, 13) if period is None else [month_num]
    monthly_activity = []
    for number in activity_months:
        entries = [x for x in chosen if x.date.month == number]
        monthly_activity.append({"month": datetime(resolved_year, number, 1).strftime("%b"),
                                 "contributions": to_rupees(sum(x.amount for x in entries if x.transaction_type == "contribution")),
                                 "withdrawals": to_rupees(sum(x.amount for x in entries if x.transaction_type == "withdrawal"))})
    return {"period": period or str(resolved_year), "total_saved": to_rupees(sum(balances.values())), "total_target": to_rupees(sum(g.target_amount for g in goals)),
            "total_remaining": to_rupees(sum(max(0, g.target_amount-balances[g.id]) for g in goals)),
            "active_goals": sum(g.status == "active" for g in goals), "completed_goals": sum(g.status == "completed" for g in goals),
            "contributions": to_rupees(sum(x.amount for x in chosen if x.transaction_type == "contribution")),
            "withdrawals": to_rupees(sum(x.amount for x in chosen if x.transaction_type == "withdrawal")),
            "emergency_balance": to_rupees(sum(balances[g.id] for g in goals if g.category == "Emergency fund")),
            "emergency_expense_average": to_rupees(round(avg_exp)), "emergency_target_low": to_rupees(round(avg_exp*3)), "emergency_target_high": to_rupees(round(avg_exp*6)),
            "goals": [savings_goal_record(g, db) for g in goals], "by_goal": by_goal,
            "monthly_activity": monthly_activity,
            "transactions": [savings_transaction_record(x) for x in sorted(chosen, key=lambda x: (x.date, x.id), reverse=True)]}


def savings_transaction_record(tx):
    return {"id": tx.id, "user_id": tx.user_id, "goal_id": tx.goal_id, "transaction_type": tx.transaction_type,
            "amount": to_rupees(tx.amount), "date": tx.date.isoformat(), "notes": tx.notes, "request_id": tx.request_id}


@app.get("/api/savings/{goal_id:int}")
def get_savings(goal_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    goal = db.scalar(select(SavingsGoal).where(SavingsGoal.id == goal_id, SavingsGoal.user_id == user.id))
    if not goal: raise HTTPException(404, "Savings goal not found")
    row = savings_goal_record(goal, db)
    row["transactions"] = [savings_transaction_record(x) for x in db.scalars(select(SavingsTransaction).where(SavingsTransaction.goal_id == goal.id, SavingsTransaction.user_id == user.id).order_by(SavingsTransaction.date.desc(), SavingsTransaction.id.desc())).all()]
    return row


@app.put("/api/savings/{goal_id:int}")
def update_savings(goal_id: int, payload: GoalCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    goal = db.scalar(select(SavingsGoal).where(SavingsGoal.id == goal_id, SavingsGoal.user_id == user.id))
    if not goal: raise HTTPException(404, "Savings goal not found")
    for k, v in payload.model_dump().items(): setattr(goal, k, to_paise(v) if k == "target_amount" else v)
    goal.name = goal.name.strip(); db.commit(); db.refresh(goal)
    return savings_goal_record(goal, db)


@app.delete("/api/savings/{goal_id:int}", status_code=204)
def delete_savings(goal_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    goal = db.scalar(select(SavingsGoal).where(SavingsGoal.id == goal_id, SavingsGoal.user_id == user.id))
    if not goal: raise HTTPException(404, "Savings goal not found")
    if db.scalar(select(SavingsTransaction.id).where(SavingsTransaction.goal_id == goal.id).limit(1)):
        raise HTTPException(409, "This goal has transaction history. Delete its transactions first to preserve your records.")
    if (savings_balance(goal.id, user.id, db) or 0) > 0:
        raise HTTPException(409, "Withdraw the remaining goal balance before deleting this goal.")
    db.delete(goal); db.commit()


def post_savings_transaction(goal_id, payload, kind, user, db):
    # Serialize balance checks across concurrent withdrawal requests (SQLite and PostgreSQL).
    db.execute(update(SavingsGoal).where(SavingsGoal.id == goal_id, SavingsGoal.user_id == user.id).values(balance=SavingsGoal.balance))
    goal = db.scalar(select(SavingsGoal).where(SavingsGoal.id == goal_id, SavingsGoal.user_id == user.id))
    if not goal: raise HTTPException(404, "Savings goal not found")
    amount = to_paise(payload.amount)
    if payload.request_id:
        prior = db.scalar(select(SavingsTransaction).where(SavingsTransaction.user_id == user.id, SavingsTransaction.request_id == payload.request_id))
        if prior:
            if prior.goal_id == goal_id and prior.transaction_type == kind and prior.amount == amount and prior.date == payload.date: return {**savings_transaction_record(prior), "balance": to_rupees(savings_balance(goal_id, user.id, db) or 0)}
            raise HTTPException(409, "This request id was already used for a different savings transaction")
    if kind == "withdrawal" and (savings_balance(goal_id, user.id, db) or 0) < amount: raise HTTPException(422, "Withdrawal exceeds the available goal balance")
    tx = SavingsTransaction(user_id=user.id, goal_id=goal_id, transaction_type=kind, amount=amount, date=payload.date,
                            notes=(payload.notes or payload.note or "").strip(), request_id=payload.request_id)
    db.add(tx)
    if kind == "contribution": goal.balance += amount
    else: goal.balance -= amount
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "This savings transaction was already submitted")
    db.refresh(tx)
    return {**savings_transaction_record(tx), "balance": to_rupees(savings_balance(goal_id, user.id, db) or 0)}


@app.get("/api/savings/{goal_id:int}/contributions")
def savings_history(goal_id: int, transaction_type: str | None = None, date_from: date | None = None, date_to: date | None = None,
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not db.scalar(select(SavingsGoal.id).where(SavingsGoal.id == goal_id, SavingsGoal.user_id == user.id)): raise HTTPException(404, "Savings goal not found")
    query = select(SavingsTransaction).where(SavingsTransaction.goal_id == goal_id, SavingsTransaction.user_id == user.id)
    if transaction_type in ("contribution", "withdrawal"): query = query.where(SavingsTransaction.transaction_type == transaction_type)
    if date_from: query = query.where(SavingsTransaction.date >= date_from)
    if date_to: query = query.where(SavingsTransaction.date <= date_to)
    return [savings_transaction_record(x) for x in db.scalars(query.order_by(SavingsTransaction.date.desc(), SavingsTransaction.id.desc())).all()]


@app.post("/api/savings/{goal_id:int}/contributions", status_code=201)
def contribute(goal_id: int, payload: Contribution, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if payload.request_id and db.scalar(select(SavingsTransaction.id).where(SavingsTransaction.user_id == user.id, SavingsTransaction.request_id == payload.request_id)):
        response.status_code = 200
    return post_savings_transaction(goal_id, payload, "contribution", user, db)


@app.post("/api/savings/{goal_id:int}/withdrawals", status_code=201)
def withdraw_savings(goal_id: int, payload: Contribution, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if payload.request_id and db.scalar(select(SavingsTransaction.id).where(SavingsTransaction.user_id == user.id, SavingsTransaction.request_id == payload.request_id)):
        response.status_code = 200
    return post_savings_transaction(goal_id, payload, "withdrawal", user, db)


@app.put("/api/savings/{goal_id:int}/contributions/{transaction_id:int}")
def update_savings_transaction(goal_id: int, transaction_id: int, payload: Contribution, user: User = Depends(current_user), db: Session = Depends(get_db)):
    tx = db.scalar(select(SavingsTransaction).where(SavingsTransaction.id == transaction_id, SavingsTransaction.goal_id == goal_id, SavingsTransaction.user_id == user.id, SavingsTransaction.transaction_type == "contribution"))
    if not tx: raise HTTPException(404, "Contribution not found")
    goal = db.get(SavingsGoal, goal_id); goal.balance += to_paise(payload.amount)-tx.amount
    tx.amount, tx.date, tx.notes = to_paise(payload.amount), payload.date, (payload.notes or payload.note or "").strip()
    db.commit(); db.refresh(tx); return savings_transaction_record(tx)


@app.delete("/api/savings/{goal_id:int}/contributions/{transaction_id:int}", status_code=204)
def delete_savings_transaction(goal_id: int, transaction_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    tx = db.scalar(select(SavingsTransaction).where(SavingsTransaction.id == transaction_id, SavingsTransaction.goal_id == goal_id, SavingsTransaction.user_id == user.id, SavingsTransaction.transaction_type == "contribution"))
    if not tx: raise HTTPException(404, "Contribution not found")
    goal = db.get(SavingsGoal, goal_id); goal.balance -= tx.amount; db.delete(tx); db.commit()


@app.put("/api/savings/{goal_id:int}/transactions/{transaction_id:int}")
def edit_savings_transaction(goal_id: int, transaction_id: int, payload: Contribution, user: User = Depends(current_user), db: Session = Depends(get_db)):
    tx = db.scalar(select(SavingsTransaction).where(SavingsTransaction.id == transaction_id, SavingsTransaction.goal_id == goal_id, SavingsTransaction.user_id == user.id))
    if not tx: raise HTTPException(404, "Savings transaction not found")
    goal = db.get(SavingsGoal, goal_id); amount = to_paise(payload.amount)
    if tx.transaction_type == "withdrawal" and (savings_balance(goal_id, user.id, db) or 0) + tx.amount < amount:
        raise HTTPException(422, "Withdrawal exceeds the available goal balance")
    if tx.transaction_type == "contribution": goal.balance += amount - tx.amount
    else: goal.balance += tx.amount - amount
    tx.amount, tx.date, tx.notes = amount, payload.date, (payload.notes or payload.note or "").strip()
    db.commit(); db.refresh(tx); return savings_transaction_record(tx)


@app.delete("/api/savings/{goal_id:int}/transactions/{transaction_id:int}", status_code=204)
def delete_any_savings_transaction(goal_id: int, transaction_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    tx = db.scalar(select(SavingsTransaction).where(SavingsTransaction.id == transaction_id, SavingsTransaction.goal_id == goal_id, SavingsTransaction.user_id == user.id))
    if not tx: raise HTTPException(404, "Savings transaction not found")
    goal = db.get(SavingsGoal, goal_id)
    if tx.transaction_type == "withdrawal": goal.balance += tx.amount
    else: goal.balance -= tx.amount
    db.delete(tx); db.commit()


REMINDER_CATEGORIES = ("Rent", "Electricity", "Water", "Internet", "Mobile recharge", "Subscriptions", "Education fees", "Insurance", "Other")
RECURRENCES = ("once", "weekly", "monthly", "quarterly", "yearly", "custom")


def recurrence_next(day, frequency, interval_days=None, anchor_day=None):
    if frequency == "weekly": return day + timedelta(days=7)
    if frequency == "custom": return day + timedelta(days=interval_days or 1)
    months = {"monthly": 1, "quarterly": 3, "yearly": 12}.get(frequency)
    if not months: return None
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12); month += 1
    return date(year, month, min(anchor_day or day.day, calendar.monthrange(year, month)[1]))


def reminder_status(item, today=None):
    today = today or kolkata_today()
    if item.status == "cancelled": return "cancelled"
    if item.paid or item.status == "paid": return "paid"
    return "overdue" if item.due_date < today else "due_today" if item.due_date == today else "upcoming"


def reminder_record(item, db=None):
    out = record(item, amount=to_rupees(item.amount), actual_paid_amount=to_rupees(item.actual_paid_amount) if item.actual_paid_amount is not None else None,
                 status=reminder_status(item), paid=item.paid, recurrence=item.recurrence or "once")
    out["due_date"] = item.due_date.isoformat()
    if item.paid_at: out["paid_at"] = item.paid_at.isoformat()
    if db is not None and item.schedule_id:
        schedule = db.get(RecurringSchedule, item.schedule_id)
        out["series_active"] = bool(schedule and schedule.active)
        out["interval_days"] = schedule.interval_days if schedule else None
        out["end_date"] = schedule.end_date.isoformat() if schedule and schedule.end_date else None
    else: out["series_active"] = False
    return out


def ensure_reminder_occurrences(user_id, db, horizon=None):
    horizon = horizon or (kolkata_today() + timedelta(days=366))
    schedules = db.scalars(select(RecurringSchedule).where(RecurringSchedule.user_id == user_id, RecurringSchedule.active.is_(True))).all()
    changed = False
    for schedule in schedules:
        last = db.scalar(select(func.max(Reminder.due_date)).where(Reminder.user_id == user_id, Reminder.schedule_id == schedule.id)) or schedule.start_date
        next_day = recurrence_next(last, schedule.frequency, schedule.interval_days, schedule.start_date.day)
        while next_day and next_day <= horizon and (not schedule.end_date or next_day <= schedule.end_date):
            db.add(Reminder(user_id=user_id, title=schedule.title, amount=schedule.amount, due_date=next_day, category=schedule.category,
                            recurrence=schedule.frequency, description=schedule.description, status="upcoming", paid=False,
                            schedule_id=schedule.id, reminder_days=schedule.reminder_days))
            changed = True
            last = next_day
            next_day = recurrence_next(last, schedule.frequency, schedule.interval_days, schedule.start_date.day)
    if changed:
        try: db.commit()
        except IntegrityError: db.rollback()


def owned_reminder(reminder_id, user_id, db):
    row = db.scalar(select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == user_id))
    if not row: raise HTTPException(404, "Reminder not found")
    return row


@app.get("/api/reminders")
def list_reminders(search: str | None = None, category: str | None = None, status: str | None = None,
                   date_from: date | None = None, date_to: date | None = None, limit: int = Query(500, ge=1, le=1000),
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
    if date_from and date_to and date_from > date_to: raise HTTPException(422, "date_from must be on or before date_to")
    ensure_reminder_occurrences(user.id, db)
    query = select(Reminder).where(Reminder.user_id == user.id)
    if category: query = query.where(Reminder.category == category)
    if date_from: query = query.where(Reminder.due_date >= date_from)
    if date_to: query = query.where(Reminder.due_date <= date_to)
    rows = db.scalars(query.order_by(Reminder.due_date, Reminder.id).limit(limit)).all()
    result = [reminder_record(x, db) for x in rows]
    if search: result = [x for x in result if search.casefold() in f"{x['title']} {x['category']} {x['description']}".casefold()]
    if status: result = [x for x in result if x["status"] == status]
    return result


@app.post("/api/reminders", status_code=201)
def create_reminder(payload: ReminderCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = payload.model_dump()
    amount = to_paise(data.pop("amount")); end_date = data.pop("end_date"); interval_days = data.get("interval_days")
    effective_days = payload.reminder_days or notification_preferences(user.id, db).advance_days
    schedule_id = None
    if payload.recurrence != "once":
        schedule = RecurringSchedule(user_id=user.id, title=payload.title, amount=amount, category=payload.category,
            description=payload.description, frequency=payload.recurrence, interval_days=interval_days,
            start_date=payload.due_date, end_date=end_date, reminder_days=effective_days, active=True)
        db.add(schedule); db.flush(); schedule_id = schedule.id
    row = Reminder(user_id=user.id, title=payload.title, amount=amount, due_date=payload.due_date, category=payload.category,
        recurrence=payload.recurrence, description=payload.description, reminder_days=effective_days,
        status="upcoming", paid=False, schedule_id=schedule_id)
    db.add(row); db.commit(); db.refresh(row)
    if schedule_id: ensure_reminder_occurrences(user.id, db)
    return reminder_record(row, db)


@app.get("/api/reminders/summary")
def reminder_summary(month: str | None = None, year: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    period, y, m = budget_month(month, year)
    ensure_reminder_occurrences(user.id, db)
    rows = db.scalars(select(Reminder).where(Reminder.user_id == user.id, Reminder.status != "cancelled")).all()
    today = kolkata_today(); open_rows = [x for x in rows if reminder_status(x, today) not in ("paid", "cancelled")]
    monthly = [x for x in open_rows if x.due_date.year == y and (m is None or x.due_date.month == m)]
    within_week = [x for x in open_rows if today <= x.due_date <= today + timedelta(days=7)]
    overdue = [x for x in open_rows if x.due_date < today]
    obligations = db.scalars(select(Debt).where(Debt.user_id == user.id, Debt.due_date.is_not(None), Debt.due_date >= today, Debt.due_date <= today + timedelta(days=7))).all()
    payable, receivable = 0, 0
    for debt in obligations:
        _, remaining, _ = debt_state(debt)
        if debt.direction == "borrowed": payable += remaining
        else: receivable += remaining
    debt_period = db.scalars(select(Debt).where(Debt.user_id == user.id, Debt.due_date.is_not(None), Debt.due_date >= date(y, m, 1) if m else Debt.due_date >= date(y, 1, 1), Debt.due_date <= date(y, m, calendar.monthrange(y, m)[1]) if m else Debt.due_date <= date(y, 12, 31))).all()
    payable_period, receivable_period = 0, 0
    for debt in debt_period:
        _, remaining, _ = debt_state(debt)
        if debt.direction == "borrowed": payable_period += remaining
        else: receivable_period += remaining
    due_month = sum(x.amount for x in monthly)
    due_week_amount = sum(x.amount for x in within_week)
    overdue_amount = sum(x.amount for x in overdue)
    all_unpaid = sum(x.amount for x in open_rows)
    income_query = select(Income).where(Income.user_id == user.id, extract("year", Income.date) == y)
    expense_query = select(Expense).where(Expense.user_id == user.id, extract("year", Expense.date) == y)
    if m:
        income_query = income_query.where(extract("month", Income.date) == m)
        expense_query = expense_query.where(extract("month", Expense.date) == m)
    incomes = db.scalars(income_query).all(); expenses = db.scalars(expense_query).all()
    debt_dates = select(Debt).where(Debt.user_id == user.id, extract("year", Debt.date) == y)
    repayment_dates = select(DebtRepayment).where(DebtRepayment.user_id == user.id, extract("year", DebtRepayment.date) == y)
    if m:
        debt_dates = debt_dates.where(extract("month", Debt.date) == m)
        repayment_dates = repayment_dates.where(extract("month", DebtRepayment.date) == m)
    debt_records = db.scalars(debt_dates).all(); repayments = db.scalars(repayment_dates).all()
    debt_by_id = {x.id:x for x in db.scalars(select(Debt).where(Debt.user_id == user.id)).all()}
    debt_net = sum(x.amount if x.direction == "borrowed" else -x.amount for x in debt_records)
    debt_net += sum(x.amount if debt_by_id.get(x.debt_id) and debt_by_id[x.debt_id].direction == "lent" else -x.amount for x in repayments)
    savings_query = select(SavingsTransaction).where(SavingsTransaction.user_id == user.id, extract("year", SavingsTransaction.date) == y)
    if m: savings_query = savings_query.where(extract("month", SavingsTransaction.date) == m)
    savings_net = sum(x.amount if x.transaction_type == "withdrawal" else -x.amount for x in db.scalars(savings_query).all())
    cash_change = sum(x.amount for x in incomes) - sum(x.amount for x in expenses) + debt_net + savings_net
    return {"period": period or str(y), "total_unpaid_bills": to_rupees(all_unpaid),
            "due_within_seven_days": to_rupees(due_week_amount), "overdue_payment_amount": to_rupees(overdue_amount),
            "upcoming_monthly_obligations": to_rupees(due_month + payable_period),
            "available_cash_after_upcoming_obligations": to_rupees(cash_change - due_month - payable_period),
            "estimated_obligations": True, "payable_debt_due_within_seven_days": to_rupees(payable),
            "receivable_debt_due_within_seven_days": to_rupees(receivable),
            "payable_debt_due_this_period": to_rupees(payable_period), "receivable_debt_due_this_period": to_rupees(receivable_period),
            "bills_due_this_period": [reminder_record(x, db) for x in monthly]}


@app.get("/api/reminders/calendar")
def reminder_calendar(month: str | None = None, year: int | None = None, category: str | None = None,
                      status: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    period, y, m = budget_month(month, year)
    ensure_reminder_occurrences(user.id, db)
    start = date(y, m, 1) if m else date(y, 1, 1)
    end = date(y, m, calendar.monthrange(y, m)[1]) if m else date(y, 12, 31)
    bills = db.scalars(select(Reminder).where(Reminder.user_id == user.id, Reminder.due_date >= start, Reminder.due_date <= end)).all()
    result = []
    for row in bills:
        item = reminder_record(row, db)
        if category and row.category != category: continue
        if status and item["status"] != status: continue
        result.append({**item, "event_type":"bill", "obligation_type":"bill"})
    debts = db.scalars(select(Debt).where(Debt.user_id == user.id, Debt.due_date >= start, Debt.due_date <= end)).all()
    for debt in debts:
        _, remaining, state = debt_state(debt)
        if remaining <= 0: continue
        event_status = "overdue" if debt.due_date < kolkata_today() else "due_today" if debt.due_date == kolkata_today() else "upcoming"
        category_name = "Friend repayment"
        if category and category != category_name: continue
        if status and status != event_status: continue
        result.append({"id": f"debt-{debt.id}", "source_id": debt.id, "title": f"{debt.friend.name if debt.friend else debt.friend_name} · {('Pay back' if debt.direction == 'borrowed' else 'Receive')}",
            "amount": to_rupees(remaining), "due_date": debt.due_date.isoformat(), "category": category_name, "status": event_status,
            "event_type":"debt", "obligation_type":"payable" if debt.direction == "borrowed" else "receivable", "debt_status":state})
    return sorted(result, key=lambda x: (x["due_date"], x["event_type"], str(x["id"])))


@app.get("/api/reminders/recurring")
def list_recurring(user: User = Depends(current_user), db: Session = Depends(get_db)):
    schedules = db.scalars(select(RecurringSchedule).where(RecurringSchedule.user_id == user.id).order_by(RecurringSchedule.start_date.desc())).all()
    return [{"id":x.id,"title":x.title,"amount":to_rupees(x.amount),"category":x.category,"description":x.description,
        "frequency":x.frequency,"interval_days":x.interval_days,"start_date":x.start_date.isoformat(),"end_date":x.end_date.isoformat() if x.end_date else None,
        "active":x.active,"reminder_days":x.reminder_days} for x in schedules]


@app.put("/api/reminders/{reminder_id:int}")
def update_reminder(reminder_id: int, payload: ReminderCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = owned_reminder(reminder_id, user.id, db)
    if row.paid: raise HTTPException(409, "Paid reminders cannot be edited")
    effective_days = payload.reminder_days or notification_preferences(user.id, db).advance_days
    if row.schedule_id:
        schedule = db.get(RecurringSchedule, row.schedule_id)
        if payload.recurrence == "once":
            if schedule:
                schedule.active = False
                db.query(Reminder).filter(Reminder.schedule_id == schedule.id, Reminder.due_date > row.due_date, Reminder.paid.is_(False)).delete(synchronize_session=False)
            row.schedule_id = None
        elif schedule:
            schedule.title, schedule.amount, schedule.category = payload.title, to_paise(payload.amount), payload.category
            schedule.description, schedule.frequency = payload.description, payload.recurrence
            schedule.interval_days, schedule.end_date = payload.interval_days, payload.end_date
            schedule.reminder_days, schedule.active = effective_days, True
            schedule.start_date = payload.due_date
            db.query(Reminder).filter(Reminder.schedule_id == schedule.id, Reminder.due_date > row.due_date, Reminder.paid.is_(False)).delete(synchronize_session=False)
        else: row.schedule_id = None
    elif payload.recurrence != "once":
        schedule = RecurringSchedule(user_id=user.id, title=payload.title, amount=to_paise(payload.amount), category=payload.category,
            description=payload.description, frequency=payload.recurrence, interval_days=payload.interval_days,
            start_date=payload.due_date, end_date=payload.end_date, reminder_days=effective_days, active=True)
        db.add(schedule); db.flush(); row.schedule_id = schedule.id
    row.title, row.amount, row.due_date = payload.title, to_paise(payload.amount), payload.due_date
    row.category, row.recurrence, row.description = payload.category, payload.recurrence, payload.description
    row.reminder_days, row.status = effective_days, "upcoming"
    db.commit(); db.refresh(row)
    if row.schedule_id: ensure_reminder_occurrences(user.id, db)
    return reminder_record(row, db)


@app.get("/api/reminders/{reminder_id:int}")
def get_reminder(reminder_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return reminder_record(owned_reminder(reminder_id, user.id, db), db)


@app.delete("/api/reminders/{reminder_id:int}", status_code=204)
def delete_reminder(reminder_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = owned_reminder(reminder_id, user.id, db)
    if row.paid: raise HTTPException(409, "Paid reminders are preserved in payment history and cannot be deleted")
    if row.schedule_id:
        row.status = "cancelled"
    else: db.delete(row)
    db.commit()


@app.post("/api/reminders/{reminder_id:int}/cancel")
def cancel_reminder_occurrence(reminder_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = owned_reminder(reminder_id, user.id, db)
    if row.paid: raise HTTPException(409, "Paid reminders cannot be cancelled")
    if row.status == "cancelled": return reminder_record(row, db)
    row.status = "cancelled"; db.commit(); db.refresh(row)
    return reminder_record(row, db)


@app.delete("/api/reminders/recurring/{schedule_id:int}", status_code=204)
def cancel_recurring(schedule_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    schedule = db.scalar(select(RecurringSchedule).where(RecurringSchedule.id == schedule_id, RecurringSchedule.user_id == user.id))
    if not schedule: raise HTTPException(404, "Recurring schedule not found")
    schedule.active = False
    db.query(Reminder).filter(Reminder.user_id == user.id, Reminder.schedule_id == schedule.id, Reminder.paid.is_(False)).update({Reminder.status:"cancelled"}, synchronize_session=False)
    db.commit()


@app.post("/api/reminders/{reminder_id:int}/mark-paid")
def mark_reminder_paid(reminder_id: int, payload: ReminderPaymentCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = owned_reminder(reminder_id, user.id, db)
    if row.paid or row.status == "paid": raise HTTPException(409, "This bill is already marked paid")
    if row.status == "cancelled": raise HTTPException(409, "Cancelled reminders cannot be paid")
    if payload.expense_id and payload.create_expense: raise HTTPException(422, "Choose an existing expense or create one, not both")
    expense = None
    if payload.expense_id:
        expense = db.scalar(select(Expense).where(Expense.id == payload.expense_id, Expense.user_id == user.id))
        if not expense: raise HTTPException(404, "Expense not found")
        if db.scalar(select(ReminderPayment.id).where(ReminderPayment.expense_id == expense.id)) or db.scalar(select(Reminder.id).where(Reminder.expense_id == expense.id)):
            raise HTTPException(409, "This expense is already linked to a bill payment")
    if row.expense_id and not payload.expense_id and not payload.create_expense: raise HTTPException(409, "A linked expense already exists for this bill")
    actual = to_paise(payload.actual_amount if payload.actual_amount is not None else Decimal(row.amount) / 100)
    if expense and expense.amount != actual:
        raise HTTPException(422, "The linked expense amount must match the actual bill payment")
    if payload.create_expense:
        exp_category = row.category if row.category in {"Rent","Electricity","Food","Groceries","Travel","Clothes","Shopping","Education","Entertainment","Subscriptions","Healthcare","Other"} else "Other"
        expense = Expense(user_id=user.id, amount=actual, category=exp_category, date=payload.paid_date,
                          description=f"Bill payment: {row.title}"[:500], payment_method="Bank transfer", notes="Created from bill payment")
        db.add(expense); db.flush()
    row.paid, row.status, row.paid_at, row.actual_paid_amount = True, "paid", payload.paid_date, actual
    row.expense_id = expense.id if expense else None
    payment = ReminderPayment(user_id=user.id, reminder_id=row.id, paid_date=payload.paid_date, actual_amount=actual, expense_id=expense.id if expense else None)
    db.add(payment); db.commit(); db.refresh(row)
    return {**reminder_record(row, db), "payment_id":payment.id}


@app.get("/api/reminders/{reminder_id:int}/payments")
def reminder_payments(reminder_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_reminder(reminder_id, user.id, db)
    rows = db.scalars(select(ReminderPayment).where(ReminderPayment.reminder_id == reminder_id, ReminderPayment.user_id == user.id).order_by(ReminderPayment.paid_date.desc(), ReminderPayment.id.desc())).all()
    return [{"id":x.id,"reminder_id":x.reminder_id,"paid_date":x.paid_date.isoformat(),"actual_amount":to_rupees(x.actual_amount),"expense_id":x.expense_id} for x in rows]


def notification_preferences(user_id, db):
    pref = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user_id))
    if pref: return pref
    pref = NotificationPreference(user_id=user_id, advance_days=[3,1,0], browser_enabled=False)
    db.add(pref); db.commit(); db.refresh(pref)
    return pref


@app.get("/api/notifications/preferences")
def get_notification_preferences(user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = notification_preferences(user.id, db)
    return {"advance_days":p.advance_days,"browser_enabled":p.browser_enabled}


@app.put("/api/notifications/preferences")
def set_notification_preferences(payload: NotificationPreferenceUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = notification_preferences(user.id, db)
    p.advance_days, p.browser_enabled = payload.advance_days, payload.browser_enabled
    db.query(Reminder).filter(Reminder.user_id == user.id, Reminder.paid.is_(False), Reminder.status != "cancelled").update({Reminder.reminder_days: payload.advance_days}, synchronize_session=False)
    db.query(RecurringSchedule).filter(RecurringSchedule.user_id == user.id, RecurringSchedule.active.is_(True)).update({RecurringSchedule.reminder_days: payload.advance_days}, synchronize_session=False)
    db.commit()
    return {"advance_days":p.advance_days,"browser_enabled":p.browser_enabled}


@app.get("/api/notifications")
def list_notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    pref = notification_preferences(user.id, db); today = kolkata_today()
    ensure_reminder_occurrences(user.id, db)
    reminders = db.scalars(select(Reminder).where(Reminder.user_id == user.id, Reminder.paid.is_(False), Reminder.status != "cancelled")).all()
    for row in reminders:
        for advance in (row.reminder_days or pref.advance_days):
            due_notification = row.due_date - timedelta(days=advance)
            if due_notification <= today <= row.due_date:
                title = f"{row.title} is due" if advance == 0 else f"{row.title} due in {advance} day{'s' if advance != 1 else ''}"
                db.add(Notification(user_id=user.id, source_type="bill", source_id=row.id, title=title,
                    message=f"{row.category} · ₹{to_rupees(row.amount):,.2f} · due {row.due_date.isoformat()}", remind_on=due_notification))
    debts = db.scalars(select(Debt).where(Debt.user_id == user.id, Debt.due_date.is_not(None), Debt.due_date >= today, Debt.due_date <= today + timedelta(days=max(pref.advance_days or [0])))).all()
    for debt in debts:
        _, remaining, _ = debt_state(debt)
        if remaining:
            for advance in pref.advance_days:
                due_notification = debt.due_date - timedelta(days=advance)
                if due_notification <= today <= debt.due_date:
                    db.add(Notification(user_id=user.id, source_type="debt", source_id=debt.id,
                        title="Friend repayment deadline", message=f"{debt.friend.name if debt.friend else debt.friend_name} · ₹{to_rupees(remaining):,.2f} · due {debt.due_date.isoformat()}", remind_on=due_notification))
    try: db.commit()
    except IntegrityError: db.rollback()
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc(), Notification.id.desc()).limit(100)).all()
    return [{"id":x.id,"source_type":x.source_type,"source_id":x.source_id,"title":x.title,"message":x.message,"remind_on":x.remind_on.isoformat(),"read":x.read,"created_at":x.created_at} for x in rows]


@app.post("/api/notifications/{notification_id:int}/read")
def mark_notification_read(notification_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id))
    if not item: raise HTTPException(404, "Notification not found")
    item.read = True; db.commit()
    return {"id":item.id,"read":item.read}


def debt_state(item):
    paid = sum(x.amount for x in item.repayments)
    remaining = max(0, item.amount - paid)
    status = "fully_paid" if remaining == 0 else "overdue" if item.due_date and item.due_date < kolkata_today() else "partial" if paid else "unpaid"
    return paid, remaining, status


def debt_record(item):
    paid, remaining, status = debt_state(item)
    return record(item, friend_name=item.friend.name if item.friend else item.friend_name,
                  repaid=to_rupees(paid), remaining=to_rupees(remaining), status=status,
                  repayment_count=len(item.repayments))


def friend_totals(friend_id, user_id, db):
    debts = db.scalars(select(Debt).where(Debt.friend_id == friend_id, Debt.user_id == user_id)).all()
    result = {"borrowed": 0, "lent": 0, "repaid": 0, "received": 0, "outstanding_borrowed": 0, "outstanding_lent": 0}
    for item in debts:
        paid, remaining, _ = debt_state(item)
        result[item.direction] += item.amount
        result["repaid" if item.direction == "borrowed" else "received"] += paid
        result["outstanding_borrowed" if item.direction == "borrowed" else "outstanding_lent"] += remaining
    return {key: to_rupees(value) for key, value in result.items()}


@app.get("/api/friends")
def list_friends(search: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Friend).where(Friend.user_id == user.id)
    if search and search.strip(): query = query.where(or_(Friend.name.ilike(f"%{search.strip()}%"), Friend.nickname.ilike(f"%{search.strip()}%"), Friend.email.ilike(f"%{search.strip()}%")))
    return [record(friend, totals=friend_totals(friend.id, user.id, db)) for friend in db.scalars(query.order_by(Friend.name)).all()]


@app.post("/api/friends", status_code=201)
def create_friend(payload: FriendCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    friend = Friend(user_id=user.id, **{k: (v.strip() if isinstance(v, str) else v) for k, v in payload.model_dump().items()})
    db.add(friend); db.commit(); db.refresh(friend)
    return record(friend, totals=friend_totals(friend.id, user.id, db))


def owned_friend(friend_id, user_id, db):
    friend = db.scalar(select(Friend).where(Friend.id == friend_id, Friend.user_id == user_id))
    if not friend: raise HTTPException(404, "Friend not found")
    return friend


@app.get("/api/friends/{friend_id}")
def friend_detail(friend_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    friend = owned_friend(friend_id, user.id, db)
    debts = db.scalars(select(Debt).where(Debt.friend_id == friend.id, Debt.user_id == user.id).order_by(Debt.date.desc(), Debt.id.desc())).all()
    history = []
    for debt in debts:
        history.extend(record(rep, direction=debt.direction, debt_id=debt.id, description=debt.description) for rep in debt.repayments)
    history.sort(key=lambda x: (x["date"], x["id"]), reverse=True)
    return record(friend, totals=friend_totals(friend.id, user.id, db), debts=[debt_record(x) for x in debts], repayment_history=history)


@app.put("/api/friends/{friend_id}")
def update_friend(friend_id: int, payload: FriendCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    friend = owned_friend(friend_id, user.id, db)
    for key, value in payload.model_dump().items(): setattr(friend, key, value.strip() if isinstance(value, str) else value)
    db.commit(); db.refresh(friend)
    return record(friend, totals=friend_totals(friend.id, user.id, db))


@app.delete("/api/friends/{friend_id}", status_code=204)
def delete_friend(friend_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    friend = owned_friend(friend_id, user.id, db)
    if db.scalar(select(func.count(Debt.id)).where(Debt.friend_id == friend.id)):
        raise HTTPException(409, "This friend has financial records. Remove those records first.")
    db.delete(friend); db.commit()


@app.get("/api/debts")
def list_debts(month: str | None = None, year: int | None = Query(None, ge=1900, le=2200), friend_id: int | None = None,
               direction: str | None = Query(None, pattern="^(borrowed|lent)$"), status: str | None = None,
               user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Debt).where(Debt.user_id == user.id)
    if friend_id: query = query.where(Debt.friend_id == friend_id)
    if direction: query = query.where(Debt.direction == direction)
    if month:
        try: y, m = map(int, month.split("-")); date(y, m, 1)
        except Exception: raise HTTPException(422, "Month must use YYYY-MM format")
        query = query.where(extract("year", Debt.date) == y, extract("month", Debt.date) == m)
    elif year: query = query.where(extract("year", Debt.date) == year)
    rows = db.scalars(query.order_by(Debt.date.desc(), Debt.id.desc())).all()
    return [out for row in rows if (out := debt_record(row)) and (not status or out["status"] == status)]


@app.post("/api/debts", status_code=201)
def create_debt(payload: DebtCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if payload.friend_id:
        friend = owned_friend(payload.friend_id, user.id, db)
    elif payload.friend_name and payload.friend_name.strip():
        name = payload.friend_name.strip()
        friend = db.scalar(select(Friend).where(Friend.user_id == user.id, func.lower(Friend.name) == name.lower()))
        if not friend:
            friend = Friend(user_id=user.id, name=name); db.add(friend); db.flush()
    else: raise HTTPException(422, "Choose a friend")
    row = Debt(user_id=user.id, friend_id=friend.id, friend_name=friend.name, direction=payload.direction,
               amount=to_paise(payload.amount), date=payload.date, due_date=payload.due_date, description=payload.description)
    db.add(row); db.commit(); db.refresh(row)
    return debt_record(row)


@app.get("/api/debts/{debt_id:int}")
def get_debt(debt_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(Debt).where(Debt.id == debt_id, Debt.user_id == user.id))
    if not row: raise HTTPException(404, "Debt not found")
    return {**debt_record(row), "repayments": [record(x) for x in sorted(row.repayments, key=lambda x: (x.date, x.id), reverse=True)]}


@app.put("/api/debts/{debt_id:int}")
def update_debt(debt_id: int, payload: DebtCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(Debt).where(Debt.id == debt_id, Debt.user_id == user.id))
    if not row: raise HTTPException(404, "Debt not found")
    if row.repayments: raise HTTPException(409, "This record has repayments and cannot be edited safely")
    friend = owned_friend(payload.friend_id, user.id, db) if payload.friend_id else None
    name = payload.friend_name.strip() if payload.friend_name else ""
    if friend is None and name:
        friend = db.scalar(select(Friend).where(Friend.user_id == user.id, func.lower(Friend.name) == name.lower()))
        if not friend: friend = Friend(user_id=user.id, name=name); db.add(friend); db.flush()
    if not friend: raise HTTPException(422, "Choose a friend")
    row.friend_id, row.friend_name, row.direction = friend.id, friend.name, payload.direction
    row.amount, row.date, row.due_date, row.description = to_paise(payload.amount), payload.date, payload.due_date, payload.description
    db.commit(); db.refresh(row)
    return debt_record(row)


@app.delete("/api/debts/{debt_id:int}", status_code=204)
def delete_debt(debt_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(Debt).where(Debt.id == debt_id, Debt.user_id == user.id))
    if not row: raise HTTPException(404, "Debt not found")
    if row.repayments: raise HTTPException(409, "This record has repayment history and cannot be deleted")
    db.delete(row); db.commit()


@app.get("/api/debts/{debt_id}/repayments")
def list_repayments(debt_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    debt = db.scalar(select(Debt).where(Debt.id == debt_id, Debt.user_id == user.id))
    if not debt: raise HTTPException(404, "Debt not found")
    return [record(x) for x in sorted(debt.repayments, key=lambda x: (x.date, x.id), reverse=True)]


@app.post("/api/debts/{debt_id}/repayments", status_code=201)
def repay(debt_id: int, payload: RepaymentCreate, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    # SQLite ignores SELECT FOR UPDATE. A no-op UPDATE acquires its write lock
    # before reading the balance; PostgreSQL additionally locks the selected row.
    db.execute(update(Debt).where(Debt.id == debt_id, Debt.user_id == user.id).values(updated_at=Debt.updated_at))
    cents = to_paise(payload.amount)
    note = payload.notes or payload.note or ""
    if payload.request_id:
        duplicate = db.scalar(select(DebtRepayment).where(DebtRepayment.user_id == user.id, DebtRepayment.request_id == payload.request_id))
        if duplicate:
            if (duplicate.debt_id, duplicate.amount, duplicate.date, duplicate.note) != (debt_id, cents, payload.date, note):
                raise HTTPException(409, "This request_id was already used for a different repayment")
            response.status_code = 200
            return record(duplicate)
    debt = db.scalar(select(Debt).where(Debt.id == debt_id, Debt.user_id == user.id).with_for_update())
    if not debt: raise HTTPException(404, "Debt not found")
    paid, remaining, _ = debt_state(debt)
    if remaining <= 0: raise HTTPException(409, "This record is already fully settled")
    if cents > remaining: raise HTTPException(422, "Repayment exceeds the outstanding balance")
    item = DebtRepayment(debt_id=debt.id, user_id=user.id, amount=cents, date=payload.date,
                         note=note, request_id=payload.request_id)
    db.add(item)
    try: db.commit()
    except IntegrityError:
        db.rollback()
        if payload.request_id:
            duplicate = db.scalar(select(DebtRepayment).where(DebtRepayment.user_id == user.id, DebtRepayment.request_id == payload.request_id))
            if duplicate and (duplicate.debt_id, duplicate.amount, duplicate.date, duplicate.note) == (debt_id, cents, payload.date, note):
                response.status_code = 200
                return record(duplicate)
        raise HTTPException(409, "Repayment could not be recorded. Refresh and try again.")
    db.refresh(item)
    return record(item)


@app.get("/api/debts/summary")
def debt_summary(month: str | None = None, year: int | None = Query(None, ge=1900, le=2200), friend_id: int | None = None,
                 direction: str | None = Query(None, pattern="^(borrowed|lent)$"), status: str | None = None,
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    all_debts = db.scalars(select(Debt).where(Debt.user_id == user.id)).all()
    def passes(d):
        if month and d.date.strftime("%Y-%m") != month: return False
        if not month and year and d.date.year != year: return False
        if friend_id and d.friend_id != friend_id: return False
        if direction and d.direction != direction: return False
        if status and debt_state(d)[2] != status: return False
        return True
    debts = [d for d in all_debts if passes(d)]
    totals = {"borrowed": 0, "lent": 0, "repaid": 0, "received": 0, "debt": 0, "receivable": 0}
    for item in debts:
        paid, remaining, _ = debt_state(item)
        totals[item.direction] += item.amount
        totals["repaid" if item.direction == "borrowed" else "received"] += paid
        totals["debt" if item.direction == "borrowed" else "receivable"] += remaining
    today = kolkata_today()
    upcoming = [debt_record(d) for d in debts if d.due_date and d.due_date >= today and debt_state(d)[1] > 0]
    upcoming.sort(key=lambda x: x["due_date"])
    overdue = [debt_record(d) for d in debts if debt_state(d)[2] == "overdue"]
    repayments = [(rep, debt) for debt in debts for rep in debt.repayments]
    repayments.sort(key=lambda pair: (pair[0].date, pair[0].id), reverse=True)
    return {"total_borrowed": to_rupees(totals["borrowed"]), "total_lent": to_rupees(totals["lent"]),
            "outstanding_debt": to_rupees(totals["debt"]), "outstanding_receivables": to_rupees(totals["receivable"]),
            "total_repayments_made": to_rupees(totals["repaid"]), "total_repayments_received": to_rupees(totals["received"]),
            "owed_to_friends": to_rupees(totals["debt"]), "owed_by_friends": to_rupees(totals["receivable"]),
            "borrowed_vs_lent": {"borrowed": to_rupees(totals["borrowed"]), "lent": to_rupees(totals["lent"])},
            "statuses": {key: sum(debt_state(d)[2] == key for d in debts) for key in ("unpaid", "partial", "fully_paid", "overdue")},
            "recent_repayments": [record(rep, direction=debt.direction, friend_name=debt.friend.name if debt.friend else debt.friend_name, debt_id=debt.id) for rep, debt in repayments[:10]],
            "upcoming_deadlines": upcoming[:10], "overdue_items": overdue}


@app.get("/api/dashboard/summary")
def dashboard_summary(month: str = Query(default_factory=lambda: kolkata_today().strftime("%Y-%m")), user: User = Depends(current_user), db: Session = Depends(get_db)):
    try: year, month_num = map(int, month.split("-")); date(year, month_num, 1)
    except Exception: raise HTTPException(422, "Month must use YYYY-MM format")
    inc = db.scalars(select(Income).where(Income.user_id == user.id, extract("year", Income.date) == year, extract("month", Income.date) == month_num)).all()
    exp = db.scalars(select(Expense).where(Expense.user_id == user.id, extract("year", Expense.date) == year, extract("month", Expense.date) == month_num)).all()
    income = sum(x.amount for x in inc); expenses = sum(x.amount for x in exp)
    debt_rows = db.scalars(select(Debt).where(Debt.user_id == user.id, extract("year", Debt.date) == year, extract("month", Debt.date) == month_num)).all()
    repayments = db.scalars(select(DebtRepayment).where(DebtRepayment.user_id == user.id, extract("year", DebtRepayment.date) == year, extract("month", DebtRepayment.date) == month_num)).all()
    debt_by_id = {d.id: d for d in db.scalars(select(Debt).where(Debt.user_id == user.id)).all()}
    borrowed_cash = sum(d.amount for d in debt_rows if d.direction == "borrowed")
    lent_cash = sum(d.amount for d in debt_rows if d.direction == "lent")
    repayment_out = sum(r.amount for r in repayments if debt_by_id.get(r.debt_id) and debt_by_id[r.debt_id].direction == "borrowed")
    repayment_in = sum(r.amount for r in repayments if debt_by_id.get(r.debt_id) and debt_by_id[r.debt_id].direction == "lent")
    debt_cash_flow = borrowed_cash - lent_cash - repayment_out + repayment_in
    goals = db.scalars(select(SavingsGoal).where(SavingsGoal.user_id == user.id)).all()
    savings_rows = db.scalars(select(SavingsTransaction).where(SavingsTransaction.user_id == user.id, extract("year", SavingsTransaction.date) == year, extract("month", SavingsTransaction.date) == month_num)).all()
    savings_cash_flow = sum(x.amount if x.transaction_type == "withdrawal" else -x.amount for x in savings_rows)
    savings_balance_total = sum(savings_balance(g.id, user.id, db) or 0 for g in goals)
    ensure_reminder_occurrences(user.id, db)
    reminders = db.scalars(select(Reminder).where(Reminder.user_id == user.id, Reminder.paid == False, Reminder.status != "cancelled")).all()
    dsum = debt_summary(month=None, year=None, friend_id=None, direction=None, status=None, user=user, db=db)
    cats = {}
    for x in exp: cats[x.category] = cats.get(x.category, 0) + x.amount
    budgets = db.scalars(select(Budget).where(Budget.user_id == user.id, Budget.month == month)).all()
    recent = [record(item, type="income", category=item.source) for item in inc]
    recent.extend(record(item, type="expense") for item in exp)
    recent.extend({**savings_transaction_record(item), "type": "savings_" + item.transaction_type, "category": "Savings"} for item in savings_rows)
    recent.sort(key=lambda item: (str(item["date"]), item["id"]), reverse=True)
    return {"month": month, "income": to_rupees(income), "expenses": to_rupees(expenses), "net": to_rupees(income-expenses),
        "debt_cash_flow": to_rupees(debt_cash_flow), "savings_cash_flow": to_rupees(savings_cash_flow), "available_cash_change": to_rupees(income-expenses+debt_cash_flow+savings_cash_flow),
        "borrowed_funds": to_rupees(borrowed_cash), "lent_funds": to_rupees(lent_cash),
        "repayments_made": to_rupees(repayment_out), "repayments_received": to_rupees(repayment_in),
        "reserved_savings": to_rupees(savings_balance_total), "actual_savings": to_rupees(max(0, income-expenses)),
        "pending_bills": to_rupees(sum(x.amount for x in reminders)), "owed_to_friends": dsum["owed_to_friends"], "owed_by_friends": dsum["owed_by_friends"],
        "categories": {k: to_rupees(v) for k,v in cats.items()}, "recent_transactions": recent[:6],
        "budgets": [{"category": b.category, "amount": to_rupees(b.amount), "spent": to_rupees(cats.get(b.category,0))} for b in budgets]}


@app.get("/api/dashboard/analytics")
def dashboard_analytics(year: int = Query(default_factory=lambda: kolkata_today().year), user: User = Depends(current_user), db: Session = Depends(get_db)):
    expenses = db.scalars(select(Expense).where(Expense.user_id == user.id, extract("year", Expense.date) == year)).all()
    income = db.scalars(select(Income).where(Income.user_id == user.id, extract("year", Income.date) == year)).all()
    monthly = [{"month": f"{year}-{m:02}", "expenses": to_rupees(sum(x.amount for x in expenses if x.date.month == m)), "income": to_rupees(sum(x.amount for x in income if x.date.month == m))} for m in range(1,13)]
    return {"year": year, "monthly": monthly}


def report_range(period: str = "this_month", start_date: date | None = None, end_date: date | None = None):
    today = kolkata_today()
    if period == "custom":
        if not start_date or not end_date or start_date > end_date:
            raise HTTPException(422, "Custom reports need a valid start_date and end_date")
        return start_date, end_date
    if start_date or end_date:
        if not start_date or not end_date or start_date > end_date:
            raise HTTPException(422, "Provide a valid start_date and end_date")
        return start_date, end_date
    if period == "this_week":
        start = today - timedelta(days=today.weekday())
        return start, today
    if period == "this_month":
        return today.replace(day=1), today
    if period == "previous_month":
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end
    if period in ("last_3_months", "last_6_months"):
        months = 3 if period == "last_3_months" else 6
        start_month = today.month - months + 1
        year = today.year + (start_month - 1) // 12
        month = (start_month - 1) % 12 + 1
        return date(year, month, 1), today
    if period == "this_year": return date(today.year, 1, 1), today
    if period == "previous_year": return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
    raise HTTPException(422, "Unsupported reporting period")


def report_data(user, db, period="this_month", start_date=None, end_date=None, transaction_type=None,
                category=None, payment_method=None):
    start, end = report_range(period, start_date, end_date)
    incomes = db.scalars(select(Income).where(Income.user_id == user.id, Income.date >= start, Income.date <= end)).all()
    expenses = db.scalars(select(Expense).where(Expense.user_id == user.id, Expense.date >= start, Expense.date <= end)).all()
    if transaction_type == "income": expenses = []
    elif transaction_type == "expense": incomes = []
    if category:
        incomes = [x for x in incomes if x.source.casefold() == category.casefold()]
        expenses = [x for x in expenses if x.category.casefold() == category.casefold()]
    if payment_method: expenses = [x for x in expenses if x.payment_method.casefold() == payment_method.casefold()]
    savings = db.scalars(select(SavingsTransaction).where(SavingsTransaction.user_id == user.id, SavingsTransaction.date >= start, SavingsTransaction.date <= end)).all()
    goals = db.scalars(select(SavingsGoal).where(SavingsGoal.user_id == user.id)).all()
    debts = db.scalars(select(Debt).where(Debt.user_id == user.id)).all()
    repayments = db.scalars(select(DebtRepayment).where(DebtRepayment.user_id == user.id, DebtRepayment.date >= start, DebtRepayment.date <= end)).all()
    ensure_reminder_occurrences(user.id, db)
    reminders = db.scalars(select(Reminder).where(Reminder.user_id == user.id)).all()
    payments = db.scalars(select(ReminderPayment).where(ReminderPayment.user_id == user.id, ReminderPayment.paid_date >= start, ReminderPayment.paid_date <= end)).all()
    all_payments = db.scalars(select(ReminderPayment).where(ReminderPayment.user_id == user.id)).all()
    today = kolkata_today()
    active_reminders = [r for r in reminders if r.status != "cancelled"]
    overdue = [r for r in active_reminders if not r.paid and start <= r.due_date < today]
    upcoming = [r for r in active_reminders if not r.paid and max(start, today) <= r.due_date <= end]
    payment_reminder_ids = {p.reminder_id for p in all_payments}
    legacy_paid = [r for r in active_reminders if r.paid and r.id not in payment_reminder_ids and start <= (r.paid_at or r.due_date) <= end]
    paid_bill_total = sum(x.actual_amount for x in payments) + sum(x.actual_paid_amount or x.amount for x in legacy_paid)
    expenses_total = sum(x.amount for x in expenses); income_total = sum(x.amount for x in incomes)
    savings_in = sum(x.amount for x in savings if x.transaction_type == "contribution")
    savings_out = sum(x.amount for x in savings if x.transaction_type == "withdrawal")
    cat_exp, cat_income, methods = {}, {}, {}
    for row in expenses:
        cat_exp[row.category] = cat_exp.get(row.category, 0) + row.amount
        methods[row.payment_method] = methods.get(row.payment_method, 0) + row.amount
    for row in incomes: cat_income[row.source] = cat_income.get(row.source, 0) + row.amount
    debt_totals = {"borrowed": 0, "lent": 0, "repaid": 0, "received": 0, "owed_to_friends": 0, "owed_by_friends": 0}
    for debt in debts:
        paid, remaining, _ = debt_state(debt)
        debt_totals["borrowed" if debt.direction == "borrowed" else "lent"] += debt.amount
        debt_totals["repaid" if debt.direction == "borrowed" else "received"] += paid
        debt_totals["owed_to_friends" if debt.direction == "borrowed" else "owed_by_friends"] += remaining
    relevant_debt_ids = {x.id: x.direction for x in debts}
    repayment_out = sum(x.amount for x in repayments if relevant_debt_ids.get(x.debt_id) == "borrowed")
    repayment_in = sum(x.amount for x in repayments if relevant_debt_ids.get(x.debt_id) == "lent")
    savings_balances = [savings_balance(g.id, user.id, db) or 0 for g in goals]
    return {"start_date": start.isoformat(), "end_date": end.isoformat(), "period": period,
        "income": income_total, "expenses": expenses_total, "net_cash_flow": income_total-expenses_total,
        "savings_contributions": savings_in, "savings_withdrawals": savings_out,
        "savings_balance": sum(savings_balances), "active_goals": sum(g.status == "active" for g in goals),
        "completed_goals": sum(g.status == "completed" for g in goals),
        "debts": debt_totals, "repayments_made": repayment_out, "repayments_received": repayment_in,
        "upcoming_obligations": sum(x.amount for x in upcoming), "upcoming_count": len(upcoming),
        "overdue_bills": sum(x.amount for x in overdue), "overdue_count": len(overdue),
        "paid_bills": paid_bill_total, "legacy_paid_reminders": legacy_paid, "expense_categories": cat_exp,
        "income_categories": cat_income, "payment_methods": methods,
        "incomes": incomes, "expense_rows": expenses, "savings_rows": savings, "goals": goals,
        "debts_rows": debts, "reminder_rows": reminders, "payment_rows": payments,
        "debt_repayments": repayments}


def report_month_buckets(data, start, end):
    months = []
    cursor = date(start.year, start.month, 1)
    last = date(end.year, end.month, 1)
    while cursor <= last:
        next_month = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
        lo, hi = max(cursor, start), min(next_month - timedelta(days=1), end)
        inc = sum(x.amount for x in data["incomes"] if lo <= x.date <= hi)
        exp = sum(x.amount for x in data["expense_rows"] if lo <= x.date <= hi)
        contrib = sum(x.amount for x in data["savings_rows"] if x.transaction_type == "contribution" and lo <= x.date <= hi)
        withdrawal = sum(x.amount for x in data["savings_rows"] if x.transaction_type == "withdrawal" and lo <= x.date <= hi)
        months.append({"month": cursor.strftime("%Y-%m"), "income": to_rupees(inc), "expenses": to_rupees(exp),
                       "net": to_rupees(inc-exp), "contributions": to_rupees(contrib), "withdrawals": to_rupees(withdrawal)})
        cursor = next_month
    return months


def report_budget_data(user_id, db, start, end):
    budgets = db.scalars(select(Budget).where(Budget.user_id == user_id, Budget.month >= start.strftime("%Y-%m"), Budget.month <= end.strftime("%Y-%m"))).all()
    expenses = db.scalars(select(Expense).where(Expense.user_id == user_id, Expense.date >= start, Expense.date <= end)).all()
    results = []
    for month in sorted({b.month for b in budgets} | {x.date.strftime("%Y-%m") for x in expenses}):
        month_budgets = [b for b in budgets if b.month == month]
        month_expenses = [x for x in expenses if x.date.strftime("%Y-%m") == month]
        used = {x.category: 0 for x in month_expenses}
        for x in month_expenses: used[x.category] += x.amount
        limits = {b.category: 0 for b in month_budgets}
        for b in month_budgets: limits[b.category] += b.amount
        details = []
        for cat in sorted(set(used) | set(limits)):
            limit, spent = limits.get(cat), used.get(cat, 0)
            details.append({"month": month, "category": cat, "budgeted": limit is not None,
                "planned": to_rupees(limit) if limit is not None else None, "actual": to_rupees(spent),
                "remaining": to_rupees(limit-spent) if limit is not None else None,
                "utilization": round(spent*100/limit, 1) if limit else None,
                "status": "unbudgeted" if limit is None else budget_status_code(spent, limit)})
        results.extend(details)
    return results


@app.get("/api/reports/summary")
def reports_summary(period: str = "this_month", start_date: date | None = None, end_date: date | None = None,
                    transaction_type: str | None = Query(None, pattern="^(income|expense)$"), category: str | None = None,
                    payment_method: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = report_data(user, db, period, start_date, end_date, transaction_type, category, payment_method)
    budget_rows = report_budget_data(user.id, db, date.fromisoformat(d["start_date"]), date.fromisoformat(d["end_date"]))
    planned = sum(to_paise(x["planned"]) for x in budget_rows if x["planned"] is not None)
    budgeted_spend = sum(to_paise(x["actual"]) for x in budget_rows if x["budgeted"])
    return {"start_date": d["start_date"], "end_date": d["end_date"], "income": to_rupees(d["income"]),
        "expenses": to_rupees(d["expenses"]), "net_cash_flow": to_rupees(d["net_cash_flow"]),
        "savings_contributions": to_rupees(d["savings_contributions"]), "savings_withdrawals": to_rupees(d["savings_withdrawals"]),
        "savings_balance": to_rupees(d["savings_balance"]), "active_goals": d["active_goals"], "completed_goals": d["completed_goals"],
        "budget_planned": to_rupees(planned), "budgeted_spend": to_rupees(budgeted_spend),
        "budget_utilization": round(budgeted_spend*100/planned, 1) if planned else None,
        "owed_to_friends": to_rupees(d["debts"]["owed_to_friends"]), "owed_by_friends": to_rupees(d["debts"]["owed_by_friends"]),
        "savings": {"contributions": to_rupees(d["savings_contributions"]), "withdrawals": to_rupees(d["savings_withdrawals"])},
        "debts": {k: to_rupees(v) for k,v in d["debts"].items()},
        "upcoming_obligations": to_rupees(d["upcoming_obligations"]), "upcoming_count": d["upcoming_count"],
        "overdue_bills": to_rupees(d["overdue_bills"]), "overdue_count": d["overdue_count"], "paid_bills": to_rupees(d["paid_bills"])}


def report_filters(period, start_date, end_date, transaction_type, category, payment_method, user, db):
    return report_data(user, db, period, start_date, end_date, transaction_type, category, payment_method)


@app.get("/api/reports/cash-flow")
def reports_cash_flow(period: str = "last_6_months", start_date: date | None = None, end_date: date | None = None,
                      transaction_type: str | None = Query(None, pattern="^(income|expense)$"), category: str | None = None,
                      payment_method: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = report_filters(period,start_date,end_date,transaction_type,category,payment_method,user,db)
    return {"monthly": report_month_buckets(d,date.fromisoformat(d["start_date"]),date.fromisoformat(d["end_date"]))}


@app.get("/api/reports/categories")
def reports_categories(period: str = "this_month", start_date: date | None = None, end_date: date | None = None,
                       transaction_type: str | None = Query(None, pattern="^(income|expense)$"), category: str | None = None,
                       payment_method: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d=report_filters(period,start_date,end_date,transaction_type,category,payment_method,user,db)
    return {"expenses": {k:to_rupees(v) for k,v in sorted(d["expense_categories"].items(),key=lambda x:-x[1])},
            "income": {k:to_rupees(v) for k,v in sorted(d["income_categories"].items(),key=lambda x:-x[1])},
            "payment_methods": {k:to_rupees(v) for k,v in sorted(d["payment_methods"].items(),key=lambda x:-x[1])},
            "average_monthly_expenses": to_rupees(round(d["expenses"] / max(1,len(report_month_buckets(d,date.fromisoformat(d["start_date"]),date.fromisoformat(d["end_date"]))))) )}


@app.get("/api/reports/budgets")
def reports_budgets(period: str = "this_month", start_date: date | None = None, end_date: date | None = None,
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
    start,end=report_range(period,start_date,end_date); rows=report_budget_data(user.id,db,start,end)
    return {"categories":rows,"monthly":[{"month":m,"planned":sum((r["planned"] or 0) for r in rows if r["month"]==m),"actual":sum(r["actual"] for r in rows if r["month"]==m)} for m in sorted({r["month"] for r in rows})],
            "exceeded":[x for x in rows if x["status"]=="exceeded"],"approaching":[x for x in rows if x["status"] in ("warning","critical")],"unbudgeted":[x for x in rows if x["status"]=="unbudgeted"]}


@app.get("/api/reports/savings")
def reports_savings(period: str = "this_month", start_date: date | None = None, end_date: date | None = None,
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
    d=report_data(user,db,period,start_date,end_date); tx=d["savings_rows"]
    goals=[]
    for g in d["goals"]:
        balance=savings_balance(g.id,user.id,db) or 0
        goals.append({"name":g.name,"category":g.category,"status":g.status,"balance":to_rupees(balance),"target":to_rupees(g.target_amount),"progress":round(balance*100/g.target_amount,1) if g.target_amount else 0})
    return {"balance":to_rupees(d["savings_balance"]),"contributions":to_rupees(d["savings_contributions"]),"withdrawals":to_rupees(d["savings_withdrawals"]),"goals":goals,
            "monthly":report_month_buckets(d,date.fromisoformat(d["start_date"]),date.fromisoformat(d["end_date"])),
            "activity":[{"date":x.date.isoformat(),"goal":next((g.name for g in d["goals"] if g.id==x.goal_id),"Savings"),"type":x.transaction_type,"amount":to_rupees(x.amount),"notes":x.notes} for x in tx]}


@app.get("/api/reports/debts")
def reports_debts(period: str = "this_month", start_date: date | None = None, end_date: date | None = None,
                  user: User = Depends(current_user), db: Session = Depends(get_db)):
    d=report_data(user,db,period,start_date,end_date); items=[]
    for x in d["debts_rows"]:
        paid,remaining,status=debt_state(x)
        if remaining: items.append({"friend":x.friend.name if x.friend else x.friend_name,"direction":x.direction,"principal":to_rupees(x.amount),"paid":to_rupees(paid),"outstanding":to_rupees(remaining),"due_date":x.due_date.isoformat() if x.due_date else None,"status":status})
    return {"summary":{k:to_rupees(v) for k,v in d["debts"].items()},"repayments_made":to_rupees(d["repayments_made"]),"repayments_received":to_rupees(d["repayments_received"]),"overdue":[x for x in items if x["status"]=="overdue"],"outstanding":items}


@app.get("/api/reports/reminders")
def reports_reminders(period: str = "this_month", start_date: date | None = None, end_date: date | None = None,
                      user: User = Depends(current_user), db: Session = Depends(get_db)):
    d=report_data(user,db,period,start_date,end_date); today=kolkata_today()
    rows=[x for x in d["reminder_rows"] if x.status!="cancelled" and date.fromisoformat(d["start_date"])<=x.due_date<=date.fromisoformat(d["end_date"])]
    return {"paid":to_rupees(d["paid_bills"]),"unpaid":to_rupees(sum(x.amount for x in rows if not x.paid)),
        "upcoming":[{"title":x.title,"category":x.category,"due_date":x.due_date.isoformat(),"amount":to_rupees(x.amount),"status":"upcoming"} for x in rows if not x.paid and x.due_date>=today],
        "overdue":[{"title":x.title,"category":x.category,"due_date":x.due_date.isoformat(),"amount":to_rupees(x.amount),"status":"overdue"} for x in rows if not x.paid and x.due_date<today],
        "categories":{k:to_rupees(v) for k,v in _sum_by(rows,lambda x:x.category,lambda x:x.amount).items()},
        "monthly_paid":_reminder_monthly(d["payment_rows"], d["legacy_paid_reminders"])}


def _sum_by(rows,key,value):
    result={}
    for row in rows: result[key(row)]=result.get(key(row),0)+value(row)
    return result


def _reminder_monthly(rows, legacy=()):
    totals=_sum_by(rows,lambda x:x.paid_date.strftime("%Y-%m"),lambda x:x.actual_amount)
    for item in legacy:
        key=(item.paid_at or item.due_date).strftime("%Y-%m")
        totals[key]=totals.get(key,0)+(item.actual_paid_amount or item.amount)
    return [{"month":k,"paid":to_rupees(v)} for k,v in sorted(totals.items())]


@app.get("/api/reports/export")
def reports_export(section: str = "transactions", period: str = "this_month", start_date: date | None = None, end_date: date | None = None,
                   transaction_type: str | None = Query(None, pattern="^(income|expense)$"), category: str | None = None,
                   payment_method: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    valid={"summary","transactions","budgets","savings","debts","reminders"}
    if section not in valid: raise HTTPException(422,"Unsupported export section")
    d=report_filters(period,start_date,end_date,transaction_type,category,payment_method,user,db)
    out=StringIO(); w=SafeCSVWriter(out)
    if section=="transactions":
        w.writerow(["Date","Type","Category or source","Description","Amount (INR)","Payment method"])
        for x in sorted([(x,"income") for x in d["incomes"]]+[(x,"expense") for x in d["expense_rows"]],key=lambda a:a[0].date):
            row,kind=x; w.writerow([row.date.isoformat(),kind,row.source if kind=="income" else row.category,row.description,f"₹{to_rupees(row.amount):.2f}",getattr(row,"payment_method","")])
    elif section=="summary":
        start,end=date.fromisoformat(d["start_date"]),date.fromisoformat(d["end_date"])
        budget_rows=report_budget_data(user.id,db,start,end)
        planned=sum(to_paise(x["planned"]) for x in budget_rows if x["planned"] is not None)
        budgeted=sum(to_paise(x["actual"]) for x in budget_rows if x["budgeted"])
        w.writerow(["Metric","Value"]); w.writerows([[k,f"₹{to_rupees(v):.2f}"] for k,v in (("Income",d["income"]),("Expenses",d["expenses"]),("Net cash flow",d["net_cash_flow"]),("Savings balance",d["savings_balance"]),("Savings contributions",d["savings_contributions"]),("Savings withdrawals",d["savings_withdrawals"]),("Budget planned",planned),("Budgeted expenses",budgeted),("Outstanding owed to friends",d["debts"]["owed_to_friends"]),("Outstanding owed by friends",d["debts"]["owed_by_friends"]),("Bills paid",d["paid_bills"]),("Upcoming obligations",d["upcoming_obligations"]),("Overdue bills",d["overdue_bills"]))])
    elif section=="budgets":
        w.writerow(["Month","Category","Planned (INR)","Actual (INR)","Remaining (INR)","Utilization (%)","Status"])
        for x in report_budget_data(user.id,db,date.fromisoformat(d["start_date"]),date.fromisoformat(d["end_date"])): w.writerow([x["month"],x["category"],f"₹{x['planned']:.2f}" if x["planned"] is not None else "",f"₹{x['actual']:.2f}",f"₹{x['remaining']:.2f}" if x["remaining"] is not None else "",x["utilization"] if x["utilization"] is not None else "",x["status"]])
    elif section=="savings":
        w.writerow(["Date","Goal","Activity","Amount (INR)","Notes"])
        for x in sorted(d["savings_rows"],key=lambda z:z.date): w.writerow([x.date.isoformat(),next((g.name for g in d["goals"] if g.id==x.goal_id),"Savings"),x.transaction_type,f"₹{to_rupees(x.amount):.2f}",x.notes])
    elif section=="debts":
        w.writerow(["Friend","Direction","Principal (INR)","Paid or received (INR)","Outstanding (INR)","Due date","Status"])
        for x in d["debts_rows"]:
            if not (date.fromisoformat(d["start_date"])<=x.date<=date.fromisoformat(d["end_date"])) and not any(r.debt_id==x.id for r in d["debt_repayments"]): continue
            paid,left,status=debt_state(x); w.writerow([x.friend.name if x.friend else x.friend_name,x.direction,f"₹{to_rupees(x.amount):.2f}",f"₹{to_rupees(paid):.2f}",f"₹{to_rupees(left):.2f}",x.due_date.isoformat() if x.due_date else "",status])
    else:
        w.writerow(["Due date","Bill","Category","Expected (INR)","Status","Paid date","Actual paid (INR)"])
        start,end=date.fromisoformat(d["start_date"]),date.fromisoformat(d["end_date"])
        for x in sorted(d["reminder_rows"],key=lambda z:z.due_date):
            if x.status=="cancelled": continue
            payment=next((p for p in d["payment_rows"] if p.reminder_id==x.id),None)
            legacy_paid=next((r for r in d["legacy_paid_reminders"] if r.id==x.id),None)
            if not (start<=x.due_date<=end or payment or legacy_paid): continue
            status="paid" if x.paid else "overdue" if x.due_date<kolkata_today() else "upcoming"
            paid_date=payment.paid_date if payment else (legacy_paid.paid_at or legacy_paid.due_date) if legacy_paid else None
            paid_amount=payment.actual_amount if payment else (legacy_paid.actual_paid_amount or legacy_paid.amount) if legacy_paid else None
            w.writerow([x.due_date.isoformat(),x.title,x.category,f"₹{to_rupees(x.amount):.2f}",status,paid_date.isoformat() if paid_date else "",f"₹{to_rupees(paid_amount):.2f}" if paid_amount is not None else ""])
    return StreamingResponse(iter([out.getvalue()]),media_type="text/csv; charset=utf-8",headers={"Content-Disposition":f"attachment; filename=pocketwise-{section}.csv"})


@app.get("/api/reports/monthly")
def monthly_report(year: int = Query(default_factory=lambda: kolkata_today().year), user: User = Depends(current_user), db: Session = Depends(get_db)):
    return dashboard_analytics(year, user, db)


@app.get("/api/reports/category")
def category_report(month: str = Query(default_factory=lambda: kolkata_today().strftime("%Y-%m")), user: User = Depends(current_user), db: Session = Depends(get_db)):
    summary = dashboard_summary(month, user, db)
    return [{"category": k, "amount": v} for k,v in summary["categories"].items()]


@app.get("/api/reports/export")
def export_transactions(month: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    incomes = db.scalars(select(Income).where(Income.user_id == user.id)).all()
    expenses = db.scalars(select(Expense).where(Expense.user_id == user.id)).all()
    output = StringIO()
    writer = SafeCSVWriter(output)
    writer.writerow(["date", "type", "category_or_source", "description", "amount_inr", "payment_method"])
    for item in incomes:
        if not month or item.date.strftime("%Y-%m") == month:
            writer.writerow([item.date.isoformat(), "income", item.source, item.description, f"{to_rupees(item.amount):.2f}", ""])
    for item in expenses:
        if not month or item.date.strftime("%Y-%m") == month:
            writer.writerow([item.date.isoformat(), "expense", item.category, item.description, f"{to_rupees(item.amount):.2f}", item.payment_method])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=pocketwise-transactions.csv"})


def assistant_financial_context(user, db, question):
    today=kolkata_today()
    start,end,label=assistant_question_range(question,today)
    incomes=db.scalars(select(Income).where(Income.user_id==user.id,Income.date>=start,Income.date<=end)).all()
    expenses=db.scalars(select(Expense).where(Expense.user_id==user.id,Expense.date>=start,Expense.date<=end)).all()
    savings_rows=db.scalars(select(SavingsTransaction).where(SavingsTransaction.user_id==user.id,SavingsTransaction.date>=start,SavingsTransaction.date<=end)).all()
    goals=db.scalars(select(SavingsGoal).where(SavingsGoal.user_id==user.id)).all()
    debts=db.scalars(select(Debt).where(Debt.user_id==user.id)).all()
    owed_to=owed_by=payable_count=receivable_count=0
    for debt in debts:
        _,remaining,_=debt_state(debt)
        if debt.direction=="borrowed": owed_to+=remaining; payable_count+=remaining>0
        else: owed_by+=remaining; receivable_count+=remaining>0
    cat_totals={}
    for row in expenses: cat_totals[row.category]=cat_totals.get(row.category,0)+row.amount
    income_sources={}
    for row in incomes: income_sources[row.source]=income_sources.get(row.source,0)+row.amount
    top=max(cat_totals.items(),key=lambda x:x[1],default=None)
    budget_rows=report_budget_data(user.id,db,start,end)
    budget_categories=[{"category":x["category"],"budgeted":x["budgeted"],"planned":to_paise(x["planned"]) if x["planned"] is not None else 0,
        "actual":to_paise(x["actual"]),"utilization":x["utilization"] or 0} for x in budget_rows]
    alerts=[{"category":x["category"],"status":x["status"],"utilization":x["utilization"],"spent":to_paise(x["actual"]),"limit":to_paise(x["planned"])} for x in budget_rows if x["budgeted"] and x["status"] in ("warning","critical","exceeded")]
    ensure_reminder_occurrences(user.id,db)
    reminders=db.scalars(select(Reminder).where(Reminder.user_id==user.id,Reminder.paid.is_(False),Reminder.status!="cancelled")).all()
    due=[{"title":x.title,"due_date":x.due_date.isoformat(),"amount":x.amount} for x in reminders if today<=x.due_date<=today+timedelta(days=6)]
    overdue=[x for x in reminders if x.due_date<today]
    recurring=db.scalars(select(RecurringSchedule).where(RecurringSchedule.user_id==user.id,RecurringSchedule.active.is_(True))).all()
    balances=[savings_balance(g.id,user.id,db) or 0 for g in goals]
    ctx={"start":start,"end":end,"period_label":label,"income":sum(x.amount for x in incomes),"expenses":sum(x.amount for x in expenses),
        "has_activity":bool(incomes or expenses),"categories":cat_totals,"income_sources":income_sources,"top_category":{"category":top[0],"amount":top[1]} if top else None,
        "budget_categories":budget_categories,"budget_alerts":alerts,"savings_balance":sum(balances),"contributions":sum(x.amount for x in savings_rows if x.transaction_type=="contribution"),
        "withdrawals":sum(x.amount for x in savings_rows if x.transaction_type=="withdrawal"),"goal_count":len(goals),
        "owed_to_friends":owed_to,"owed_by_friends":owed_by,"payable_count":payable_count,"receivable_count":receivable_count,
        "due_next_week":due,"overdue_bills":sum(x.amount for x in overdue),
        "overdue_items":[{"title":x.title,"due_date":x.due_date.isoformat(),"amount":x.amount} for x in overdue],
        "recurring":[{"title":x.title,"amount":x.amount,"frequency":x.frequency,"category":x.category} for x in recurring]}
    # Compare the current month with the same elapsed dates in the prior month.
    current_start=today.replace(day=1); previous_end=current_start-timedelta(days=1)
    previous_start=previous_end.replace(day=1); comparable_end=min(previous_end,previous_start.replace(day=min(today.day,calendar.monthrange(previous_end.year,previous_end.month)[1])))
    current_month_expenses=db.scalars(select(Expense).where(Expense.user_id==user.id,Expense.date>=current_start,Expense.date<=today)).all()
    prior_expenses=db.scalars(select(Expense).where(Expense.user_id==user.id,Expense.date>=previous_start,Expense.date<=comparable_end)).all()
    cur_cat=_sum_by(current_month_expenses,lambda x:x.category,lambda x:x.amount)
    prev_cat=_sum_by(prior_expenses,lambda x:x.category,lambda x:x.amount)
    ctx["month_to_date_expenses"]=sum(x.amount for x in current_month_expenses)
    ctx["previous_month_expenses"]=sum(x.amount for x in prior_expenses)
    ctx["top_category_change"]=(cur_cat.get(top[0],0)-prev_cat.get(top[0],0)) if top else None
    ctx["category_changes"]={category:cur_cat.get(category,0)-prev_cat.get(category,0) for category in set(cur_cat)|set(prev_cat)}
    current_month=datetime(today.year,today.month,1).strftime("%Y-%m")
    current_budget=budget_summary_data(user.id,db,month=current_month)
    ctx["current_budget_alerts"]=[{"category":x["category"],"status":x["status"],"utilization":x["utilization"],"spent":to_paise(x["spent"]),"limit":to_paise(x["amount"])} for x in current_budget["categories"] if x["budgeted"] and x["status"] in ("warning","critical","exceeded")]
    current_savings_summary=savings_summary(month=current_month,year=None,user=user,db=db)
    dashboard=dashboard_summary(current_month,user,db)
    today_plus= today+timedelta(days=30)
    next_bills=[x.amount for x in reminders if today<=x.due_date<=today_plus]
    planned_remaining=0
    month_budget_rows=report_budget_data(user.id,db,current_start,date(today.year,today.month,calendar.monthrange(today.year,today.month)[1]))
    for x in month_budget_rows:
        if x["planned"] is not None: planned_remaining+=max(0,to_paise(x["planned"])-to_paise(x["actual"]))
    goal_pace=0
    for goal in goals:
        if goal.target_date and goal.target_date>today:
            goal_pace+=to_paise(savings_goal_record(goal,db).get("monthly_target") or 0)
    ctx["affordability"]={"available_cash":to_paise(dashboard["available_cash_change"]),"upcoming_bills":sum(next_bills),
        "budget_reserve":planned_remaining,"goal_reserve":goal_pace,"savings_balance":sum(balances),"has_activity":bool(dashboard["income"] or dashboard["expenses"])}
    ctx["affordability_answer"]=lambda amount: _affordability_text(amount,ctx["affordability"])
    ctx["current_savings_summary"]=current_savings_summary
    return ctx


def _affordability_text(amount, context):
    result=affordability_result(amount,context)
    return result["message"]+f" Estimated classification: {result['classification'].replace('_',' ')}."


def _assistant_public_context(ctx):
    return {"period":ctx["period_label"],"income_inr":to_rupees(ctx["income"]),"expenses_inr":to_rupees(ctx["expenses"]),
        "category_totals_inr":{k:to_rupees(v) for k,v in ctx["categories"].items()},
        "budgets":[{"category":x["category"],"status":x["status"],"utilization_percent":x["utilization"],"spent_inr":to_rupees(x["spent"]),"limit_inr":to_rupees(x["limit"])} for x in ctx["budget_alerts"]],
        "savings_balance_inr":to_rupees(ctx["savings_balance"]),
        "owed_to_friends_inr":to_rupees(ctx["owed_to_friends"]),"owed_by_friends_inr":to_rupees(ctx["owed_by_friends"]),
        "unpaid_bills_due_next_week":[{"title":x["title"],"date":x["due_date"],"amount_inr":to_rupees(x["amount"])} for x in ctx["due_next_week"]]}


ASSISTANT_SUGGESTIONS=["How much did I spend this month?","What is my highest spending category?","Am I exceeding any budget?",
    "How much do my friends owe me?","How much do I owe friends?","What bills are due next week?",
    "How much have I saved?","Which recurring bills should I review?","Can I afford a purchase of ₹1,500?","How can I reduce my monthly expenses?"]


@app.post("/api/assistant/chat")
def assistant_chat(payload: AssistantChat, user: User = Depends(current_user), db: Session = Depends(get_db)):
    context=assistant_financial_context(user,db,payload.message)
    answer=assistant_rule_answer(payload.message,context)
    provider="rules"
    local_ai_relevant=any(term in payload.message.casefold() for term in ("money","spend","expense","income","budget","sav","bill","debt","borrow","lent","transaction","financial","category","purchase","afford"))
    if settings.assistant_provider.casefold()=="ollama" and answer.startswith("I can help with") and local_ai_relevant:
        model_answer=OllamaProvider(settings.ollama_base_url,settings.ollama_model).answer(payload.message,_assistant_public_context(context))
        if model_answer: answer=model_answer; provider="ollama_local"
    return {"answer":answer,"period":context["period_label"],"provider":provider,"disclaimer":ASSISTANT_DISCLAIMER}


@app.get("/api/assistant/suggestions")
def assistant_suggestions(user: User = Depends(current_user)):
    return {"suggestions":ASSISTANT_SUGGESTIONS}


@app.post("/api/assistant/affordability")
def assistant_affordability(payload: AffordabilityCheck, user: User = Depends(current_user), db: Session = Depends(get_db)):
    context=assistant_financial_context(user,db,"this month")
    result=affordability_result(to_paise(payload.amount),context["affordability"])
    return {**result,"amount":float(payload.amount),"remaining":to_rupees(result.get("remaining",0)),"disclaimer":ASSISTANT_DISCLAIMER}


@app.get("/api/assistant/insights")
def assistant_insights(user: User = Depends(current_user), db: Session = Depends(get_db)):
    today=kolkata_today(); current_month=today.strftime("%Y-%m")
    context=assistant_financial_context(user,db,"this month")
    insights=[]
    def add(key,title,detail,kind="info"):
        if key not in {item["id"] for item in insights}: insights.append({"id":key,"title":title,"detail":detail,"type":kind})
    if context["month_to_date_expenses"]>context["previous_month_expenses"]:
        delta=context["month_to_date_expenses"]-context["previous_month_expenses"]
        add("spend_up","Spending is higher",f"This month to date is {assistant_rupees(delta)} above the same elapsed dates last month.","warning")
    elif context["previous_month_expenses"]>context["month_to_date_expenses"]:
        delta=context["previous_month_expenses"]-context["month_to_date_expenses"]
        add("spend_down","Spending is lower",f"This month to date is {assistant_rupees(delta)} below the same elapsed dates last month.","positive")
    for row in context["current_budget_alerts"]:
        add(f"budget:{row['category']}",f"{row['category']} budget {row['status']}",f"{row['utilization']:.0f}% used ({assistant_rupees(row['spent'])} of {assistant_rupees(row['limit'])}).","warning")
    if context["due_next_week"]:
        total=sum(x["amount"] for x in context["due_next_week"])
        add("bills_soon","Bills due soon",f"{len(context['due_next_week'])} unpaid reminder(s) totaling {assistant_rupees(total)} are due within 7 days.","warning")
    if context["affordability"]["upcoming_bills"]>context["affordability"]["available_cash"]:
        add("bill_pressure","Upcoming bills may put pressure on cash flow",f"Saved reminders due in 30 days total {assistant_rupees(context['affordability']['upcoming_bills'])}, above this month's recorded cash-flow estimate of {assistant_rupees(context['affordability']['available_cash'])}.","warning")
    if context["overdue_bills"]:
        add("bills_overdue","Overdue bills","Your saved unpaid bill reminders include an overdue balance of "+assistant_rupees(context["overdue_bills"])+".","warning")
    for goal in context["current_savings_summary"]["goals"]:
        if goal.get("overdue"):
            add(f"goal_overdue:{goal['id']}",f"Savings goal target date passed: {goal['name']}",f"The target date {goal.get('target_date')} has passed with {assistant_rupees(to_paise(goal.get('remaining') or 0))} remaining.","warning")
        if goal.get("monthly_target") and goal.get("target_date"):
            tx=db.scalars(select(SavingsTransaction).where(SavingsTransaction.user_id==user.id,SavingsTransaction.goal_id==goal["id"],SavingsTransaction.date>=today.replace(day=1),SavingsTransaction.date<=today)).all()
            contributed=sum(x.amount for x in tx if x.transaction_type=="contribution")
            pace=to_paise(goal["monthly_target"])
            if contributed<pace: add(f"goal:{goal['id']}",f"Savings goal pace: {goal['name']}",f"Recorded contributions this month are {assistant_rupees(pace-contributed)} below the goal's target-date monthly pace.","info")
    decreased=[(name,-change) for name,change in context["category_changes"].items() if change<0]
    if decreased:
        name,amount=max(decreased,key=lambda x:x[1])
        add(f"category_down:{name}",f"Spending decreased in {name}",f"This month to date is {assistant_rupees(amount)} below the same elapsed dates last month.","positive")
    subscriptions=[x for x in context["recurring"] if x["category"]=="Subscriptions"]
    if subscriptions:
        total=sum(x["amount"] for x in subscriptions)
        add("subscriptions_review","Review recurring subscriptions",f"You have {len(subscriptions)} active subscription reminder(s) totaling {assistant_rupees(total)} per recurrence. Confirm you still use each one.","info")
    return {"insights":insights,"period":current_month,"based_on":"saved account records","disclaimer":ASSISTANT_DISCLAIMER}


@app.get("/api/ai/insights")
def ai_insights(month: str = Query(default_factory=lambda: kolkata_today().strftime("%Y-%m")), user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = dashboard_summary(month, user, db); insights = []
    if s["expenses"] == 0: insights.append("Add your first expense to start seeing spending insights.")
    else:
        if s["net"] > 0: insights.append(f"You have ₹{s['net']:,.0f} left after recorded income and expenses this month.")
        if s["categories"]:
            category, amount = max(s["categories"].items(), key=lambda item:item[1])
            insights.append(f"{category} is your highest recorded spending category at ₹{amount:,.0f}.")
        for b in s["budgets"]:
            pct = b["spent"] / b["amount"] * 100 if b["amount"] else 0
            if pct >= 90: insights.append(f"{b['category']} budget is at {pct:.0f}% — consider pausing optional purchases.")
            elif pct >= 75: insights.append(f"{b['category']} budget has reached {pct:.0f}%.")
    return {"insights": insights, "data_period": month}


@app.post("/api/ai/chat")
def ai_chat(payload: dict, month: str = Query(default_factory=lambda: kolkata_today().strftime("%Y-%m")), user: User = Depends(current_user), db: Session = Depends(get_db)):
    question = str(payload.get("message", "")).strip()
    if not question: raise HTTPException(422, "Message is required")
    s = dashboard_summary(month, user, db); q = question.lower()
    if any(x in q for x in ("owe", "debt", "borrow")): answer = f"You owe friends ₹{s['owed_to_friends']:,.2f} and friends owe you ₹{s['owed_by_friends']:,.2f}."
    elif "category" in q or "spend" in q:
        top = max(s["categories"].items(), key=lambda i:i[1]) if s["categories"] else None
        answer = f"You spent ₹{s['expenses']:,.2f} this month." + (f" Your highest category is {top[0]} at ₹{top[1]:,.2f}." if top else " No expenses are recorded for this month yet.")
    elif "save" in q or "afford" in q: answer = f"Your recorded income minus expenses is ₹{s['net']:,.2f} this month. Treat this as an estimate; pending bills and upcoming needs may change what is safe to spend."
    elif "rent" in q:
        rent = s["categories"].get("Rent", 0); answer = f"Your recorded rent spending this month is ₹{rent:,.2f}. Add a rent reminder or budget if you want to plan for an upcoming payment."
    else: answer = f"For {month}, your recorded income is ₹{s['income']:,.2f}, expenses are ₹{s['expenses']:,.2f}, and net is ₹{s['net']:,.2f}. Ask about spending, categories, savings, rent, or friend debts."
    return {"answer": answer, "based_on": month, "disclaimer": "Planning support based on records you entered, not guaranteed financial advice."}
