from datetime import date as PythonDate, datetime, timezone
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, Index, UniqueConstraint, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def now_utc():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    friends: Mapped[list["Friend"]] = relationship(back_populates="user")
    incomes: Mapped[list["Income"]] = relationship(cascade="all, delete-orphan")
    expenses: Mapped[list["Expense"]] = relationship(cascade="all, delete-orphan")
    budgets: Mapped[list["Budget"]] = relationship(cascade="all, delete-orphan")
    goals: Mapped[list["SavingsGoal"]] = relationship(cascade="all, delete-orphan")
    savings_transactions: Mapped[list["SavingsTransaction"]] = relationship(cascade="all, delete-orphan")
    debts: Mapped[list["Debt"]] = relationship(cascade="all, delete-orphan")
    reminders: Mapped[list["Reminder"]] = relationship(cascade="all, delete-orphan")


class Income(Base):
    __tablename__ = "income"
    __table_args__ = (Index("ix_income_user_date", "user_id", "date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    amount: Mapped[int] = mapped_column(Integer)  # integer paise
    source: Mapped[str] = mapped_column(String(100))
    date: Mapped[PythonDate] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(500), default="")
    notes: Mapped[str] = mapped_column(Text, default="")


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (Index("ix_expenses_user_date", "user_id", "date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    amount: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(60))
    date: Mapped[PythonDate] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(500), default="")
    payment_method: Mapped[str] = mapped_column(String(40), default="UPI")
    notes: Mapped[str] = mapped_column(Text, default="")


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("user_id", "category", "month", name="uq_budget_user_category_month"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(60))
    amount: Mapped[int] = mapped_column(Integer)
    month: Mapped[str] = mapped_column(String(7), index=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class SavingsGoal(Base):
    __tablename__ = "savings_goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    target_amount: Mapped[int] = mapped_column(Integer)
    target_date: Mapped[PythonDate | None] = mapped_column(Date, nullable=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    opening_balance: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(String(500), default="")
    category: Mapped[str] = mapped_column(String(40), default="Other")
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    transactions: Mapped[list["SavingsTransaction"]] = relationship(cascade="all, delete-orphan")


class SavingsTransaction(Base):
    __tablename__ = "savings_transactions"
    __table_args__ = (Index("ix_savings_tx_user_goal_date", "user_id", "goal_id", "date"),
                      UniqueConstraint("user_id", "request_id", name="uq_savings_user_request"))
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    goal_id: Mapped[int] = mapped_column(ForeignKey("savings_goals.id", ondelete="CASCADE"))
    transaction_type: Mapped[str] = mapped_column(String(20))
    amount: Mapped[int] = mapped_column(Integer)
    date: Mapped[PythonDate] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Friend(Base):
    __tablename__ = "friends"
    __table_args__ = (Index("ix_friends_user_name", "user_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    nickname: Mapped[str | None] = mapped_column(String(80), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    user: Mapped["User"] = relationship(back_populates="friends")
    debts: Mapped[list["Debt"]] = relationship(back_populates="friend")


class Debt(Base):
    __tablename__ = "debts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    friend_id: Mapped[int | None] = mapped_column(ForeignKey("friends.id", ondelete="RESTRICT"), nullable=True)
    friend_name: Mapped[str] = mapped_column(String(120))  # retained for old API/data compatibility
    direction: Mapped[str] = mapped_column(String(10))  # borrowed or lent
    amount: Mapped[int] = mapped_column(Integer)
    date: Mapped[PythonDate] = mapped_column(Date)
    due_date: Mapped[PythonDate | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    friend: Mapped[Friend | None] = relationship(back_populates="debts")
    repayments: Mapped[list["DebtRepayment"]] = relationship(cascade="all, delete-orphan")


class DebtRepayment(Base):
    __tablename__ = "debt_repayments"
    id: Mapped[int] = mapped_column(primary_key=True)
    debt_id: Mapped[int] = mapped_column(ForeignKey("debts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    amount: Mapped[int] = mapped_column(Integer)
    date: Mapped[PythonDate] = mapped_column(Date)
    note: Mapped[str] = mapped_column(String(300), default="")
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (UniqueConstraint("schedule_id", "due_date", name="uq_reminder_schedule_occurrence"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    amount: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[PythonDate] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(60), default="Other")
    recurrence: Mapped[str] = mapped_column(String(20), default="once")
    paid: Mapped[bool] = mapped_column(default=False)
    description: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="upcoming")
    schedule_id: Mapped[int | None] = mapped_column(ForeignKey("recurring_schedules.id", ondelete="SET NULL"), nullable=True)
    reminder_days: Mapped[list[int]] = mapped_column(JSON, default=lambda: [3, 1, 0])
    paid_at: Mapped[PythonDate | None] = mapped_column(Date, nullable=True)
    actual_paid_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id", ondelete="SET NULL"), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class RecurringSchedule(Base):
    __tablename__ = "recurring_schedules"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    amount: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(60), default="Other")
    description: Mapped[str] = mapped_column(String(500), default="")
    frequency: Mapped[str] = mapped_column(String(20))
    interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[PythonDate] = mapped_column(Date)
    end_date: Mapped[PythonDate | None] = mapped_column(Date, nullable=True)
    reminder_days: Mapped[list[int]] = mapped_column(JSON, default=lambda: [3, 1, 0])
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ReminderPayment(Base):
    __tablename__ = "reminder_payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reminder_id: Mapped[int] = mapped_column(ForeignKey("reminders.id", ondelete="CASCADE"), index=True)
    paid_date: Mapped[PythonDate] = mapped_column(Date)
    actual_amount: Mapped[int] = mapped_column(Integer)
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id", ondelete="SET NULL"), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    advance_days: Mapped[list[int]] = mapped_column(JSON, default=lambda: [3, 1, 0])
    browser_enabled: Mapped[bool] = mapped_column(Boolean, default=False)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("user_id", "source_type", "source_id", "remind_on", name="uq_notification_occurrence"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(20))
    source_id: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(180))
    message: Mapped[str] = mapped_column(String(400))
    remind_on: Mapped[PythonDate] = mapped_column(Date)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class PasswordResetOTP(Base):
    __tablename__ = "password_reset_otps"
    __table_args__ = (Index("ix_password_reset_email_created", "email", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[int] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
