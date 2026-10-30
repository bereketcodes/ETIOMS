# ETIOMS

**AI-Powered Ethiopian Tender Intelligence and Opportunity Management System**

ETIOMS helps Ethiopian companies find procurement tenders, check whether they qualify, and track the bids they decide to pursue. A company describes itself once (sectors, regions, experience, certifications, past projects). The system then scores every tender against that profile, runs a preliminary compliance check, answers questions about a tender's text, and follows each bid from discovery to award.

> AI output is advisory. Always verify against the official tender notice.

## Features

- **Tender ingestion:** upload a PDF/TXT or paste a notice; Gemini extracts title, entity, sector, region, deadline, budget and requirements.
- **Search and filters:** by keyword, sector, region, status and days until deadline.
- **Match score (0-100):** 70 points rule-based (sector 25, region 20, experience 25) + 30 points AI fit, with a per-factor breakdown. 60 or above is "qualified".
- **Compliance audit:** checks trade license, tax clearance and VAT/TIN, then gives BID / NO-BID / CONDITIONAL with risks.
- **Tender Q&A:** questions answered only from the tender text, with citations or a clear "not available".
- **Opportunity pipeline:** Discovered, Interested, Analyzing, Preparing, Submitted, Awarded / Not Awarded, with notes.
- **Comparison:** side by side, 2 to 5 tenders.
- **Alerts:** in-app notification for tenders closing within 7 days.
- **Teams:** companies with roles (Organization Admin, Team Member), single-use 24-hour invitation codes, and an admin console.

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | Next.js 16, React 19, TypeScript |
| Backend | Python, FastAPI, Uvicorn, Pydantic v2 |
| Database | SQLAlchemy; SQLite by default, PostgreSQL via `DATABASE_URL` |
| Auth | JWT (HS256, 30 min), PBKDF2-SHA256 password hashing |
| AI | Google Gemini (`gemini-3.6-flash`, `text-embedding-004`) |
| Documents | pypdf |

## Getting started

Requirements: Python 3.10+/ python 3.13-, Node.js 20+, a Google Gemini API key.

```bash
git clone -b finish-mvp https://github.com/bereketcodes/ETIOMS.git
cd ETIOMS

python -m venv venv
venv\Scripts\activate            # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt

copy .env.example .env           # Linux/macOS: cp .env.example .env
```

Edit `.env`:

```env
JWT_SECRET_KEY=<at least 32 random characters>
GEMINI_API_KEY=<your Gemini API key>
FRONTEND_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
# DATABASE_URL=sqlite:///./etioms.db
```

Generate a secret with: `python -c "import secrets; print(secrets.token_urlsafe(48))"`

Run the backend (from the repository root):

```bash
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Run the frontend (second terminal):

```bash
cd frontend
npm install
npm run dev
```

On Windows you can start both with `start_etioms.bat`.

| What | Address |
| --- | --- |
| Web app | http://localhost:3000 |
| API docs (Swagger) | http://127.0.0.1:8000/docs |
| Health check | http://127.0.0.1:8000/health |

The frontend reads the API address from `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`).

### Demo account

The bundled database includes a demo company:

- Email: `admin@afrotech.et`
- Password: `DemoPassword123!`

## How to use it

1. Register a company (or join one with an invitation code).
2. Fill in the **Company profile**.
3. **Upload a tender** (PDF, TXT or pasted text).
4. Open the **ranked list** and click a tender for the score breakdown, compliance audit and Q&A.
5. Save tenders, compare them, and move them through the **pipeline**.
6. Use the **Admin console** to see the team and create invitation codes.

## Project structure

```
backend/app/
  main.py          app setup, CORS, routers, /health
  database.py      engine and session
  security.py      password hashing and JWT
  models/          database tables
  schemas/         request/response models
  routers/         auth, tenders, profile, intelligence, opportunities, notifications, admin
  services/        ai, ingestion, pdf, matching, compliance, rag, embedding, proposal
frontend/app/      Next.js pages (views live in etioms-app.tsx)
docs/              project documentation
uploads/           uploaded tender files
start_etioms.bat   Windows launcher
```

## API overview

29 endpoints under `/api/auth`, `/api/tenders`, `/api/profile`, `/api/intelligence`, `/api/opportunities`, `/api/notifications` and `/api/admin`, plus `/health`. All require a Bearer token except `/health`, register and login. See `/docs` for the full interactive list.

## Known limitations

- Tender Q&A sends the document text (first 40,000 characters) to the model; it does not use chunked vector retrieval.
- Tenders are a shared catalogue, and any signed-in user can add them. Admin checks are not yet strict.
- Cached match scores are not cleared when the profile changes (use "Force AI refresh").
- AI features need `GEMINI_API_KEY`; without it, ingestion and compliance audit return an error.
- There is no automated test suite yet.

## Documentation

Full project documentation: see the `docs/` folder.
