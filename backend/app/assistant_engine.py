"""Private, deterministic rule-based financial answers and affordability estimates."""
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
import re


DISCLAIMER = "Informational planning estimate based on records you entered, not professional financial advice or a guaranteed outcome."


def add_months(day: date, count: int) -> date:
    index = day.year * 12 + day.month - 1 + count
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def question_range(question: str, today: date) -> tuple[date, date, str]:
    q = question.casefold()
    month_match = re.search(r"\b(20\d{2})-(0[1-9]|1[0-2])\b", q)
    if month_match:
        year, month = map(int, month_match.groups())
        lo = date(year, month, 1)
        return lo, date(year, month, monthrange(year, month)[1]), lo.strftime("%B %Y")
    named = re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)(?:\s+(20\d{2}))?\b", q)
    if named:
        month = ["january","february","march","april","may","june","july","august","september","october","november","december"].index(named.group(1))+1
        year = int(named.group(2)) if named.group(2) else today.year
        lo = date(year,month,1)
        return lo,date(year,month,monthrange(year,month)[1]),lo.strftime("%B %Y")
    if "last week" in q or "previous week" in q:
        end=today-timedelta(days=today.weekday()+1); start=end-timedelta(days=6)
        return start,end,"last week"
    if "next week" in q:
        start=today-timedelta(days=today.weekday())+timedelta(days=7)
        return start,start+timedelta(days=6),"next week"
    if "this week" in q:
        start=today-timedelta(days=today.weekday()); end=start+timedelta(days=6)
        return start,today,"this week"
    if "yesterday" in q:
        return today-timedelta(days=1),today-timedelta(days=1),"yesterday"
    if "today" in q:
        return today,today,"today"
    if "last 7 days" in q or "past 7 days" in q:
        return today-timedelta(days=6),today,"last 7 days"
    if "last year" in q or "previous year" in q:
        return date(today.year-1,1,1),date(today.year-1,12,31),str(today.year-1)
    if "this year" in q:
        return date(today.year,1,1),today,str(today.year)
    n=re.search(r"(?:last|past)\s+(\d+)\s+months?",q)
    if n:
        count=max(1,min(24,int(n.group(1))))
        return add_months(today.replace(day=1),-(count-1)),today,f"last {count} months"
    if "last month" in q or "previous month" in q:
        end=today.replace(day=1)-timedelta(days=1)
        return end.replace(day=1),end,end.strftime("%B %Y")
    start=today.replace(day=1)
    return start,today,start.strftime("%B %Y")


def rupees(paise: int) -> str:
    return f"₹{Decimal(paise) / Decimal(100):,.2f}"


def answer_question(question: str, context: dict) -> str:
    q=question.casefold()
    if any(k in q for k in ("ignore previous", "ignore all", "system prompt", "reveal", "password", "api key", "execute", "sql", "other user", "another user", "someone else", "all users")):
        return "I can only answer questions about your own PocketWise financial summaries. I can't reveal private system or account information or perform actions."
    if any(k in q for k in ("owe me", "owed to me", "friends owe", "owe you", "lent", "receivable")):
        return f"Friends owe you {rupees(context['owed_by_friends'])} across {context['receivable_count']} outstanding record(s). Expected repayments are not counted as available cash."
    if any(k in q for k in ("owe friends", "i owe", "borrowed", "payable")):
        return f"You owe friends {rupees(context['owed_to_friends'])} across {context['payable_count']} outstanding record(s)."
    if any(k in q for k in ("bill", "subscription", "recurring", "due next", "due soon", "payment due")):
        if "overdue" in q:
            rows=context["overdue_items"]
            if not rows:return "There are no unpaid overdue bill reminders in your records. This only reflects reminders you've entered."
            return "Overdue unpaid reminders: "+"; ".join(f"{x['title']} (due {x['due_date']}, {rupees(x['amount'])})" for x in rows[:8])+f". Total: {rupees(sum(x['amount'] for x in rows))}."
        if "subscription" in q or "recurring" in q:
            rows=context["recurring"]
            if not rows:return "I couldn't find active recurring bills in your records. Add a recurring reminder to review subscriptions here."
            return "Active recurring obligations to review: " + "; ".join(f"{x['title']} ({rupees(x['amount'])}, {x['frequency']})" for x in rows[:8]) + ". Consider cancelling services you no longer use."
        rows=context["due_next_week"]
        if not rows:return "There are no unpaid bill reminders due in the next 7 days in your records. This only reflects reminders you've entered."
        return "Unpaid bills due in the next 7 days: " + "; ".join(f"{x['title']} on {x['due_date']} ({rupees(x['amount'])})" for x in rows[:8]) + f". Total: {rupees(sum(x['amount'] for x in rows))}."
    if any(k in q for k in ("saved", "savings", "saving goal")) and not any(k in q for k in ("afford", "purchase", "buy")):
        return f"Your savings goals currently hold {rupees(context['savings_balance'])}. In {context['period_label']}, you recorded {rupees(context['contributions'])} in contributions and {rupees(context['withdrawals'])} in withdrawals across {context['goal_count']} goal(s)."
    if any(k in q for k in ("budget", "exceed", "over budget", "approaching")):
        selected=next((x for x in context["budget_categories"] if x["category"].casefold() in q),None)
        if selected:
            if not selected["budgeted"]:
                return f"{selected['category']} has no budget saved for {context['period_label']}; recorded spending is {rupees(selected['actual'])}."
            return f"{selected['category']} is {selected['utilization']:.0f}% of budget for {context['period_label']}: {rupees(selected['actual'])} spent from {rupees(selected['planned'])}, with {rupees(selected['planned']-selected['actual'])} remaining."
        rows=context["budget_alerts"]
        if not rows:return f"No categories are approaching or exceeding their budgets for {context['period_label']}. Budget status is based on the limits and expenses you've entered."
        return "Budget attention for " + context["period_label"] + ": " + "; ".join(f"{x['category']} is at {x['utilization']:.0f}% ({rupees(x['spent'])} of {rupees(x['limit'])}; {x['status']})" for x in rows[:8]) + "."
    if any(k in q for k in ("reduce", "cut", "lower", "save money", "spending advice")):
        top=context["top_category"]
        if not top:return "There isn't enough expense history yet to suggest a category to reduce. Add expenses across a few weeks, then ask again."
        increase=context.get("top_category_change")
        trend=f" It is up {rupees(increase)} versus the previous month." if increase and increase>0 else f" It is down {rupees(abs(increase))} versus the previous month." if increase and increase<0 else ""
        return f"{top['category']} is your highest spending category for {context['period_label']} at {rupees(top['amount'])}.{trend} Review optional purchases in this category first, and compare each change with your actual budget."
    if any(k in q for k in ("weekday", "weekend", "day of week")):
        return "I don't currently calculate weekday or weekend spending patterns. I can compare your saved monthly totals, categories, budgets, and payment methods instead."
    if any(k in q for k in ("income", "receive", "received", "earned")):
        source=next((name for name in context["income_sources"] if name.casefold() in q),None)
        if source:return f"You recorded {rupees(context['income_sources'][source])} from {source} during {context['period_label']}."
    if any(k in q for k in ("spend", "spent", "expense", "cost")):
        category=next((name for name in context["categories"] if name.casefold() in q),None)
        if category:return f"You recorded {rupees(context['categories'][category])} in {category} expenses during {context['period_label']}."
    if any(k in q for k in ("highest", "most", "category", "where did i spend")):
        top=context["top_category"]
        return f"Your highest spending category for {context['period_label']} is {top['category']} at {rupees(top['amount'])}." if top else f"No expenses are recorded for {context['period_label']}, so I can't identify a highest category."
    if "afford" in q or "purchase" in q or "buy" in q:
        amount_match=re.search(r"(?:₹|inr\s*)\s*([\d,]+(?:\.\d{1,2})?)|\b([\d,]+(?:\.\d{1,2})?)\s*(?:rupees|inr)\b",q)
        if not amount_match:return "Tell me the purchase amount, for example: ‘Can I afford ₹1,500?’ I’ll compare it with this month’s recorded cash flow, upcoming bills and planned reserves."
        amount=Decimal((amount_match.group(1) or amount_match.group(2)).replace(",",""))
        return context["affordability_answer"](int(amount*100))
    if any(k in q for k in ("spend", "expense", "cash flow", "income", "left over", "net")):
        if not context["has_activity"]:return f"I don't have income or expense records for {context['period_label']} yet, so I can't calculate spending or cash flow."
        return f"For {context['period_label']}, you recorded {rupees(context['income'])} income and {rupees(context['expenses'])} expenses. Net income minus expenses is {rupees(context['income']-context['expenses'])}. This excludes savings transfers and unpaid bill reminders."
    return "I can help with spending, category trends, budgets, savings, friend balances, bills due, recurring subscriptions, and purchase affordability. Ask a specific question about your records."


def affordability_result(amount: int, context: dict) -> dict:
    if amount <= 0: return {"classification":"insufficient_data","message":"Enter a purchase amount greater than zero."}
    if not context["has_activity"] and context["available_cash"] == 0:
        return {"classification":"insufficient_data","message":"There isn't enough recorded cash-flow information to estimate affordability. Add income and expense records first."}
    after= context["available_cash"] - context["upcoming_bills"] - context["budget_reserve"] - context["goal_reserve"] - amount
    if after < 0: label="not_recommended"
    elif after < max(50000, amount // 5): label="affordable_with_caution"
    else: label="affordable"
    message=(f"Current month cash-flow estimate: {rupees(context['available_cash'])}. "
        f"Less upcoming unpaid bills ({rupees(context['upcoming_bills'])}), planned budget remaining ({rupees(context['budget_reserve'])}), "
        f"and dated savings-goal pace ({rupees(context['goal_reserve'])}), then this purchase ({rupees(amount)}), leaves an estimated {rupees(after)}. "
        f"Current savings goal balances ({rupees(context['savings_balance'])}) and expected repayments are excluded from spendable cash.")
    return {"classification":label,"remaining":after,"message":message,"disclaimer":DISCLAIMER}
