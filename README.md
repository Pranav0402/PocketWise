# PocketWise

PocketWise is a student-focused personal finance application for tracking income, expenses, budgets, savings goals, friend debts and payment reminders. Currency is INR. Financial values are stored as integer paise; the API uses rupee amounts at its JSON boundary.

Students often track allowances, small purchases, shared expenses, bills and savings in separate places. PocketWise brings these records together in one account-scoped workspace, with clear summaries that distinguish actual cash activity from savings movements, debt and upcoming obligations.

## Screens and modules

- Landing, login and registration screens.
- Dashboard with monthly income and expense summaries, cash position, category charts, recent activity, savings and upcoming obligations.
- Income and expense history with create, edit, delete, search and filters.
- Friends and debts, including borrowing, lending, due dates and repayment history.
- Monthly category budgets and spending progress.
- Savings goals with contribution and withdrawal ledgers.
- One-time and recurring bill reminders, payment history and notifications.
- Financial reports with date filters and CSV export.
- Record-based finance assistant with an optional local Ollama provider.
- Separate `/demo` dashboard with fictional sample data, responsive navigation and an independent theme setting.

## Architecture

The browser talks to the FastAPI service through JSON endpoints. Authentication is bearer-token based; the API scopes financial records to the signed-in user. SQLAlchemy stores data in SQLite for local development or PostgreSQL when configured for deployment. The assistant defaults to deterministic, record-based rules; Ollama is an optional loopback-only provider.

```mermaid
flowchart LR
  User[Student] --> Web[React + Vite + Tailwind PWA]
  Web -->|JSON + bearer token| API[FastAPI + Pydantic]
  API --> Auth[Authentication and account scoping]
  API --> Services[Finance, budgets, savings, debts, reminders, reports]
  Services --> ORM[SQLAlchemy]
  ORM --> DB[(SQLite local or PostgreSQL)]
  Services --> Assistant[Rules-based finance assistant]
  Assistant -. optional loopback .-> Ollama[Local Ollama model]
  Demo[/demo fictional UI/] -. isolated from API .-> Web
```

## Technology stack

| Layer | Technologies |
| --- | --- |
| Frontend | React 19, Vite, Tailwind CSS 4, React Router, Recharts, Lucide |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy |
| Authentication | Argon2 password hashing, signed JWT bearer tokens |
| Storage | SQLite for local development; PostgreSQL via `psycopg` when configured |
| Tests | Pytest and HTTPX for the API; Node.js built-in test runner for frontend utilities |
| Progressive web app | Web manifest, install icons, service worker and offline shell |

## Requirements

- Python 3.10+
- Node.js 20+

## Local setup in Windows / VS Code

Open the PocketWise folder in VS Code. In a PowerShell terminal at the repository root, copy `.env.example` to `.env` and replace `SECRET_KEY` with a random value (for example, run `python -c "import secrets; print(secrets.token_urlsafe(48))"` and paste the output). The example file contains placeholders only and is safe to commit; `.env` is ignored by Git.

## Run locally

In PowerShell, from the repository root:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Visit http://localhost:5173. The backend API and interactive schema are at http://localhost:8000 and http://localhost:8000/docs.

Vite proxies `/api` to the local backend, so the frontend defaults to a same-origin `/api` path. Set `VITE_API_URL` only when the deployed API is on a separate origin.

## Frontend demo

Visit http://localhost:5173/demo (or choose **View demo** on the landing page) to explore the responsive dashboard without creating an account. The demo's fictional sample data lives in `frontend/src/pages/demoData.js`; it is separate from the API-backed account views and is never posted to or stored by the backend. The demo includes working sidebar sections, transaction search and type filters, a mobile navigation drawer, and a light/dark theme toggle.

## Income and expense management

After signing in, use **Income** or **Expenses** in the sidebar to manage the authenticated account's records. Both pages support create, edit, delete, search, date range filtering, and amount/date sorting. Income records use a source category and may include notes. Expense records include a category, payment method, and optional notes. All transaction requests require the user's JWT; the API applies `user_id` scoping to reads, updates, and deletes. Decimal request amounts are validated to two decimal places and stored as integer paise.

The backend initializes missing SQLite tables at startup and applies non-destructive schema upgrades. Existing debt rows are preserved: startup adds nullable friend/repayment metadata columns, links old friend names to new friend profiles per account, and associates existing repayments with their debt owner. Existing budget rows gain year, description and timestamp fields. A per-user/category/month unique index is added where existing data permits; duplicate legacy budgets are preserved and API writes still reject new duplicates. Back up a production database before upgrades and use Alembic for managed production schema changes. Dashboard income and expenses remain separate from debt activity; `debt_cash_flow` and `available_cash_change` separately account for borrowing, lending, and principal repayments. The `/demo` route continues to use the isolated fictional dataset described above.

## Friends, borrowing and lending

The authenticated **Friends & debts** area supports optional friend contact details, per-friend summaries, borrowing and lending records, deadlines, filtering, and repayment histories. Each repayment is a separate integer-paise record; repayments do not change the original principal and are not categorized as income or expenses. Records with repayment history cannot be edited or deleted, and friends with financial records cannot be deleted, preserving the audit trail. Submissions accept an optional idempotency key (`request_id`) to safely retry repayments.

Debt statuses are calculated from the outstanding balance and due date: `unpaid`, `partial`, `fully_paid`, or `overdue`. The summary supports `month`, `year`, `friend_id`, `direction`, and `status` filters. The default dashboard debt totals are account-wide outstanding amounts; cash movement metrics are scoped to the selected dashboard month.

## Monthly budgets

The authenticated **Budgets** area creates one monthly limit per category, edits and deletes plans, copies categories forward from the previous month, and shows historical planned versus actual totals. Category cards distinguish normal (<75%), warning (75% to <90%), critical (90% to 100%), exceeded (>100%), and unbudgeted spending. Actuals come only from authenticated expense records; unbudgeted expenses remain visible in total spending but have no invented zero limit. Alerts are derived from current spending, so page refreshes do not create duplicate alert records. The standard expense categories are used so budget categories match expense categories.

Frontend transaction checks run with `cd frontend; npm test`. Backend API tests run with `cd backend; python -m pytest`.

## Savings goals

The authenticated **Savings goals** area supports goal creation, editing, deletion (only when no history would be lost), pausing/resuming, and marking a goal complete. Goals include category, priority, target date, and description. Goal detail pages show progress, remaining balance, planner pace, and contribution/withdrawal history. Summary filters support a month or year. Emergency fund guidance is calculated only from the signed-in user's recorded expense history; it does not create or assume a goal.

Contributions and withdrawals are separate ledger entries stored in integer paise. They change reserved goal balances and the dashboard's `available_cash_change`, but are not reclassified as income or expenses. Withdrawals cannot exceed the current goal balance. Entries can be edited or removed, and a `request_id` makes transaction submissions safe to retry. On startup, the backward-compatible savings migration adds goal metadata and copies each pre-ledger `balance` into `opening_balance` once; later balances are derived from that opening amount and the ledger.

Savings endpoints (all require authentication): `GET|POST /api/savings`, `GET|PUT|DELETE /api/savings/{id}`, `GET /api/savings/summary?month=YYYY-MM` or `?year=YYYY`, `GET /api/savings/{id}/contributions`, `POST /api/savings/{id}/contributions`, `POST /api/savings/{id}/withdrawals`, and `PUT|DELETE /api/savings/{id}/transactions/{transaction_id}`. Legacy contribution edit/delete routes remain available.

## Payment reminders and recurring bills

The authenticated **Payment reminders** page supports one-time and recurring bills, upcoming/overdue/due-today/paid/cancelled states, a month calendar and year list, category/status filters, payment history, notification preferences, and in-app notification history. Monthly, weekly, quarterly, yearly, and custom-day recurrence create occurrence rows at most once. Monthly/yearly occurrences retain their original day anchor (for example, a due date on the 31st clamps to February's last day and returns to the 31st in March). Recurring schedules are expanded through the next year when reminders, calendar, or notification endpoints are read; a unique schedule/date key prevents duplicates. Cancelling a series cancels unpaid occurrences and leaves paid history intact.

Marking a bill paid records the actual date and amount. The user may leave it as payment history, link an existing expense, or explicitly create one expense. A linked expense is represented once in ordinary expense totals; unpaid reminders never count as expenses. Friend debt due dates appear in the calendar as payable or receivable projections using outstanding debt balances. The reminders module does not create debt or repayment records. Summary values label unpaid bills and upcoming amounts as estimates, separate from actual expenses.

The notification center records in-app alerts once per bill/debt deadline and supports configurable advance days. Browser permission is requested only after the user presses **Enable browser alerts**; if browser notifications are unavailable or denied, in-app history remains available.

Reminder endpoints (all require authentication): `GET|POST /api/reminders`, `GET|PUT|DELETE /api/reminders/{id}`, `POST /api/reminders/{id}/cancel`, `POST /api/reminders/{id}/mark-paid`, `GET /api/reminders/{id}/payments`, `GET /api/reminders/calendar?month=YYYY-MM` or `?year=YYYY`, `GET /api/reminders/summary`, `GET /api/reminders/recurring`, `DELETE /api/reminders/recurring/{schedule_id}`. Notification endpoints: `GET /api/notifications`, `POST /api/notifications/{id}/read`, `GET|PUT /api/notifications/preferences`.

## Reports and analytics

The authenticated **Reports & analytics** page aggregates the current user's saved transaction, budget, savings, debt and bill records. Select this week, this month, previous month, the last 3 or 6 months, this year, previous year, or a custom date range. Income/expense reports also support transaction type, category and payment method filters. Reports include cash-flow trends, expense categories, income sources, payment methods, budget utilization and unbudgeted/exceeded categories, goal progress and savings activity, separately owed/receivable friend balances, and paid/unpaid/upcoming/overdue bill information. Savings and principal repayment activity remain separate from ordinary income and expenses; unpaid reminders are obligations and never count as expenses. The `/demo` experience remains static and is not queried or exported through authenticated report APIs.

All report endpoints require a bearer token. Date parameters use ISO `YYYY-MM-DD`; `period` accepts `this_week`, `this_month`, `previous_month`, `last_3_months`, `last_6_months`, `this_year`, `previous_year`, or `custom`. Custom ranges require both `start_date` and `end_date`. Summary/cash-flow/categories also accept `transaction_type=income|expense`, `category`, and `payment_method`.

- `GET /api/reports/summary` ? selected-period totals, budget utilization, balances and obligations.
- `GET /api/reports/cash-flow` ? monthly income, expenses, net and separate savings movements.
- `GET /api/reports/categories` ? expense categories, income sources, payment methods and average monthly expenses.
- `GET /api/reports/budgets` ? planned versus actual by month/category, with exceeded, approaching and unbudgeted rows.
- `GET /api/reports/savings` ? current goal balances/progress and filtered activity.
- `GET /api/reports/debts` ? borrowed/lent totals, repayments, outstanding balances and overdue deadlines.
- `GET /api/reports/reminders` ? paid history, unpaid obligations, upcoming/overdue bills and categories.
- `GET /api/reports/export?section=summary|transactions|budgets|savings|debts|reminders` ? filtered CSV attachment. Amount columns are labeled INR and include rupee values; record IDs and credentials are omitted. Empty sections export headers only.

Date filtering applies to dated activity; current outstanding debt and savings goal balances are lifetime/current balances, with dated movements limited to the selected interval. A reminder linked to an expense remains a single actual expense, while reminder payment history is reported independently.

## AI Finance Assistant

The authenticated **AI Finance Assistant** answers common questions using only the signed-in user's records. The default rule-based engine works without a model or paid API. It supports monthly and date-specific spending, highest categories, budget warnings, current savings balances/activity, separately owed-to/owed-by friend balances, upcoming/overdue bills, recurring subscription reminders, and purchase affordability. Affordability is a conservative estimate based on the current month's recorded cash movement, upcoming unpaid reminders, remaining budget limits, and dated goal contribution pace; it cannot read an actual bank balance and excludes outstanding expected repayments. Answers and generated insights explain the records they use and are informational, not professional financial advice.

The chat history exists only in the open browser session and **Clear chat** removes it locally. Questions are length-limited, the assistant has no transaction-writing tools, and user text cannot choose an account ID or run SQL/code. Financial context is selected server-side by the bearer token and never comes from `/demo`.

Optional local Ollama support is disabled by default. Install and run Ollama locally, pull a model, then configure the backend environment (no API key is used):

```dotenv
ASSISTANT_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:3b
```

The Ollama adapter only accepts loopback HTTP addresses, sends a compact account summary (not raw transaction descriptions or identifiers), has a short timeout, and automatically falls back to the rule engine if the local service is unavailable. Keep `ASSISTANT_PROVIDER=rules` to ensure no model request is made. Never point the assistant provider at an internet host.

Authenticated assistant endpoints:

- `POST /api/assistant/chat` with `{ "message": "How much did I spend last month?" }`
- `GET /api/assistant/insights` for unique, record-backed observations
- `GET /api/assistant/suggestions` for suggested questions
- `POST /api/assistant/affordability` with `{ "amount": "1500.00" }`

Example questions: ?What is my highest spending category??, ?Am I exceeding any budget??, ?How much do my friends owe me??, ?What bills are due next week??, ?Which recurring bills should I review??, ?Can I afford â‚¹1,500??, and ?How can I reduce my monthly expenses?? Questions can name periods such as last week, last month, last 3 months, a month name, or `YYYY-MM`. If records do not support an answer, the assistant says what is missing rather than filling in a number.

## Configuration

Copy `.env.example` to `.env`, set a long random `SECRET_KEY`, and set `DATABASE_URL` and `CORS_ORIGINS` for your environment. SQLite is initialized automatically on API startup. SQLAlchemy models are portable to PostgreSQL; set `DATABASE_URL` to a PostgreSQL SQLAlchemy URL and install a matching PostgreSQL driver before deployment. Use Alembic migrations before operating against persistent production data.

## Features

- Email/password registration and login with Argon2 password hashing and expiring JWT bearer tokens.
- Account scoped API access for income, expenses, budgets, savings, reminders and debts.
- Month summary, year analytics, reports and CSV-ready data APIs.
- Friend profiles and linked borrowing/lending records preserve original principal and store each partial repayment independently.
- Debt analytics include status, deadline, repayment and borrowed-versus-lent summaries; principal movements are shown separately from earned income and ordinary expenses.
- Monthly category budgets include safe duplicate prevention, paise-accurate utilization, threshold alerts, unbudgeted spending visibility and historical summaries.
- Savings goals support paise-accurate contribution/withdrawal history, legacy balance migration, cash-flow integration, user-recorded emergency fund guidance, and target-date planning.
- Payment reminders support calendar and recurring bill occurrences, payment history, in-app/browser notifications, and debt deadline projections without mixing estimates with actual expenses.
- A private AI Finance Assistant with rule-based chat, record-backed insights, affordability estimates, and optional loopback-only Ollama fallback.
- Responsive dashboard, charts, search, category filters by search, and mobile navigation.

## API overview

All financial endpoints require `Authorization: Bearer <token>`.

- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `GET|POST /api/income`, `GET|POST /api/expenses`
- `GET|POST /api/budgets`, `GET|PUT|DELETE /api/budgets/{id}`
- `GET /api/budgets/summary?month=YYYY-MM`, `GET /api/budgets/history?year=YYYY`
- `GET|POST /api/savings`, `GET|PUT|DELETE /api/savings/{id}`, `GET /api/savings/summary?month=YYYY-MM`
- `GET /api/savings/{id}/contributions`, `POST /api/savings/{id}/contributions`, `POST /api/savings/{id}/withdrawals`, `PUT|DELETE /api/savings/{id}/transactions/{transaction_id}`
- `GET|POST /api/reminders`, `GET|PUT|DELETE /api/reminders/{id}`, `POST /api/reminders/{id}/cancel`, `POST /api/reminders/{id}/mark-paid`, `GET /api/reminders/{id}/payments`
- `GET /api/reminders/calendar?month=YYYY-MM` or `?year=YYYY`, `GET /api/reminders/summary`, `GET /api/reminders/recurring`, `DELETE /api/reminders/recurring/{schedule_id}`
- `GET /api/notifications`, `POST /api/notifications/{id}/read`, `GET|PUT /api/notifications/preferences`
- `GET|POST /api/friends`, `GET|PUT|DELETE /api/friends/{id}`
- `GET|POST /api/debts`, `GET|PUT|DELETE /api/debts/{id}`
- `GET|POST /api/debts/{id}/repayments`, `GET /api/debts/summary`
- `GET /api/debts?month=YYYY-MM&friend_id=1&direction=borrowed&status=partial`
- `GET|POST /api/reminders`
- `GET /api/dashboard/summary?month=YYYY-MM`, `GET /api/dashboard/analytics?year=YYYY`
- `GET /api/reports/summary`, `/cash-flow`, `/categories`, `/budgets`, `/savings`, `/debts`, `/reminders`, `/export`
- `POST /api/assistant/chat`, `GET /api/assistant/insights`, `GET /api/assistant/suggestions`, `POST /api/assistant/affordability`
- Legacy `GET /api/reports/monthly` and `/category`, `GET /api/ai/insights`, `POST /api/ai/chat`

## Tests

```powershell
cd backend
pip install -r requirements.txt
python -m pytest
```

The test suite covers authentication and user isolation, friend profile CRUD, borrowing/lending records, repayment idempotency and overpayment guards, overdue status, integer-paise dashboard cash flow, income/expense CRUD, budget CRUD/duplicates, category utilization thresholds, reminder payment handling, expense-link deduplication, recurring generation/month-end dates/cancellation, notification deduplication, debt calendar projections, reports aggregation/date filters/category and payment method filtering, savings/debt/reminder separation, CSV escaping and account isolation, assistant spending/category/budget/savings/debt/bill question handling, affordability, prompt-injection refusal, Ollama fallback, insights and account isolation, migrations, and savings goal CRUD, transaction validation/idempotency, withdrawals, planning, cash flow, and legacy balances. Frontend Node tests cover assistant conversation reset, report query filters, reminder filters, savings planning and cash movement, debt and budget calculations, demo-data isolation, and existing financial helpers.

## Deployment notes

Set secrets only in the hosting platform's environment configuration. Use HTTPS, a managed PostgreSQL database, restrictive CORS origins, Alembic migrations, backups, and operational monitoring before accepting real user records. Never request bank passwords, UPI PINs or OTPs. Optional local Ollama integration can be added behind a server-side provider interface; core functionality does not depend on a paid AI API.

## Milestone 9: production hardening, performance and PWA

### Feature and architecture overview

PocketWise keeps the public fictional `/demo` experience separate from authenticated account routes. The frontend is React, Vite, Tailwind CSS and React Router, with Recharts loaded only on the pages that need charts. The FastAPI backend uses Pydantic validation and SQLAlchemy. Financial values are stored as integer paise and formatted as INR at API boundaries. SQLite is used locally; SQLAlchemy and the `psycopg` driver support PostgreSQL deployments.

Authenticated APIs use Argon2 password hashes (through `pwdlib`) and signed JWT bearer tokens. JWTs must have a valid expiration and user subject. Every financial query is scoped by the authenticated user. The browser keeps the bearer token in `sessionStorage`; older PocketWise `localStorage` tokens are moved to the current tab session and removed from persistent storage. This reduces persistence after closing the tab, but JavaScript running on the page can still access a bearer token, so keep frontend dependencies updated and protect the site against script injection. The backend does not accept bank passwords, UPI PINs or OTPs.

The API only permits configured CORS origins; production requires explicit HTTPS origins, a non-placeholder secret of at least 32 characters and `AUTO_MIGRATE=false`. API responses are marked `no-store`; security headers are applied to API responses. JSON request bodies with a declared `Content-Length` above 1 MiB are rejected. Put a reverse proxy/WAF request-size and rate limit in front of a public deployment. This app does not implement a distributed rate limiter; in-process throttling would not reliably protect multiple workers or replicas. Authentication errors are generic. CSV exports escape cells that spreadsheet software could interpret as formulas and use a fixed set of export sections.

The optional assistant provider defaults to deterministic rules. Ollama is only called if explicitly configured and the backend adapter accepts loopback URLs only. Do not point it at a public or internet-facing model service.

### Environment variables

Copy `.env.example` to `.env` for local development and never commit `.env` or production secret files.

| Variable | Local example | Production guidance |
| --- | --- | --- |
| `SECRET_KEY` | Placeholder in example; replace locally | Generate a unique random value with `python -c "import secrets; print(secrets.token_urlsafe(48))"`; store in the host secret manager |
| `APP_ENVIRONMENT` | `development` | `production` |
| `ACCESS_TOKEN_MINUTES` | `1440` | Choose a shorter lifetime if the product's session UX supports it |
| `DATABASE_URL` | `sqlite:///./pocketwise.db` | Persistent database URL; for PostgreSQL use `postgresql+psycopg://...` |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated, exact HTTPS frontend origins; no wildcard |
| `AUTO_MIGRATE` | `true` | Set `false`; run the schema initializer explicitly before starting the API |
| `VITE_API_URL` | Blank (Vite proxy + `/api`) | Set to `https://<api-host>/api` when the API is hosted separately; rebuild frontend after changing it |
| `ASSISTANT_PROVIDER` | `rules` | Keep `rules` unless you intentionally operate a loopback Ollama sidecar |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | Loopback URL / local model name | Ollama is optional and must not be internet-exposed |

### Database schema upgrades

In development, the backend creates missing tables and applies its existing backward-compatible SQLAlchemy schema upgrades on startup. Before production, take a database backup and set `AUTO_MIGRATE=false`. Run the existing schema initializer once from the backend folder using the production environment:

```powershell
cd backend
python -c "import app.models.models; from app.core.database import initialize_database; initialize_database()"
```

Then start/restart the API. The API import will not make schema changes with `AUTO_MIGRATE=false`. This project currently uses its compatibility initializer rather than Alembic revision files; review the initializer and test a backup restore before a production schema change. A health check is available at `/api/health` and returns 503 if the database cannot be reached.

### Tests and production build

From the repository root:

```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m pytest -q
cd ..\frontend
npm.cmd test
npm.cmd run build
```

To run the local backend and frontend, use the commands in Local setup in separate VS Code terminals. The frontend production files are created in `frontend/dist`.

### PWA installation and offline behavior

The frontend ships `frontend/public/manifest.webmanifest`, 192 px and 512 px icons, a service worker and an offline fallback page. A secure HTTPS deployment (or localhost during development) is required for browser installation. Use the browser's Install app / Add to Home Screen command.

The worker caches only the app shell and same-origin versioned static assets. It explicitly skips `/api/`, requests carrying Authorization, non-GET requests and cross-origin requests. Financial records, authentication responses and assistant conversations are not stored for offline use. Dashboard data, forms, reports, registration/login and assistant features need an internet connection and a working API. When offline, a simple offline page is shown; reconnect and retry to continue.

### Deployment guide (no deployment has been performed)

A practical free-tier demonstration setup is Vercel for the static React frontend, a free Render web service for FastAPI, and a Supabase Free PostgreSQL database. Verify each provider's current terms and quotas before use. Vercel Hobby is intended for personal, non-commercial usage and includes usage caps ([Vercel Hobby plan](https://vercel.com/docs/plans/hobby)). Render free web services sleep after 15 minutes without traffic, take about a minute to wake, and have ephemeral filesystems, so never put the production SQLite database on a free Render service ([Render free services](https://render.com/docs/free)). Supabase Free currently lists 500 MB for the database and pauses projects after a week of low activity; treat this as a demo/learning tier and arrange verified backups before storing financial records relied on by users ([Supabase pricing](https://supabase.com/pricing), [Supabase free PostgreSQL FAQ](https://supabase.com/kb/faqs/platform/free-postgres-for-side-projects)). Free plans can change, and free database plans may not provide the backup guarantees needed for real financial records.

**Frontend (Vercel static site):** Create a project from the `frontend` directory. Build command: `npm run build`; output directory: `dist`; install command: `npm install`. Set `VITE_API_URL=https://<your-api-host>/api` in the frontend project's build environment. `frontend/vercel.json` provides SPA route fallback and baseline browser security headers. Deploy the API first so you can configure its exact origin in backend CORS, then rebuild/deploy the frontend with the API URL. Vercel Hobby is free for personal/non-commercial projects; check current policy and usage limits before public or commercial use.

**Email password recovery (Gmail SMTP):** Configure these environment variables on the backend hosting service (Render → PocketWise service → Environment), not only as GitHub Actions secrets:

- `SMTP_HOST=smtp.gmail.com`
- `SMTP_PORT=587`
- `SMTP_USERNAME=<the dedicated PocketWise Gmail address>`
- `SMTP_PASSWORD=<the Google App Password>`
- `SMTP_FROM_EMAIL=<the same Gmail address>`

Keep the App Password private and never commit it to the repository. The app sends a six-digit email OTP that expires after 10 minutes, allows up to five verification attempts, and returns a generic request response to avoid revealing whether an email is registered. SMS and phone-number recovery are not used. If SMTP is not configured, the reset request endpoint returns a temporary delivery error.

**Backend (Render web service):** Create a Python web service rooted at `backend`. Build command: `pip install -r requirements.txt`. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers`. Set `APP_ENVIRONMENT=production`, `AUTO_MIGRATE=false`, a generated `SECRET_KEY`, the database URL, `CORS_ORIGINS=https://<your-frontend-host>`, and `ASSISTANT_PROVIDER=rules`. Do not set CORS to `*`. Use the host's secret/environment settings, not a committed file. Render free service sleep means cold starts and is not suitable when reliable availability is required.

**Persistent database (Supabase PostgreSQL):** Create a PostgreSQL project, copy its connection string into `DATABASE_URL` using SQLAlchemy's `postgresql+psycopg://` driver prefix, and use the provider's recommended SSL parameters. For example, transform `postgresql://USER:PASSWORD@HOST:PORT/DB?sslmode=require` to `postgresql+psycopg://USER:PASSWORD@HOST:PORT/DB?sslmode=require`. Keep the database password in the backend host's secret manager. Run the schema initializer above against the production database before the first API start, after taking a backup. Confirm `/api/health` returns `{"status":"ok","app":"PocketWise"}`. Never use local SQLite on an ephemeral host filesystem. Free-tier inactivity pauses and storage quotas can interrupt service; move to durable hosting and tested backups before relying on the service.

**Troubleshooting:** A browser CORS error means the exact frontend origin is missing from `CORS_ORIGINS`; include scheme and hostname, with no trailing route. A blank/failed API view usually means `VITE_API_URL` was not set at build time or the API is still waking up. A 503 from health indicates the database URL, SSL options, network access or database availability needs attention. A 401 requires signing in again because the session token is tab-scoped or expired. After changing frontend environment values, run a fresh build and redeploy. If a route returns a 404 on a static host, verify the SPA rewrite is enabled.

### Verification status and limitations

Current full verification: backend tests cover registration/login, authenticated route scoping, cross-user isolation, financial modules, reports/CSV, assistant rules and Ollama fallback, health/security headers, request size rejection and CSV formula escaping. Frontend tests cover the existing feature utilities, demo separation and PWA manifest/service-worker safeguards. The production build emits separate route and chart chunks and no chunk exceeds Vite's 500 kB warning threshold.

Limitations: offline use is intentionally limited to the static shell; no account data is available offline. Bearer tokens remain accessible to page JavaScript while a tab is open. There is no built-in distributed rate limiter or Alembic revision history. Free hosting is for evaluation only and does not guarantee persistent availability, backups or appropriate handling of sensitive financial records. No external deployment or account was created.

