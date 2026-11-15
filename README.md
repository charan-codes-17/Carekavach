# CareKavach

A senior-first, collaborative elderly care and medication management platform. CareKavach keeps the
senior at the centre while giving caretakers and family a trustworthy, privacy-respecting view of the
daily routine.

## Live Application

**Deployed URL:** https://carekavach.onrender.com

---

## Project Overview

CareKavach is a server-rendered web application for managing an elderly person's daily medication
schedule, adherence, and doctor appointments. A single care profile is shared by three roles:

- **Senior** - owns the profile, controls privacy, and can revoke members.
- **Caretaker** - helps manage medications, log doses, and record appointments.
- **Family** - read-only peace-of-mind view of adherence and upcoming appointments.

Access uses a unique **name + passcode** (no email/password needed), so seniors are not forced to
remember an email address. Every reminder is a purely logistical scheduling alert: the application
never provides medical advice, diagnoses, dosing instructions, or drug-interaction information.

---

## Features

- **Role-based shared ecosystem** across Senior, Caretaker, and Family, with per-member `can_edit`
  privileges.
- **Name + passcode authentication** using salted PBKDF2-HMAC-SHA256 hashes and constant-time
  comparison.
- **Medication schedule management** with soft deactivation (records are never hard-deleted) and a
  per-medication **private** flag hidden from the Family role.
- **Dose adherence logging** (`TAKEN` / `SKIPPED`) with atomic, deterministic slot IDs that prevent
  double-logging of the same scheduled slot.
- **Derived missed doses** computed on demand from the schedule and current time (never stored).
- **Appointment monitoring** for upcoming doctor visits, displayed in the profile timezone.
- **Immutable audit trail** of medication, dose, appointment, and member changes.
- **Proactive email reminders** for upcoming doses, overdue/escalated misses, and approaching
  appointments, dispatched from an idempotent task endpoint.
- **Gemini-assisted non-clinical pattern summaries** with a strict timeout and deterministic fallback.
- **Senior-first accessible interface** (WCAG 2.1 AA oriented).

---

## Architecture

Server-rendered Python application with a clean layering:

- **`app/routes/`** - FastAPI route handlers (auth, setup, members, medications, doses,
  appointments, audit, tasks, health) that render Jinja2 templates.
- **`app/services/`** - domain logic: auth/session signing, CSRF, rate limiting, adherence and
  derived-miss computation, escalation, email dispatch, Gemini summaries, audit recording.
- **`app/repositories/`** - a `BaseRepository` interface with two implementations:
  `MemoryRepository` (in-memory, for tests and local demos) and `FirestoreRepository` (Cloud
  Firestore). The active one is selected by the `USE_FIRESTORE` environment variable.
- **`app/models/`** - Pydantic models for profiles, members, medications, dose logs, appointments,
  audit entries, and reminder notifications.
- **`app/templates/` + `app/static/`** - Jinja2 templates and the accessible CSS design system.

A single in-process clock abstraction (`app/clock.py`) makes all time-dependent logic deterministic
and testable.

---

## Google Cloud Services Actually Used

CareKavach uses **only** the following Google Cloud services. Nothing else should be assumed.

### Firestore - durable, concurrent-safe persistence

- **Why:** the app must run as a stateless container, so persistence cannot live in process memory.
  Firestore provides a managed, scalable NoSQL store for members, medications, dose logs, and
  appointments.
- **How:** `FirestoreRepository` writes dose logs and reminder notifications using **deterministic
  document IDs** (`{medication_id}_{date}_{time}` and
  `{task_type}_{target_id}_{slot_date}_{slot_time}`) via Firestore's atomic `create()`. If the
  document already exists, Firestore raises a conflict, which the app maps to an `AlreadyExistsError`.
  This is what guarantees **no double dose-logging** and **exactly-once reminders**, even across
  concurrent requests or multiple instances.
- **Local/test mode:** the identical contract is implemented by `MemoryRepository`, which raises the
  same `AlreadyExistsError`, so behaviour is consistent without a live database.

### Gemini API (`google-genai`) - non-clinical pattern summaries

- **Why:** a short, plain-language summary of the day's schedule routine makes reminder emails easier
  to understand for seniors and family, without adding clinical content.
- **How:** `app/services/gemini_summary.py` sends **only aggregated, anonymised schedule facts**
  (counts of scheduled, taken, and overdue doses, and missed slots in the last 72 hours). No names,
  emails, or medication names are ever sent. The output is sanitised: markdown is stripped, output is
  capped, and any clinical term (e.g. "diagnos", "interaction", "dose change") causes the result to be
  discarded.
- **Timeout and fallback:** the call is wrapped in `asyncio.wait_for(..., timeout=3.0)`. On timeout,
  missing API key, network failure, or any API error, the service returns a **deterministic plain-text
  fallback** and never raises. Reminder emails always send immediately, AI content or not.

> CareKavach does **not** use Cloud Run or Cloud Scheduler. The application is containerised and
> hosted on **Render**, and the reminder task endpoint is triggered by an external HTTP scheduler.

---

## Scoring Signals Map

| Signal | What was done |
|---|---|
| **Code Quality** | Small, single-purpose modules split across `routes/`, `services/`, `repositories/`; full Python type hints; zero dead code or debug statements; `ruff check` and `ruff format` pass cleanly. |
| **Security** | Salted PBKDF2-HMAC-SHA256 passcodes with constant-time comparison; HMAC-signed session cookies; HMAC CSRF tokens on every state-changing form; login rate limiting per IP and per name; defensible security headers; Jinja2 autoescaping; the member is re-read from the database on every request (roles are never trusted from the cookie); no secrets in the repository. |
| **Efficiency** | Lean dependency set and small container footprint; deterministic in-memory adherence/derived-miss maths (no redundant database calls); fast cold-start-friendly FastAPI app; single-process design suited to a small free-tier instance. |
| **Testing** | `pytest` suite covering domain logic, boundary inputs (e.g. 59/60/61-minute overdue thresholds), double-logging prevention, rate-limit lockout, role privacy, and dashboard behaviour per role; run with a single command. |
| **Accessibility (WCAG 2.1 AA)** | 18px base font, 48px minimum touch targets, high-contrast design tokens, keyboard-navigable layouts with a persistent focus ring, skip link, labelled form fields, and text status labels. |
| **Problem Alignment** | Medication scheduling, adherence tracking, appointment monitoring, a role-based shared ecosystem (Senior/Caretaker/Family), proactive email reminders, senior-centric privacy controls, and member revocation — all built into the same care profile. |
| **Google Services Usage** | **Firestore** for durable, atomic persistence (dose-log and reminder idempotency) and the **Gemini API** for non-clinical pattern summaries with a strict timeout and deterministic fallback. |

---

## Accessibility Notes

- **18px base font size** (1.125rem) with a 1.6 line height for legibility.
- **48px minimum touch targets** on all buttons and form controls, with larger **56px** hero actions
  ("Mark as Taken" / "Skip Dose") on the senior dashboard.
- **Skip link** ("Skip to main content") as the first focusable element on every page.
- **Labelled inputs** - every form field has an associated `<label>`; the login and setup forms are
  keyboard operable with clear focus states.
- **Text status labels, never colour alone** - dose states render as explicit text such as
  "Taken at 8:15 AM", "Due at 12:00 PM", "Skipped", or "Missed - overdue".
- **Semantic landmarks** (`header`, `nav`, `main`, `footer`) and exactly one `<h1>` per page, with a
  valid `lang` attribute.
- **High-contrast design tokens** retained throughout (primary blue `#1e40af`, success `#14532d`,
  danger `#7f1d1d`) to exceed 4.5:1 and target 7:1 where feasible.

---

## Security Notes

- **Salted PBKDF2** passcode hashing (PBKDF2-HMAC-SHA256, 200,000 iterations, random per-member salt)
  with `secrets.compare_digest` constant-time verification, plus uniform dummy verification so
  non-existent names take the same time as real ones.
- **Signed session cookies** - HMAC-SHA256 signed payloads carrying only a member ID and an expiry;
  cookies are `HttpOnly` and `SameSite=Lax` (and `Secure` when `COOKIE_SECURE=true`).
- **CSRF protection** - every state-changing POST form carries an HMAC CSRF token derived from the
  session, verified in constant time.
- **Rate limiting** - failed logins are limited per client IP (first `X-Forwarded-For` value) and per
  member name (5 failures in 5 minutes).
- **Role re-read each request** - the current member is reloaded from the repository on every request
  to re-check `is_active` and `role`; revoking a member invalidates their session immediately.
- **No secrets in the repository** - all secrets are injected via environment variables; `.env` is
  git-ignored and `.env.example` lists variable names only.

---

## Known Limitations

- **In-memory rate limiter per instance** - the sliding-window limiter state lives in process memory,
  so limits apply per running instance and reset on restart.
- **Stateless cookie sessions** - sessions are signed but not stored server-side, so there is no
  central session revocation list beyond the live `is_active` check; logout simply clears the cookie.
- **Free-tier cold starts** - the free hosting tier spins down when idle, so the first request after
  inactivity may be slow to respond.
- **Email backend may log instead of send** - when no SMTP/Resend credentials are configured (or a
  delivery attempt fails), emails are rendered and written to the application log rather than
  delivered, so the app never crashes on email problems.
- **Hosted on Render, not Cloud Run** - the application is deployed as a Docker web service on
  Render; the reminder endpoint must be triggered by an external HTTP scheduler because the app does
  not provision a scheduler itself.

---

## Local Setup

```powershell
# 1. Clone and enter the project
git clone <your-repository-url> CareKavach
cd CareKavach

# 2. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate         # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
Copy-Item .env.example .env
# Then edit .env and set at least SESSION_SECRET (32+ characters) and SETUP_CODE.

# 5. Run the application
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8080
```

By default the app runs with the in-memory repository (`USE_FIRESTORE=false`). To use Cloud Firestore,
set `USE_FIRESTORE=true` and provide `GOOGLE_CLOUD_PROJECT` and credentials. After starting, visit
`/setup` with your `SETUP_CODE` to bootstrap the care profile and the Senior account.

---

## Running the Tests

```powershell
pytest
```

---

## How Antigravity Was Used

CareKavach was built inside the **Antigravity** agentic development environment, which was used
end-to-end rather than as a plain editor:

- **Planning** - Antigravity helped break the challenge down into phased, traceable subphases across
  the domain layers, keeping each change reviewable.
- **Implementation** - it scaffolded and edited the FastAPI routes, repository interface with a
  memory fake and a Firestore implementation, the accessible CSS design system, and the Jinja2
  templates.
- **Testing and verification** - it wrote and ran the `pytest` suite (including boundary and
  privacy cases), and ran `ruff check` and `ruff format` to keep the codebase clean.
- **Iteration** - the agentic loop of propose, run, and inspect outputs made it practical to verify
  each change against the tests and the accessibility requirements before moving on.
