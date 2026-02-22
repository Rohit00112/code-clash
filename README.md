# Code Clash Platform

A self-hosted competitive coding contest platform built for live programming events. Participants solve coding challenges through a VS Code-like browser IDE with real-time code execution, auto-grading, and support for 6 programming languages.

Built for **Itahari International College — Creative Clash 2026**.

## Features

- **VS Code-like IDE** — Monaco Editor with syntax highlighting, autocomplete, bracket matching
- **6 Languages** — Python, JavaScript, Java, C, C++, C#
- **Two coding styles** — Function-based (`def solution(n): return n*2`) or input-based (`n = int(input()); print(n*2)`)
- **Integrated Terminal** — Install pip packages, run/submit from terminal
- **Keyboard Shortcuts** — `Ctrl+Enter` to run, `Ctrl+Shift+Enter` to submit
- **Auto-save Drafts** — Code is saved every 2 seconds
- **Async Judging Queue** — submissions are queued and processed by a background worker
- **Refresh Token Rotation** — secure session renewal with token-family revocation
- **Admin Dashboard** — Upload challenges, bulk import users, export Excel results
- **Optimized for 50+ concurrent users** — Connection pooling, execution semaphore, GZip compression
- **Operational Telemetry** — `/health` readiness checks and `/metrics` for Prometheus

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+ / FastAPI / SQLAlchemy / PostgreSQL |
| Frontend | React 18 / TypeScript / Vite / Monaco Editor |
| Auth | JWT (HS256) + bcrypt |
| Code Execution | Sandboxed subprocess with timeout + memory limits |

## Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **PostgreSQL** (running, with a database created)
- **Git**
- For C/C++: `gcc`/`g++` installed
- For Java: `javac` + `java` installed
- For C#: `csc` installed (optional)

## Docker Deployment (Full Stack)

Run frontend + backend + PostgreSQL with one command.

### 1. Configure Docker env

```bash
cp .env.docker.example .env.docker
```

Edit `.env.docker` and set strong values for:
- `POSTGRES_PASSWORD`
- `SECRET_KEY` (generate with `openssl rand -hex 32`)
- `ADMIN_PASSWORD`
- `CORS_ORIGINS` (set your server/domain origin)

### 2. Build and start

```bash
docker compose --env-file .env.docker up -d --build
```

### 3. Verify

```bash
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs -f backend
```

Open `http://YOUR_SERVER_IP:3000` (or your configured `FRONTEND_PORT`).

### 4. Stop

```bash
docker compose --env-file .env.docker down
```

Notes:
- Database and app data persist in Docker volumes (`postgres_data`, `questions_data`, `testcases_data`, etc.).
- Backend runs migrations automatically on startup.
- Queue worker runs embedded in backend (`RUN_EMBEDDED_WORKER=true`).

## Quick Start

### 1. Clone

```bash
git clone https://github.com/rameshsapkota900/TEST.git
cd TEST
```

### 2. Setup Database

Create a PostgreSQL database:

```sql
CREATE DATABASE code;
```

### 3. Backend

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate
# Windows (CMD):
venv\Scripts\activate.bat
# Windows (PowerShell):
venv\Scripts\Activate.ps1
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — set your DATABASE_URL:
#   DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/code

# Apply DB migrations (when DB_INIT_MODE=migrate)
alembic upgrade head
```

### 4. Frontend

```bash
cd frontend
npm install
```

### 5. Run

Open **three terminals**:

**Terminal 1 — Backend API:**
```bash
cd backend
venv\Scripts\activate.bat   # or source venv/bin/activate
python run.py
```
Backend starts at `http://localhost:8000`

**Terminal 2 — Worker:**
```bash
cd backend
venv\Scripts\activate.bat   # or source venv/bin/activate
python run_worker.py
```

**Terminal 3 — Frontend:**
```bash
cd frontend
npm run dev
```
Frontend starts at `http://localhost:3000`

### 6. Login

Open `http://localhost:3000` in your browser.

- **Admin:** `admin` / `admin123` (change in `.env`)
- **Participants:** Created by admin via bulk import

## Admin Guide

### Upload Challenges

1. Go to **Challenges** tab in admin dashboard
2. Click **Upload Challenge** — provide:
   - **Title** (optional, e.g. "Two Sum")
   - **PDF file** — the problem statement
   - **JSON file** — the test cases
3. Challenges appear immediately for all participants

### Test Case JSON Format

```json
{
  "title": "Find All Anagrams",
  "function_name": "find_anagrams",
  "test_cases": [
    {
      "id": 1,
      "input": ["listen", ["enlists", "google", "inlets", "banana"]],
      "output": ["inlets"],
      "is_sample": true
    },
    {
      "id": 2,
      "input": ["rat", ["art", "tar", "rat", "car"]],
      "output": ["art", "tar", "rat"],
      "is_sample": false
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `function_name` | The function participants must implement |
| `input` | Array of arguments (spread as positional args to the function, or piped as stdin lines) |
| `output` | Expected return value (compared as JSON) or expected printed output (compared as string) |
| `is_sample: true` | Visible to participants during "Run Code" |
| `is_sample: false` | Hidden — only used during "Submit" for scoring |

Backward compatibility:
- Legacy `sample` is accepted and normalized to `is_sample`.

Optional testcase metadata:
- `name`: short testcase label
- `weight`: numeric weight for scoring extensions
- `timeout_ms`: per-test timeout override (future extension)

### How Participants Can Write Code

Participants can use **either** approach — the platform auto-detects:

**Option A — Function style (template):**
```python
def find_anagrams(word, candidates):
    return [c for c in candidates if sorted(c) == sorted(word)]
```

**Option B — input() style:**
```python
word = input()
n = int(input())
candidates = [input() for _ in range(n)]
result = [c for c in candidates if sorted(c) == sorted(word)]
print(result)
```

Both styles work for Run and Submit. The test case `input` values are piped as stdin lines.

### Scoring

```
score = (passed_test_cases / total_test_cases) * 100
```

If a challenge has 7 test cases and a participant passes 5, their score is `71`.

### Async Submission Lifecycle

`POST /submissions/submit` now queues submissions and returns immediately:

```json
{
  "success": true,
  "submission_id": 42,
  "status": "queued",
  "message": "Submission queued for evaluation"
}
```

Status values: `queued`, `running`, `completed`, `failed`, `timeout`.

### Manage Users

1. Go to **Manage** tab
2. Enter usernames (comma or newline separated)
3. Click **Import** — passwords are auto-generated as `username@123`

### Export Results

Click **Export Excel** to download a spreadsheet with:
- Leaderboard with per-question scores
- Detailed submissions list
- Event statistics

## Supported Languages

| Language | Auto Test Harness | Input Style | Compiler/Runtime |
|----------|:-:|:-:|-----------------|
| Python | Yes | Yes | `python` |
| JavaScript | Yes | Yes | `node` |
| Java | — | Yes | `javac` + `java` |
| C | — | Yes | `gcc` |
| C++ | — | Yes | `g++` |
| C# | — | Yes | `csc` |

**Python & JavaScript** — participants can write just the function or use `input()`. The harness auto-detects.

**Java, C, C++, C#** — participants write their own `main()` and handle I/O via stdin/stdout.

## Project Structure

```
code-clash/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # Routes: auth, admin, challenges, submissions, drafts, terminal
│   │   ├── core/            # Database, security (JWT/bcrypt), exceptions
│   │   ├── models/          # SQLAlchemy: User, Submission, TestResult, CodeDraft
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   └── services/        # Business logic:
│   │       ├── code_executor.py      # Sandboxed code execution + stdin piping
│   │       ├── challenge_loader.py   # Dynamic PDF/JSON loading with cache
│   │       ├── submission_service.py # Grading + scoring
│   │       ├── excel_service.py      # Excel export
│   │       └── user_service.py       # User management
│   ├── .env.example         # Environment template
│   ├── requirements.txt
│   └── run.py               # Entry point
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── VSCodeIDE.tsx    # Monaco editor + terminal + keyboard shortcuts
│   │   │   └── VSCodeIDE.css
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── AdminDashboard.tsx
│   │   │   └── ParticipantDashboard.tsx
│   │   └── services/
│   │       └── api.ts           # Axios client with JWT interceptor
│   └── package.json
├── questions/               # Problem PDFs (question1.pdf, question2.pdf, ...)
├── testcases/               # Test case JSONs (question1.json, question2.json, ...)
├── .gitignore
└── README.md
```

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and configure:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | PostgreSQL connection string |
| `SECRET_KEY` | — | JWT signing key (use `openssl rand -hex 32`) |
| `DEBUG` | `False` | Enable debug mode |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `WORKERS` | `4` | Uvicorn workers (production) |
| `CODE_EXECUTION_TIMEOUT` | `5` | Max seconds per code execution |
| `MAX_CODE_SIZE` | `51200` | Max code size in bytes |
| `DB_INIT_MODE` | `migrate` | DB startup mode: `migrate`, `create_all`, `off` |
| `ENABLE_TERMINAL_INSTALLS` | `false` | Allow participant `pip install` |
| `RUN_EMBEDDED_WORKER` | `true` | Start worker thread inside API process |
| `ADMIN_USERNAME` | `admin` | Default admin username |
| `ADMIN_PASSWORD` | `change_this_password_immediately` | Default admin password |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed frontend origins |

## Security Notes

- In production, startup fails if insecure defaults are used for `SECRET_KEY` or `ADMIN_PASSWORD`.
- Refresh tokens are rotated on every refresh call and tracked by token family.
- Terminal installs are allowlisted and quota-limited.

## Developer Commands

```bash
# Run migrations (required when DB_INIT_MODE=migrate)
cd backend
alembic upgrade head

# API server
python run.py

# Worker (if not using embedded worker)
python run_worker.py

# Backend tests
python -m pytest -q

# Frontend checks
cd ../frontend
npm run typecheck
npm run build
```

## LAN Deployment (Contest Day)

To let participants on the same network access the platform:

1. Set in `backend/.env`:
   ```
   DEBUG=False
   WORKERS=8
   CORS_ORIGINS=["http://YOUR_IP:3000","http://localhost:3000"]
   ```

2. Set in `frontend/.env`:
   ```
   VITE_API_BASE_URL=http://YOUR_IP:8000/api/v1
   ```

3. Start backend + worker + frontend:
   ```bash
   cd backend && python run.py
   cd backend && python run_worker.py
   cd frontend && npx vite --host
   ```

4. Participants open `http://YOUR_IP:3000`.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | Login (access + refresh token) |
| POST | `/api/v1/auth/refresh` | Rotate refresh token |
| GET | `/api/v1/challenges` | List challenges |
| GET | `/api/v1/challenges/{id}/pdf` | Download problem PDF |
| POST | `/api/v1/submissions/test-run` | Run code with structured output |
| POST | `/api/v1/submissions/submit` | Queue submission for grading |
| GET | `/api/v1/submissions/{id}` | Submission status/details |
| POST | `/api/v1/drafts/save` | Auto-save draft |
| POST | `/api/v1/terminal/execute` | Controlled terminal installs |
| GET | `/api/v1/admin/statistics` | Platform stats |
| POST | `/api/v1/admin/bulk-import` | Bulk create users |
| POST | `/api/v1/admin/challenges/validate` | Validate testcase JSON |
| POST | `/api/v1/admin/challenges/upload` | Upload challenge |
| GET | `/api/v1/admin/audit-events` | Audit trail |
| GET | `/health` | Readiness/health details |
| GET | `/metrics` | Prometheus metrics |

Full API docs available at `http://localhost:8000/api/docs` when `DEBUG=True`.

## License

MIT
