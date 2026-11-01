from datetime import date as DateType
from datetime import datetime
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


def kolkata_today():
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


class Register(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value):
        value=value.strip()
        if len(value)<2:
            raise ValueError("Name must contain at least two non-space characters")
        return value


class Login(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AssistantChat(BaseModel):
    message: str = Field(min_length=1, max_length=1200)

    @field_validator("message")
    @classmethod
    def trim_question(cls, value):
        value=value.strip()
        if not value:
            raise ValueError("Question cannot be blank")
        return value


class AffordabilityCheck(BaseModel):
    amount: Decimal = Field(gt=0, le=100000000, max_digits=12, decimal_places=2)


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MoneyRecord(BaseModel):
    amount: Decimal = Field(gt=0, le=100000000, max_digits=12, decimal_places=2)
    date: DateType
    description: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=2000)


class IncomeCreate(MoneyRecord):
    source: Literal["Monthly allowance from home", "Scholarship", "Part-time income", "Freelancing", "Gifts", "Other income", "Allowance"]


class ExpenseCreate(MoneyRecord):
    category: Literal["Rent", "Electricity", "Food", "Groceries", "Travel", "Clothes", "Shopping", "Education", "Entertainment", "Subscriptions", "Healthcare", "Other"]
    payment_method: Literal["Cash", "UPI", "Card", "Bank transfer", "Other"] = "UPI"


class BudgetCreate(BaseModel):
    category: Literal["Rent", "Electricity", "Food", "Groceries", "Travel", "Clothes", "Shopping", "Education", "Entertainment", "Subscriptions", "Healthcare", "Other"]
    amount: Decimal = Field(gt=0, le=100000000, max_digits=12, decimal_places=2)
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    year: int | None = Field(default=None, ge=1900, le=2200)
    description: str = Field(default="", max_length=300)

    @field_validator("month")
    @classmethod
    def validate_month(cls, value):
        try:
            datetime.strptime(value, "%Y-%m")
        except ValueError as exc:
            raise ValueError("Month must be a valid calendar month in YYYY-MM format") from exc
        return value

    @field_validator("year")
    @classmethod
    def validate_year_matches_month(cls, value, info):
        month = info.data.get("month")
        if value is not None and month and value != int(month[:4]):
            raise ValueError("Year must match the selected month")
        return value


class GoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    target_amount: Decimal = Field(gt=0, le=100000000, max_digits=12, decimal_places=2)
    target_date: DateType | None = None
    description: str = Field(default="", max_length=500)
    category: Literal["Emergency fund", "Education", "Electronics", "Travel", "Personal", "Other"] = "Other"
    priority: Literal["low", "medium", "high"] = "medium"
    status: Literal["active", "paused", "completed"] = "active"


class Contribution(BaseModel):
    amount: Decimal = Field(gt=0, le=100000000, max_digits=12, decimal_places=2)
    date: DateType = Field(default_factory=kolkata_today)
    notes: str = Field(default="", max_length=2000)
    note: str | None = Field(default=None, max_length=2000)
    request_id: str | None = Field(default=None, max_length=100)


class FriendCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    nickname: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    notes: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Friend name cannot be blank")
        return value


class DebtCreate(BaseModel):
    friend_id: int | None = Field(default=None, gt=0)
    friend_name: str | None = Field(default=None, min_length=1, max_length=120)
    direction: Literal["borrowed", "lent"]
    amount: Decimal = Field(gt=0, le=100000000, max_digits=12, decimal_places=2)
    date: DateType
    due_date: DateType | None = None
    description: str = Field(default="", max_length=300)


class RepaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, le=100000000, max_digits=12, decimal_places=2)
    date: DateType = Field(default_factory=kolkata_today)
    notes: str = Field(default="", max_length=300)
    note: str | None = Field(default=None, max_length=300)  # old clients may still send `note`
    request_id: str | None = Field(default=None, max_length=100)


class ReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    amount: Decimal = Field(gt=0, le=100000000, max_digits=12, decimal_places=2)
    due_date: DateType
    category: Literal["Rent", "Electricity", "Water", "Internet", "Mobile recharge", "Subscriptions", "Education fees", "Insurance", "Other"] = "Other"
    recurrence: Literal["once", "weekly", "monthly", "quarterly", "yearly", "custom"] = "once"
    interval_days: int | None = Field(default=None, ge=1, le=365)
    end_date: DateType | None = None
    description: str = Field(default="", max_length=500)
    reminder_days: list[int] | None = Field(default=None, max_length=8)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Bill title cannot be blank")
        return value

    @field_validator("reminder_days")
    @classmethod
    def validate_reminder_days(cls, value):
        if value is None: return value
        if any(day < 0 or day > 365 for day in value) or len(set(value)) != len(value):
            raise ValueError("Reminder days must be unique values from 0 to 365")
        return sorted(value, reverse=True)

    @model_validator(mode="after")
    def validate_custom_recurrence(self):
        if self.recurrence == "custom" and self.interval_days is None:
            raise ValueError("Custom recurrence requires interval_days")
        if self.end_date and self.end_date < self.due_date:
            raise ValueError("end_date must be on or after the first due date")
        return self


class ReminderPaymentCreate(BaseModel):
    paid_date: DateType = Field(default_factory=kolkata_today)
    actual_amount: Decimal | None = Field(default=None, gt=0, le=100000000, max_digits=12, decimal_places=2)
    expense_id: int | None = Field(default=None, gt=0)
    create_expense: bool = False


class NotificationPreferenceUpdate(BaseModel):
    advance_days: list[int] = Field(default_factory=lambda: [3, 1, 0], max_length=8)
    browser_enabled: bool = False

    @field_validator("advance_days")
    @classmethod
    def validate_advance_days(cls, value):
        if any(day < 0 or day > 365 for day in value) or len(set(value)) != len(value):
            raise ValueError("Advance reminder days must be unique values from 0 to 365")
        return sorted(value, reverse=True)
