# IMPLEMENTATION PLAN: CareKavach

A senior-first, collaborative elderly care and medication management platform designed for Cloud Run, Firestore, Cloud Scheduler, and the Gemini API.

---

## Plan Overview & Constraints

- **Builder**: Solo developer.
- **Time Available**: ~5 hours of build & test time remaining (10:15 AM to 3:30 PM IST, submission buffer to 4:15 PM IST).
- **Target Pipeline Smoke Deploy**: Cloud Run live skeleton with `/health/db` verified by ~10:50 AM IST (end of Phase 1).
- **Target Core Redeploy + Scheduler**: Verified by ~12:30 PM IST (end of Phase 4).
- **Final Submission**: Prior to 4:15 PM IST (window closes 5:00 PM IST).
- **Guiding Rule**: In any conflict between documents, `docs/decisions.md` (and its Amendments section) governs. All work adheres to `AGENTS.md`.

---

## 1. Requirement Traceability Matrix

Every requirement from `docs/problem_statement.md` is directly mapped to its delivery subphase:

| Requirement ID | Problem Statement Requirement | Delivery Subphase | Verification Method |
|---|---|---|---|
| **REQ-1** | Daily medication management (view, add, edit, deactivate schedules) | **3.1** | Unit & route tests for medication CRUD, timezone slot handling, soft-deactivation. |
| **REQ-2** | Adherence tracking (logging doses taken/skipped, derived misses) | **3.2** | Deterministic document ID atomic creation tests, double-logging prevention, derived miss logic. |
| **REQ-3** | Private medication controls (hidden from family role & family emails) | **3.1, 5.2** | Role-based filtering tests ensuring family members cannot view private items in UI or emails. |
| **REQ-4** | Monitor upcoming doctor appointments | **3.3** | Appointment listing and sorting tests with date boundary checks. |
| **REQ-5** | Shared ecosystem (Senior, Caretaker, Family roles with `can_edit`) | **2.0, 2.3, 7.3** | RBAC session checks, `can_edit` permission tests, and role-tailored dashboard views. |
| **REQ-6** | Secure passcode-based profile access (name + passcode) | **2.1, 2.2** | Salted PBKDF2 hash with constant-time comparison, per-IP and per-name rate limiting. |
| **REQ-7** | Member revocation by Senior | **2.3** | Senior revocation tests ensuring revoked passcodes/sessions are rejected immediately. |
| **REQ-8** | Audit trail of changes and dose logging | **3.3** | Immutable audit log verification for dose logs, profile setup, and schedule edits. |
| **REQ-9** | Proactive email reminders for upcoming doses | **5.1, 5.3** | End-to-end task execution test checking SMTP dispatch for impending slots. |
| **REQ-10** | Proactive email reminders for missed medications & escalation | **5.2, 5.3** | Deterministic escalation rule test (>60 min overdue or 2 derived misses in 3 days). |
| **REQ-11** | Proactive email reminders for medical appointments | **5.1, 5.3** | Appointment alert window test (24h and 2h notification triggers). |
| **REQ-12** | Gemini non-clinical pattern summary (facts only, no names/emails) | **6.1, 6.2** | Mocked Gemini API test, `GEMINI_MODEL` env, 3s timeout, fail-safe plain fallback. |
| **REQ-13** | Senior-first accessibility (WCAG 2.1 AA tokens in 1.3, polish in 7) | **1.3, 7.1, 7.2** | 18px base text, 48px hit targets, 7:1 contrast, keyboard navigation, Lighthouse check. |
| **REQ-14** | Zero medical advice / clinical boundary enforcement | **6.1, 8.2** | Prompt assertion tests verifying zero diagnostic or clinical dosing guidance. |
| **REQ-15** | Cloud Run deployment, Firestore integration & public health | **1.3, 1.4, 4.1–4.3** | Live public Cloud Run URL reachable in incognito mode with `/health` and `/health/db`. |
| **REQ-16** | System bootstrap & profile initialization | **2.0** | `/setup` endpoint guarded by `SETUP_CODE`, disabled after single profile creation. |
| **REQ-17** | Final submission compliance & artifact delivery | **9.4** | Clean git single branch verification, size < 10 MB, LinkedIn post, submission form. |

---

## 2. Phase-by-Phase Plan

```
Phase 1: Foundation & Pipeline Smoke Deploy (10:15 - 10:55)
   ├── 1.1 Config, Dependencies & Freezing (install then freeze)
   ├── 1.2 Repository Interface, Memory Fake (AlreadyExists) & Firestore
   ├── 1.3 FastAPI Skeleton, Base CSS Tokens & Dockerfile ($PORT)
   └── 1.4 PIPELINE SMOKE DEPLOY: Cloud Run Live Skeleton & /health/db Check (~10:50)
Phase 2: Bootstrap, Auth & Role Access (10:55 - 11:30)
   ├── 2.0 Profile Bootstrap (/setup guarded by SETUP_CODE, member attributes)
   ├── 2.1 Salted Hashing (secrets.compare_digest) & Session Cookies
   ├── 2.2 Rate Limiting (per-IP & per-name) & Auth Handlers
   └── 2.3 Role Authorization (can_edit) & Member Revocation
Phase 3: Core Healthcare Domain (11:30 - 12:15)
   ├── 3.1 Medication CRUD, Deactivation & Privacy Controls
   ├── 3.2 Dose Adherence (Atomic deterministic IDs, Derived Misses)
   └── 3.3 Appointments & Audit Logging
Phase 4: CORE REDEPLOY & CLOUD SCHEDULER (12:15 - 12:45) [MILESTONE: Live System Active]
   ├── 4.1 Cloud Run Redeploy with Production Env Vars
   ├── 4.2 Cloud Scheduler Setup & Task Triggering
   └── 4.3 Incognito Live Walkthrough Verification
Phase 5: Reminders & Proactive Alerts (12:45 - 13:20)
   ├── 5.1 SMTP Email Notification Dispatcher (Log Fallback)
   ├── 5.2 Deterministic Escalation Engine (Derived Miss Counting)
   └── 5.3 Idempotent /tasks/run-reminders (Deterministic Keys)
Phase 6: Gemini Intelligence Summary (13:20 - 13:45)
   ├── 6.1 google-genai Integration (Aggregated facts only, no names/emails)
   └── 6.2 3s Timeout, Graceful Fallback & Medical Boundary
Phase 7: Senior UI Polish & Accessibility Check (13:45 - 14:15)
   ├── 7.1 Senior Dashboard Polish & Visual Action Cards
   ├── 7.2 Keyboard Navigation & ARIA Landmarks
   └── 7.3 Caretaker/Family Portals & Manual Lighthouse Audit
Phase 8: Testing & Security Hardening (14:15 - 14:45)
   ├── 8.1 Automated Pytest Edge Cases & Failure Paths
   ├── 8.2 Security Headers, XSS Check & Secret Scan
   └── 8.3 Ruff Linting & Formatting Pass
Phase 9: Final Submission Deliverables (14:45 - 15:30, buffer to 4:15 PM)
   ├── 9.1 Comprehensive README with Signal & Google Services Map
   ├── 9.2 LinkedIn Post Draft
   ├── 9.3 Rulebook Checklist Audit & Live Cloud Run Health Check
   └── 9.4 Final Submission: Commit, Push main, Submit Form by 4:15 PM
```

---

### Phase 1: Foundation & Pipeline Smoke Deploy
**Estimated Duration**: 40 minutes (10:15 – 10:55)  
**Objective**: Build a clean, typed foundation with dependency freezing, dual-mode repository (Memory with `AlreadyExists` + Firestore), base layout with senior CSS tokens, and deploy a live smoke pipeline to Cloud Run with `/health/db` by ~10:50 AM IST.

#### Subphase 1.1: Project Dependencies & Typed Settings
- **Goal**: Install minimal dependencies, freeze actual resolved versions, and implement typed settings.
- **Files to Create/Change**:
  - `requirements.txt`
  - `app/config.py`
- **Detailed Tasks**:
  - Install dependencies into environment, then freeze actual resolved versions to `requirements.txt` (do not invent version numbers): `fastapi`, `uvicorn`, `jinja2`, `python-multipart`, `pydantic`, `pydantic-settings`, `google-genai`, `google-cloud-firestore`, `pytest`, `httpx`, `ruff`.
  - Implement `Settings` class in `app/config.py` loading:
    - `GEMINI_API_KEY`, `GEMINI_MODEL` (default: `gemini-2.5-flash` or current stable).
    - `SETUP_CODE` (secret string to unlock `/setup`).
    - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`.
    - `SCHEDULER_SECRET`, `SESSION_SECRET`, `COOKIE_SECURE` (bool, default False in local dev, True in prod).
    - `GOOGLE_CLOUD_PROJECT`, `PORT` (default 8080), `USE_FIRESTORE` (bool flag).
    - `DEFAULT_TIMEZONE` (default: `Asia/Kolkata`).
- **Acceptance Criteria**:
  - `requirements.txt` contains real frozen versions.
  - `app.config.get_settings()` validates environment inputs without hardcoded secrets.
- **Tests Required**:
  - `tests/test_config.py`: Test settings loading with default fallbacks and custom environment variables.
- **Scoring Signals Supported**: Code Quality, Security, Efficiency.
- **Time Estimate**: 10 minutes.

#### Subphase 1.2: Repository Interface, In-Memory Fake & Firestore Repository
- **Goal**: Create abstract repository contract, an in-memory implementation that raises `AlreadyExists` for duplicate deterministic IDs, and a Firestore implementation with Clock dependency.
- **Files to Create/Change**:
  - `app/repositories/base.py`
  - `app/repositories/memory.py`
  - `app/repositories/firestore.py`
  - `app/services/clock.py`
- **Detailed Tasks**:
  - Implement injectable `Clock` protocol with `get_current_time()` returning timezone-aware UTC datetime, convertible to wall-clock `Asia/Kolkata` using `zoneinfo.ZoneInfo`.
  - Define `BaseRepository` ABC with async methods:
    - Profile: `get_profile(profile_id)`, `create_profile(profile)`.
    - Members: `get_member_by_id(profile_id, member_id)`, `get_member_by_name(profile_id, name)` (names unique per profile), `create_member(member)`, `update_member(member)`, `list_members(profile_id)`.
    - Medications: `create_medication(med)`, `get_medication(profile_id, med_id)`, `update_medication(med)`, `list_medications(profile_id, active_only=True)`.
    - Dose Logs: `create_dose_log(dose_log)` (deterministic ID `{medication_id}_{date}_{time}`), `list_dose_logs(profile_id, start_date, end_date)`.
    - Appointments: `create_appointment(appt)`, `list_appointments(profile_id)`.
    - Notifications: `create_reminder_notification(notification_key)` (deterministic ID), `has_reminder_been_sent(notification_key)`.
    - Audit Logs: `create_audit_entry(audit_entry)`, `list_audit_entries(profile_id)`.
    - Health check: `ping_db() -> bool`.
  - In `MemoryRepository`: implement storage dicts; when writing dose log or notification key, if key exists raise custom `AlreadyExistsError`.
  - In `FirestoreRepository`: use `collection.document(id).create(data)` which natively raises `google.cloud.exceptions.Conflict` / `AlreadyExists`.
- **Acceptance Criteria**:
  - `get_member_by_name` replaces old hash lookup.
  - Duplicate writes to same dose slot or notification key fail with `AlreadyExistsError`.
- **Tests Required**:
  - `tests/test_repository.py`: Verify CRUD contract against `MemoryRepository`, including `AlreadyExistsError` on duplicate deterministic IDs.
- **Scoring Signals Supported**: Code Quality, Testing, Efficiency, Google Services Usage.
- **Time Estimate**: 12 minutes.

#### Subphase 1.3: FastAPI Skeleton, Senior CSS Tokens & Dockerfile
- **Goal**: Implement FastAPI app skeleton, `/health` and `/health/db` routes, senior-first base CSS tokens (18px font, 48px targets, 7:1 contrast), and Cloud Run Dockerfile.
- **Files to Create/Change**:
  - `app/main.py`
  - `app/routes/health.py`
  - `app/templates/base.html`
  - `app/static/css/styles.css`
  - `Dockerfile`
  - `.dockerignore`
- **Detailed Tasks**:
  - Implement FastAPI initialization with lifespan management, dependency injection for repository and clock.
  - Implement GET `/health` returning `{"status": "healthy"}`.
  - Implement GET `/health/db` performing a real read/write check against the repository `ping_db()`.
  - Build `app/templates/base.html` and `app/static/css/styles.css` with fundamental senior-first tokens:
    - 18px base typography (`font-size: 1.125rem`, `line-height: 1.6`).
    - Minimum 48x48px hit areas on all buttons and form controls.
    - High contrast text (`#0f172a` on `#f8fafc` background; `#1e40af` buttons with `#ffffff` text, ratio > 7:1).
    - Persistent focus ring (`outline: 3px solid #2563eb; outline-offset: 2px;`).
    - Standard skip link (`<a href="#main-content" class="skip-link">Skip to main content</a>`) and semantic `<header>`, `<main id="main-content">`, `<footer>`.
  - Write multi-stage `Dockerfile` based on `python:3.12-slim`:
    - Listen on dynamic `$PORT` (default 8080) on `0.0.0.0`.
    - Non-root user execution for security.
- **Acceptance Criteria**:
  - `GET /health` and `GET /health/db` return 200 OK.
  - `base.html` renders with 18px typography, 48px touch targets, and skip link.
- **Tests Required**:
  - `tests/test_health.py`: Test `/health` and `/health/db` response status and JSON payload.
- **Scoring Signals Supported**: Code Quality, Accessibility, Google Services Usage.
- **Time Estimate**: 10 minutes.

#### Subphase 1.4: Pipeline Smoke Deploy to Cloud Run (~10:50 AM)
- **Goal**: Deploy Phase 1 skeleton to Cloud Run early and verify live `/health` and `/health/db` over HTTPS.
- **Files to Create/Change**:
  - Deployment logs / Cloud Run service notes
- **Detailed Tasks**:
  - Deploy to Cloud Run using `gcloud run deploy carekavach --source . --region asia-south1 --allow-unauthenticated`.
  - Pass initial environment variables (`GOOGLE_CLOUD_PROJECT`, `USE_FIRESTORE=true`, `SETUP_CODE`).
  - Test the public deployed URL in an incognito window:
    - `https://<cloud-run-url>/health`
    - `https://<cloud-run-url>/health/db` (verifies live Cloud Run $\leftrightarrow$ Firestore connectivity).
- **Acceptance Criteria**:
  - Live Cloud Run URL is active, reachable publicly without login, and `/health/db` returns status 200 OK.
- **Tests Required**:
  - Public HTTP smoke test via `curl` and incognito browser.
- **Scoring Signals Supported**: Google Services Usage, Security, Efficiency.
- **Time Estimate**: 8 minutes.

---

### Phase 2: Bootstrap, Auth and Roles
**Estimated Duration**: 35 minutes (10:55 – 11:30)  
**Objective**: Build profile bootstrap (`/setup`), member identity with `can_edit`, secure salted PBKDF2 authentication with constant-time comparison, rate limiting, and member revocation.

#### Subphase 2.0: Single Profile Bootstrap (`/setup`)
- **Goal**: Create one-time setup endpoint guarded by `SETUP_CODE` to initialize the care profile and the Senior.
- **Files to Create/Change**:
  - `app/routes/setup.py`
  - `app/models/profile.py`
  - `app/models/member.py`
  - `app/templates/setup.html`
- **Detailed Tasks**:
  - Define `CareProfile` model: `id` (e.g. `default_profile`), `senior_name`, `timezone` (defaults to `Asia/Kolkata`), `created_at`.
  - Define `Member` model: `id`, `profile_id`, `name` (unique per profile), `email` (optional, validated with Pydantic `EmailStr`), `role` (`SENIOR`, `CARETAKER`, `FAMILY`), `can_edit` (bool: True for Senior; defaults True for Caretaker, False for Family), `passcode_salt`, `passcode_hash`, `is_active` (bool), `created_at`.
  - Implement GET `/setup` and POST `/setup`:
    - Require `setup_code` matching `settings.SETUP_CODE`.
    - Check if profile already exists. If yes, disable endpoint and redirect to `/login` with an informational message.
    - On POST, create the care profile and the initial Senior member with hashed passcode.
- **Acceptance Criteria**:
  - `/setup` successfully creates the profile and senior member with valid `SETUP_CODE`.
  - Once a profile exists, `/setup` is completely disabled.
- **Tests Required**:
  - `tests/test_setup.py`: Test profile bootstrap with correct/incorrect setup code, and ensure disabling after initial setup.
- **Scoring Signals Supported**: Security, Problem Alignment, Code Quality.
- **Time Estimate**: 10 minutes.

#### Subphase 2.1: Salted Passcode Hashing & Secure Session Cookies
- **Goal**: Implement PBKDF2 passcode hashing, constant-time comparison (`secrets.compare_digest`), and tamper-proof session cookies.
- **Files to Create/Change**:
  - `app/services/auth.py`
  - `app/dependencies.py`
- **Detailed Tasks**:
  - Implement `hash_passcode(passcode: str, salt: str) -> str` using `hashlib.pbkdf2_hmac('sha256', ...)`.
  - Implement `verify_passcode(passcode: str, salt: str, expected_hash: str) -> bool` using `secrets.compare_digest`. Passcode minimum length: 6 characters.
  - Implement signed session cookie generation and decoding using HMAC-SHA256 with timestamp expiry (e.g. 12 hours).
  - Security amendment: Cookie stores only `member_id` and `profile_id`. The dependency `get_current_active_member` **re-reads the member from the repository on every request** to check `is_active` and `role`. Never trust the role in the cookie.
  - Cookie security: set `HttpOnly=True`, `SameSite=Lax`, `Secure=settings.COOKIE_SECURE`.
- **Acceptance Criteria**:
  - Constant-time comparison prevents timing attacks.
  - Revoking a member immediately invalidates their active cookie on the next request.
- **Tests Required**:
  - `tests/test_auth_service.py`: Verify PBKDF2 hashing, constant-time verification, session signing, expiration, and database re-read on dependency.
- **Scoring Signals Supported**: Security, Code Quality.
- **Time Estimate**: 10 minutes.

#### Subphase 2.2: Rate Limiting & Auth Endpoints (Name + Passcode)
- **Goal**: Implement login page, rate limiting per IP and per name, and generic error messages.
- **Files to Create/Change**:
  - `app/routes/auth.py`
  - `app/services/rate_limiter.py`
  - `app/templates/login.html`
- **Detailed Tasks**:
  - Implement dual rate limiter:
    - Limit failed attempts per IP (extract first IP from `X-Forwarded-For` header, falling back to `request.client.host`).
    - Limit failed attempts per member name.
    - Threshold: 5 failed attempts in 5 minutes triggers HTTP 429.
  - GET `/login`: Render login form with Senior-accessible large name and passcode inputs.
  - POST `/login`:
    - Lookup member by `get_member_by_name(profile_id, name)`.
    - If member not found or invalid passcode, return generic error: *"Invalid name or passcode."* (never leak whether the name exists).
    - If valid, issue signed session cookie and redirect to dashboard.
  - GET `/logout`: Clear cookie and redirect to `/login`.
- **Acceptance Criteria**:
  - Successful login sets signed cookie.
  - Generic error message on failure.
  - 5 invalid attempts lock out IP and name.
- **Tests Required**:
  - `tests/test_auth_routes.py`: Test successful login, wrong passcode, non-existent name, rate limiting per IP and per name.
- **Scoring Signals Supported**: Security, Problem Alignment, Accessibility.
- **Time Estimate**: 8 minutes.

#### Subphase 2.3: Role Permissions, `can_edit` & Member Revocation
- **Goal**: Implement member management, `can_edit` flag enforcement, and Senior revocation.
- **Files to Create/Change**:
  - `app/routes/members.py`
  - `app/templates/members.html`
- **Detailed Tasks**:
  - GET `/members`: List all authorized members in the care profile.
  - POST `/members/invite` (Senior only): Create new member with name, role (`CARETAKER` or `FAMILY`), optional email, and `can_edit` (defaults True for Caretaker, False for Family, but editable by Senior).
  - POST `/members/{member_id}/revoke` (Senior only): Set `is_active = False`.
  - Enforce `can_edit` dependency on routes that mutate data (medication edit, dose log, appointment create).
- **Acceptance Criteria**:
  - Only Senior can invite or revoke members.
  - A Family member with `can_edit=False` cannot edit schedules or log doses.
- **Tests Required**:
  - `tests/test_members.py`: Test member invitation, `can_edit` enforcement, and Senior-only revocation.
- **Scoring Signals Supported**: Problem Alignment, Security, Code Quality.
- **Time Estimate**: 7 minutes.

---

### Phase 3: Core Features
**Estimated Duration**: 45 minutes (11:30 – 12:15)  
**Objective**: Build core domain features: medication CRUD with soft deactivation, dose adherence with atomic deterministic IDs and derived misses, doctor appointments, and an immutable audit log.

#### Subphase 3.1: Medications CRUD, Soft Deactivation & Privacy Controls
- **Goal**: Provide complete medication management where items are deactivated (never hard-deleted) and private medications are hidden from Family members.
- **Files to Create/Change**:
  - `app/models/medication.py`
  - `app/routes/medications.py`
  - `app/templates/medications.html`
  - `app/templates/medication_form.html`
- **Detailed Tasks**:
  - Define `Medication` model: `id`, `profile_id`, `name`, `dosage`, `frequency`, `scheduled_times` (list of wall-clock "HH:MM" in profile timezone `Asia/Kolkata`), `instructions`, `is_private` (bool), `is_active` (bool, default True), `created_by`, `updated_at`.
  - Implement routes:
    - GET `/medications`: List active medications. If current member role is `FAMILY`, filter out medications where `is_private=True`.
    - GET `/medications/new` & POST `/medications`: Add medication (requires `can_edit`).
    - GET `/medications/{id}/edit` & POST `/medications/{id}/edit`: Edit medication schedule.
    - POST `/medications/{id}/deactivate`: Soft-deactivate by setting `is_active = False` (never hard-delete).
- **Acceptance Criteria**:
  - Soft deactivation sets `is_active=False` and keeps history intact.
  - Family members cannot view or query private medications.
- **Tests Required**:
  - `tests/test_medications.py`: Test CRUD, deactivation behavior, and privacy masking for family role.
- **Scoring Signals Supported**: Problem Alignment, Security, Code Quality.
- **Time Estimate**: 15 minutes.

#### Subphase 3.2: Dose Adherence Tracking & Derived Misses
- **Goal**: Implement dose logging with deterministic IDs written atomically via `create()`, and compute derived misses dynamically.
- **Files to Create/Change**:
  - `app/models/dose_log.py`
  - `app/services/adherence.py`
  - `app/routes/doses.py`
- **Detailed Tasks**:
  - Stored dose statuses: `TAKEN`, `SKIPPED`. (Missed doses are DERIVED, not stored).
  - Deterministic document ID: `{medication_id}_{date}_{time}` (e.g. `med123_2026-11-15_08:00`).
  - Implement atomic write: call repository `create_dose_log(log)` which uses Firestore `create()` or raises `AlreadyExistsError` in memory fake. If slot exists, return friendly message ("Dose already logged by [Name]").
  - Implement derived miss logic in `app/services/adherence.py`:
    - Given a medication and a target date/time, if scheduled slot is 60+ minutes past wall-clock time in profile timezone (`Asia/Kolkata`) and no `TAKEN` or `SKIPPED` log exists, it is marked as `DERIVED_MISSED`.
  - GET `/doses/today`: Render timeline showing today's slots with status (`Taken`, `Skipped`, `Pending`, or `Missed [Overdue]`).
  - POST `/doses/log`: Senior or Caretaker logs status (`TAKEN` or `SKIPPED`).
- **Acceptance Criteria**:
  - Atomic create guarantees no double-logging for the same slot.
  - Missed doses are derived dynamically using the injected `Clock`.
- **Tests Required**:
  - `tests/test_adherence.py`: Test atomic deterministic ID write, duplicate rejection, and derived miss calculation at various time offsets.
- **Scoring Signals Supported**: Problem Alignment, Code Quality, Testing.
- **Time Estimate**: 15 minutes.

#### Subphase 3.3: Doctor Appointments & Audit Trail
- **Goal**: Enable appointment monitoring and record an immutable audit log for every change.
- **Files to Create/Change**:
  - `app/models/appointment.py`
  - `app/models/audit.py`
  - `app/routes/appointments.py`
  - `app/services/audit.py`
  - `app/templates/appointments.html`
  - `app/templates/audit_log.html`
- **Detailed Tasks**:
  - Define `Appointment` model: `id`, `profile_id`, `doctor_name`, `specialty`, `location`, `appointment_datetime` (stored in UTC), `notes`, `created_by`.
  - GET `/appointments`: List upcoming appointments sorted chronologically.
  - POST `/appointments/new`: Create appointment (requires `can_edit`).
  - Implement `record_audit_event(profile_id, action, actor_name, details)`:
    - Log every medication addition, update, deactivation, dose log, member invite, and revocation.
  - GET `/audit`: Chronological view of all recorded events (accessible to Senior & Caretaker).
- **Acceptance Criteria**:
  - Appointments display in local `Asia/Kolkata` time.
  - Audit log immutably records all state modifications with actor identity.
- **Tests Required**:
  - `tests/test_appointments.py`: Test appointment sorting and timezone display.
  - `tests/test_audit.py`: Verify audit entry generation across domain actions.
- **Scoring Signals Supported**: Problem Alignment, Security, Code Quality.
- **Time Estimate**: 15 minutes.

---

### Phase 4: Core Redeploy & Cloud Scheduler Setup
**Estimated Duration**: 30 minutes (12:15 – 12:45)  
**Objective**: Redeploy the complete core system to Cloud Run with production environment variables, set up Cloud Scheduler, and verify live functionality in an incognito window.

#### Subphase 4.1: Cloud Run Redeploy with Production Configuration
- **Goal**: Deploy the full working app to Cloud Run with production secrets injected.
- **Files to Create/Change**:
  - Deployment command / environment variable specification
- **Detailed Tasks**:
  - Execute `gcloud run deploy carekavach --source . --region asia-south1 --allow-unauthenticated` with:
    - `SESSION_SECRET=<random_secret>`
    - `SETUP_CODE=<secure_setup_code>`
    - `SCHEDULER_SECRET=<secret_key>`
    - `COOKIE_SECURE=true`
    - `USE_FIRESTORE=true`
    - `GOOGLE_CLOUD_PROJECT=<project_id>`
- **Acceptance Criteria**:
  - Cloud Run deployment succeeds and 100% traffic is routed to the new revision.
- **Tests Required**:
  - Live HTTPS smoke test against `/health` and `/health/db`.
- **Scoring Signals Supported**: Google Services Usage, Security, Efficiency.
- **Time Estimate**: 10 minutes.

#### Subphase 4.2: Cloud Scheduler Job Setup
- **Goal**: Provision Cloud Scheduler job to periodically trigger reminder evaluations.
- **Files to Create/Change**:
  - Cloud Scheduler setup command documentation
- **Detailed Tasks**:
  - Set up Cloud Scheduler job calling the Cloud Run endpoint:
    ```bash
    gcloud scheduler jobs create http carekavach-reminders \
      --schedule="*/15 * * * *" \
      --uri="https://<cloud-run-url>/tasks/run-reminders" \
      --http-method=POST \
      --headers="X-Scheduler-Secret=<secret_key>" \
      --location=asia-south1
    ```
- **Acceptance Criteria**:
  - Scheduler job is configured and scheduled every 15 minutes.
- **Tests Required**:
  - Manual trigger test via `gcloud scheduler jobs run carekavach-reminders --location=asia-south1`.
- **Scoring Signals Supported**: Google Services Usage, Problem Alignment.
- **Time Estimate**: 10 minutes.

#### Subphase 4.3: Incognito End-to-End Walkthrough Verification
- **Goal**: Perform an end-to-end verification of `/setup`, login, medication creation, and dose logging on the live Cloud Run URL in an incognito window.
- **Files to Create/Change**:
  - Verification checklist
- **Detailed Tasks**:
  - Open incognito browser:
    - Run `/setup` with `SETUP_CODE` to create Senior.
    - Confirm `/setup` is now disabled.
    - Log in with Senior name + passcode.
    - Add a medication and log a dose.
    - Confirm `/health` and `/health/db` return 200 OK.
- **Acceptance Criteria**:
  - The live Cloud Run application is verified functioning end-to-end.
- **Tests Required**:
  - Incognito browser walkthrough.
- **Scoring Signals Supported**: Google Services Usage, Efficiency, Problem Alignment.
- **Time Estimate**: 10 minutes.

---

### Phase 5: Reminders and Email
**Estimated Duration**: 35 minutes (12:45 – 13:20)  
**Objective**: Build proactive email reminder dispatch via SMTP (with stdout log fallback), deterministic escalation counting derived misses, and idempotent `/tasks/run-reminders` using deterministic notification keys.

#### Subphase 5.1: SMTP Email Notification Dispatcher & Log Fallback
- **Goal**: Implement email notification dispatcher with standard MIME formatting and seamless stdout log fallback when credentials are dummy.
- **Files to Create/Change**:
  - `app/services/email.py`
  - `app/templates/emails/reminder_upcoming.html`
  - `app/templates/emails/escalation_missed.html`
  - `app/templates/emails/appointment_reminder.html`
- **Detailed Tasks**:
  - Implement `EmailService` using standard library `smtplib` / `email.mime`.
  - Connect using `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`.
  - If SMTP host is not configured or fails, log the full rendered email cleanly to stdout (Cloud Logging) without throwing an exception.
- **Acceptance Criteria**:
  - Clean HTML and plain text email rendering.
  - Graceful fallback to stdout logging when SMTP is offline or disabled.
- **Tests Required**:
  - `tests/test_email_service.py`: Verify email rendering and graceful fallback without live SMTP server.
- **Scoring Signals Supported**: Code Quality, Problem Alignment, Efficiency.
- **Time Estimate**: 10 minutes.

#### Subphase 5.2: Deterministic Escalation Engine (Counting Derived Misses)
- **Goal**: Implement deterministic escalation rules to alert Caretakers while protecting Family privacy.
- **Files to Create/Change**:
  - `app/services/escalation.py`
- **Detailed Tasks**:
  - Implement escalation evaluation per `docs/decisions.md`:
    - Rule A: A single scheduled dose is 60+ minutes overdue with no log recorded.
    - Rule B: 2 or more derived missed doses within the past 3 days (72 hours).
  - Privacy amendment: **Private medications never appear in emails to family members.** Emails to Caretakers contain full details.
  - Dispatch escalation alerts to active `CARETAKER` members with registered emails.
- **Acceptance Criteria**:
  - Escalation fires if 60+ min overdue or 2 derived misses in 3 days.
  - Family members never receive alerts containing private medications.
- **Tests Required**:
  - `tests/test_escalation.py`: Test Rule A and Rule B evaluation, and verify private medication exclusion for family emails.
- **Scoring Signals Supported**: Problem Alignment, Security, Testing.
- **Time Estimate**: 12 minutes.

#### Subphase 5.3: Idempotent `/tasks/run-reminders` with Deterministic Keys
- **Goal**: Implement protected, idempotent reminder task runner using deterministic document IDs.
- **Files to Create/Change**:
  - `app/routes/tasks.py`
  - `app/services/reminder_runner.py`
- **Detailed Tasks**:
  - Create POST `/tasks/run-reminders` protected by `X-Scheduler-Secret` header matching `SCHEDULER_SECRET`.
  - Deterministic notification key format: `{task_type}_{target_id}_{slot_date}_{slot_time}` (e.g. `dose_reminder_med1_2026-11-15_08:00`).
  - Attempt to write notification key using repository `create_reminder_notification(key)`:
    - If `AlreadyExistsError` / document exists, skip sending (guarantees idempotency).
    - If write succeeds, dispatch the email.
  - Scan for:
    - Upcoming doses within next 30 minutes.
    - Overdue doses matching escalation rules.
    - Appointments within 24 hours and 2 hours.
- **Acceptance Criteria**:
  - Unauthorized calls return HTTP 401.
  - Duplicate executions within the same window send alerts exactly once.
- **Tests Required**:
  - `tests/test_tasks.py`: Test secret header check, notification dispatch, and duplicate execution suppression.
- **Scoring Signals Supported**: Security, Efficiency, Google Services Usage.
- **Time Estimate**: 13 minutes.

---

### Phase 6: Gemini Summary (Non-Clinical Pattern Summary)
**Estimated Duration**: 25 minutes (13:20 – 13:45)  
**Objective**: Use Gemini via `google-genai` to draft non-clinical pattern summaries with strict 3s timeout, fail-safe fallback, and aggregated schedule facts only (zero names, zero emails, zero medical advice).

#### Subphase 6.1: `google-genai` Integration with Strict Privacy & Clinical Boundary
- **Goal**: Integrate `google-genai` SDK passing only aggregated, anonymized schedule facts.
- **Files to Create/Change**:
  - `app/services/gemini_summary.py`
- **Detailed Tasks**:
  - Read `GEMINI_MODEL` from settings (e.g. `gemini-2.5-flash`).
  - Strict privacy rule: **Gemini receives only aggregated schedule facts: no patient names, no caretaker names, no emails.**
    - Example prompt input: `"Schedule status: 3 doses scheduled today. 2 doses taken on time. 1 dose overdue by 65 minutes."`
  - Strict clinical boundary in system instruction:
    - *"You are a compassionate adherence assistant. Summarize adherence facts in 2 short sentences. UNDER NO CIRCUMSTANCES provide medical advice, diagnosis, dosage advice, or drug interaction evaluation. Focus purely on schedule routine logistics."*
  - Call Gemini using the async client or `asyncio.to_thread`.
- **Acceptance Criteria**:
  - Model generates non-clinical, 2-sentence adherence summary without names or clinical advice.
- **Tests Required**:
  - `tests/test_gemini_summary.py`: Verify prompt construction contains no personal names or emails; mock model response.
- **Scoring Signals Supported**: Google Services Usage, Security, Problem Alignment.
- **Time Estimate**: 15 minutes.

#### Subphase 6.2: 3-Second Timeout & Fail-Safe Fallback
- **Goal**: Enforce strict 3.0s timeout and return deterministic plain fallback if Gemini is slow or fails.
- **Files to Create/Change**:
  - `app/services/gemini_summary.py`
- **Detailed Tasks**:
  - Wrap Gemini call with `asyncio.wait_for(..., timeout=3.0)` and comprehensive try/except block.
  - If timeout, network failure, or API quota error occurs:
    - Catch error silently.
    - Return deterministic plain summary: e.g., *"Routine update: 1 dose is currently overdue for today."*
  - Ensure the email dispatch pipeline is never delayed or blocked by Gemini.
- **Acceptance Criteria**:
  - Any error or timeout > 3.0s returns deterministic fallback within 3 seconds.
- **Tests Required**:
  - `tests/test_gemini_summary.py`: Test timeout triggering fallback, API error fallback, and missing API key fallback.
- **Scoring Signals Supported**: Efficiency, Testing, Security, Google Services Usage.
- **Time Estimate**: 10 minutes.

---

### Phase 7: Senior UI Polish & Accessibility Check
**Estimated Duration**: 30 minutes (13:45 – 14:15)  
**Objective**: Polish senior visual components (tokens already established in 1.3), verify full keyboard navigation, and perform a manual Lighthouse accessibility audit.

#### Subphase 7.1: Senior Dashboard Polish & Visual Action Cards
- **Goal**: Refine Senior dashboard with clear visual hierarchy, large dose action buttons, and high contrast.
- **Files to Create/Change**:
  - `app/templates/dashboard_senior.html`
  - `app/static/css/styles.css`
- **Detailed Tasks**:
  - Prominent "Next Action" hero card displaying the immediate scheduled dose.
  - Giant "Taken" and "Skip" buttons with minimum 56px height.
  - Clear status chips with explicit text labels ("Taken at 8:15 AM", "Due at 12:00 PM", "Missed"). Never rely on color alone.
- **Acceptance Criteria**:
  - Senior can log immediate dose in one tap.
  - Contrast ratios exceed 7:1 for text.
- **Tests Required**:
  - `tests/test_accessibility.py`: Verify presence of semantic headings (`<h1>`, `<h2>`), proper `alt` attributes, and text-based status labels.
- **Scoring Signals Supported**: Accessibility, Problem Alignment, Code Quality.
- **Time Estimate**: 10 minutes.

#### Subphase 7.2: Keyboard Navigation & ARIA Landmarks
- **Goal**: Ensure complete keyboard tab navigability, visible blue focus rings, and screen-reader accessibility.
- **Files to Create/Change**:
  - `app/templates/base.html`
  - `app/templates/partials/nav.html`
- **Detailed Tasks**:
  - Ensure skip link jumps directly to `<main id="main-content">`.
  - Verify every `<input>` and `<select>` has an associated `<label for="...">`.
  - Add `aria-live="polite"` container for flash/toast notifications.
  - Verify visible focus ring on all interactive elements.
- **Acceptance Criteria**:
  - Entire user flow (login $\rightarrow$ dashboard $\rightarrow$ dose log $\rightarrow$ logout) is executable using only the Tab and Enter keys.
- **Tests Required**:
  - `tests/test_accessibility.py`: Validate matching `<label>` elements for all form fields, landmarks presence, and valid HTML structure.
- **Scoring Signals Supported**: Accessibility, Code Quality.
- **Time Estimate**: 10 minutes.

#### Subphase 7.3: Caretaker & Family Portals + Lighthouse Audit
- **Goal**: Complete Caretaker and Family portal views, and conduct a manual Lighthouse accessibility audit.
- **Files to Create/Change**:
  - `app/templates/dashboard_caretaker.html`
  - `app/templates/dashboard_family.html`
  - `docs/accessibility_audit.md`
- **Detailed Tasks**:
  - Caretaker view: Schedule overview, derived miss count, audit log preview.
  - Family view: Peace-of-mind adherence summary and upcoming doctor appointments; strictly omitting private medications.
  - Perform manual Google Chrome Lighthouse Accessibility audit on the live pages and record score in `docs/accessibility_audit.md`.
- **Acceptance Criteria**:
  - Manual Lighthouse Accessibility score is 95+.
- **Tests Required**:
  - Manual Lighthouse check in Chrome DevTools.
- **Scoring Signals Supported**: Accessibility, Problem Alignment.
- **Time Estimate**: 10 minutes.

---

### Phase 8: Tests and Security Hardening
**Estimated Duration**: 30 minutes (14:15 – 14:45)  
**Objective**: Complete pytest suite (edge cases, failure branches, double-logging), inject defensive security headers, verify template autoescaping, and run a secret scan.

#### Subphase 8.1: Comprehensive Test Suite & Boundary Coverage
- **Goal**: Achieve comprehensive automated test coverage across domain logic and failure branches.
- **Files to Create/Change**:
  - `tests/conftest.py`
  - `tests/test_edge_cases.py`
  - `tests/test_security.py`
- **Detailed Tasks**:
  - Parameterized tests:
    - Concurrent/duplicate dose log attempts for the exact same slot.
    - Malformed and boundary schedule times.
    - Rate limiter IP and name lockout resets.
    - Inactive/revoked member session rejection.
    - Unauthenticated scheduler task endpoint requests.
    - Derived miss calculation at boundary offsets (59m vs 60m).
- **Acceptance Criteria**:
  - Single-command `pytest` executes and passes 100% of tests in under 5 seconds.
- **Tests Required**:
  - Full test suite run (`pytest -v`).
- **Scoring Signals Supported**: Testing, Code Quality.
- **Time Estimate**: 15 minutes.

#### Subphase 8.2: Security Headers, XSS Validation & Secret Scan
- **Goal**: Apply defensive HTTP security headers, verify XSS auto-escaping, and ensure zero secrets in repository.
- **Files to Create/Change**:
  - `app/middleware/security.py`
  - `app/main.py`
- **Detailed Tasks**:
  - Add security middleware injecting:
    - `X-Content-Type-Options: nosniff`
    - `X-Frame-Options: DENY`
    - `X-XSS-Protection: 1; mode=block`
    - `Referrer-Policy: strict-origin-when-cross-origin`
    - `Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self';`
  - Verify Jinja2 template autoescaping prevents script injection.
  - Run regex secret scan across all tracked files to verify zero API keys or credentials.
- **Acceptance Criteria**:
  - Security headers present on all responses.
  - Secret scan returns zero findings.
- **Tests Required**:
  - `tests/test_security_headers.py`: Assert presence of defensive headers.
- **Scoring Signals Supported**: Security, Code Quality.
- **Time Estimate**: 8 minutes.

#### Subphase 8.3: Ruff Linting & Code Hygiene Audit
- **Goal**: Ensure complete codebase passes Ruff linting and formatting with zero dead code or debug statements.
- **Files to Create/Change**:
  - All `.py` files
- **Detailed Tasks**:
  - Run `ruff check app tests`.
  - Run `ruff format --check app tests`.
  - Verify no `print()` statements or commented-out blocks exist.
- **Acceptance Criteria**:
  - `ruff check` and `ruff format` exit with 0 errors.
- **Tests Required**:
  - `ruff check app tests`
- **Scoring Signals Supported**: Code Quality, Efficiency.
- **Time Estimate**: 7 minutes.

---

### Phase 9: Final Submission Deliverables
**Estimated Duration**: 45 minutes (14:45 – 15:30, buffer to 4:15 PM)  
**Objective**: Complete the README with full scoring signal map, draft the LinkedIn post, audit rulebook compliance, redeploy final code to Cloud Run, commit and push to `main`, and submit before 4:15 PM IST.

#### Subphase 9.1: Comprehensive README Documentation
- **Goal**: Write an exemplary `README.md` detailing architecture, Google services usage, and mapping all 7 judging signals.
- **Files to Create/Change**:
  - `README.md`
- **Detailed Tasks**:
  - Document:
    1. Project Overview & Senior-First Mission.
    2. Architecture & Tech Stack (Python 3.12, FastAPI, Jinja2, Firestore, Cloud Run, Cloud Scheduler, Gemini API).
    3. Google Services Usage & Justification:
       - **Cloud Run**: Stateless container hosting, HTTPS, fast autoscaling.
       - **Firestore**: Native NoSQL document persistence with atomic document creation.
       - **Cloud Scheduler**: Cron-based automated polling for proactive alerts.
       - **Gemini API (`google-genai`)**: Empathetic, non-clinical pattern summaries with deterministic fallback.
    4. Scoring Signal Mapping (Detailed table addressing Code Quality, Security, Efficiency, Testing, Accessibility, Problem Alignment, Google Services).
    5. Accessibility Highlights (WCAG 2.1 AA tokens, 18px text, 48px hit areas, Lighthouse score).
    6. Local Setup & Testing Instructions (`pytest`, local run).
    7. Live Cloud Run Deployed URL.
- **Acceptance Criteria**:
  - README covers every evaluation signal thoroughly and cleanly.
- **Tests Required**:
  - Markdown syntax and link check.
- **Scoring Signals Supported**: Code Quality, Problem Alignment, Google Services Usage.
- **Time Estimate**: 15 minutes.

#### Subphase 9.2: LinkedIn Post Draft & Compliance Verification
- **Goal**: Draft the required LinkedIn submission post URL (starting with `https://`) and complete the rulebook compliance checklist.
- **Files to Create/Change**:
  - `docs/linkedin_post_draft.md`
- **Detailed Tasks**:
  - Draft LinkedIn post highlighting:
    - Elderly Care & Medication Management Platform challenge.
    - CareKavach innovations (empowering seniors, adaptive alert escalation, role-based ecosystem, zero medical advice boundary).
    - Google technologies used (Cloud Run, Gemini API, Firestore, Cloud Scheduler).
    - Required tags and hashtags: `@Google for Developers`, `@Hack2skill`, `#PromptWars`, `#Catalyst`, `#BuildWithAI`.
  - Audit Rulebook Compliance:
    - Solo builder, single account.
    - Public GitHub repo.
    - Repository size strictly under 10 MB.
    - Single branch (`main`).
    - Zero secrets in code or git history.
- **Acceptance Criteria**:
  - LinkedIn post drafted; all compliance checks verified.
- **Tests Required**:
  - Repo size check (`git count-objects -vH`).
- **Scoring Signals Supported**: Problem Alignment, Security.
- **Time Estimate**: 10 minutes.

#### Subphase 9.3: Final Cloud Run Live Health Check
- **Goal**: Perform the final live health and walkthrough check on Cloud Run in an incognito window.
- **Files to Create/Change**:
  - None (validation).
- **Detailed Tasks**:
  - Re-verify live Cloud Run URL in incognito mode:
    - `/health` returns 200.
    - `/health/db` returns 200.
    - Login and medication dashboard loads in < 500ms.
  - **CRITICAL HARD RULE**: Once verified, **DO NOT touch, redeploy, or delete the Cloud Run service**.
- **Acceptance Criteria**:
  - Cloud Run URL is confirmed rock-solid and publicly accessible.
- **Tests Required**:
  - Incognito browser walkthrough.
- **Scoring Signals Supported**: Google Services Usage, Efficiency, Problem Alignment.
- **Time Estimate**: 10 minutes.

#### Subphase 9.4: Final Submission (Commit, Push & Form Submission by 4:15 PM)
- **Goal**: Commit to `main`, push to public GitHub, publish LinkedIn post, submit the form before 4:15 PM IST, and archive confirmation screenshots.
- **Files to Create/Change**:
  - Git repository commit on `main`
- **Detailed Tasks**:
  - Check `git branch -a` to guarantee strictly one branch (`main`).
  - Stage all files, review `git diff --cached` to ensure zero secrets or build artifacts.
  - Execute `git commit -m "CareKavach: Elderly Care and Medication Management Platform"`.
  - Execute `git push origin main`.
  - Publish the drafted LinkedIn post and copy the public post URL (starts with `https://`).
  - Fill and submit the official submission form:
    1. Select Challenge: Elderly Care & Medication Management Platform.
    2. GitHub Public Repo URL.
    3. Deployed Cloud Run URL.
    4. LinkedIn Post URL (starts with `https://`).
  - Take screenshot of submission confirmation and attempt history (Attempt 1 of 2).
- **Acceptance Criteria**:
  - Form submitted before 4:15 PM IST; screenshot archived.
- **Tests Required**:
  - Verify GitHub repo URL and Cloud Run URL in signed-out browser.
- **Scoring Signals Supported**: Problem Alignment, Security, Code Quality.
- **Time Estimate**: 10 minutes.

---

## 3. Priority Cut List (If Behind Schedule)

If unexpected delays occur, drop items strictly in this revised order:

| Cut Priority | Feature to Drop | Rationale | Fallback Behavior |
|---|---|---|---|
| **1 (Drop First)** | Gemini pattern summary in emails | Nice-to-have AI summary; deterministic alert text already satisfies the core reminder requirement. | Emails send standard deterministic alert text immediately. |
| **2 (Drop Second)** | Appointment creation form | Problem statement mandates *monitoring* upcoming doctor appointments; creation form is secondary. | Pre-seed 2-3 realistic upcoming doctor appointments in database during `/setup`. |
| **3 (Drop Third)** | `can_edit` customization for Family role | Role defaults (Family = read-only, Caretaker = edit) already cover the essential ecosystem roles. | Hardcode Family to read-only and Caretaker to edit. |
| **4 (Drop Fourth)** | Live SMTP transmission | External SMTP relay can face firewall blocks or credential issues. | System logs rendered emails cleanly to application log stream (`stdout`), viewable in Cloud Logging. |
| **NEVER DROP** | **Firestore Persistence** | **MANDATORY**: Core persistence for Cloud Run multi-instance operation. | **Firestore is NEVER cut.** |
| **NEVER DROP** | **Cloud Run Live Deployed URL** | **DISQUALIFICATION RISK**: Dead link causes immediate disqualification. | Must stay running at all costs. |
| **NEVER DROP** | **Passcode Auth & Role Isolation** | Core prompt requirement (shared ecosystem, passcode access, senior privacy). | Must remain intact. |
| **NEVER DROP** | **Dose Adherence & Double-Logging Prevention** | Core prompt requirement and evaluation differentiator. | Must remain intact. |
| **NEVER DROP** | **Zero Secrets & Single Main Branch** | Hard disqualification repository rules. | Must remain intact. |

---

## 4. Risks & Mitigations

| Phase | Identified Risk | Impact | Mitigation Strategy |
|---|---|---|---|
| **Phase 1** | Dependency installation or freezing delays | Setup delay | Install core packages first; freeze exact resolved versions via `pip freeze` into `requirements.txt`. |
| **Phase 1** | Cloud Run port binding or container startup failure | Deploy failure | Use official `python:3.12-slim`; test `$PORT` binding; deploy Phase 1.4 smoke skeleton at ~10:50 AM. |
| **Phase 2** | Password hashing library compatibility issues | Runtime crash | Use Python standard library `hashlib.pbkdf2_hmac` with SHA-256 and `secrets.compare_digest` (zero binary C-extensions). |
| **Phase 2** | Rate limiter IP spoofing behind Cloud Run load balancer | Security bypass | Parse first IP address in `X-Forwarded-For` header; combine with per-name rate limiting. |
| **Phase 3** | Wall-clock timezone shifts in dose overdue calculations | False escalations | Anchor all medication schedule times to wall-clock `Asia/Kolkata` using `zoneinfo.ZoneInfo`; inject mockable `Clock` dependency in tests. |
| **Phase 3** | Concurrent requests double-logging the same dose slot | Adherence flaw | Use deterministic document IDs (`{medication_id}_{date}_{time}`) with atomic Firestore `create()` or `AlreadyExistsError`. |
| **Phase 5** | SMTP connection blocked or credentials invalid on Cloud Run | Email errors | Wrap SMTP calls in robust try/except; fallback gracefully to structured stdout logging so app never crashes. |
| **Phase 6** | Gemini API latency spikes (>3s) or rate limit 429 | Task timeout | Wrap in strict 3.0s `asyncio.wait_for`; deterministic fallback triggers seamlessly on any exception. |
| **Phase 7** | Accessibility regression | Score penalty | Base layout and tokens established in Phase 1.3; run manual Chrome Lighthouse Accessibility audit at end. |
| **Phase 8** | Test failures right before submission | Panic / late submit | Run tests incrementally after each subphase; keep tests fast (<5s total run time). |
| **Phase 9** | Cloud Run link accidentally redeployed or stopped after submission | Instant Disqualification | **Hard rule**: After final deploy check in 9.3, DO NOT touch, redeploy, or delete the Cloud Run service. |

---

## 5. Definition of Done (Whole Project)

The project is considered complete and submission-ready when all the following conditions are met:

1. **Problem Alignment & Ecosystem**:
   - Single care profile initialized via `/setup` guarded by `SETUP_CODE`, disabled thereafter.
   - Senior, Caretaker, and Family roles authenticate via unique name + salted passcode (min 6 chars).
   - Rate limiting enforced per IP (first `X-Forwarded-For` value) and per name with generic error messages.
   - Seniors and Caretakers (with `can_edit`) can manage medications and log doses with double-log prevention.
   - Private medications are visible to Seniors and Caretakers, but strictly hidden from Family members in the UI and in emails.
   - Upcoming appointments are monitored and displayed in `Asia/Kolkata` time.
   - Immutable audit trail records who logged doses or modified schedules.
2. **Proactive Reminders & Google Services**:
   - `/tasks/run-reminders` runs idempotently with shared secret authentication and deterministic notification keys.
   - Deterministic escalation triggers when doses are 60+ minutes overdue or missed 2 times in 3 days (counting derived misses).
   - Gemini API drafts non-clinical pattern summaries using aggregated schedule facts only (zero names, zero emails) with an automatic 3-second fallback.
   - Cloud Run service is active, publicly accessible, and verified in an incognito window with `/health` and `/health/db`.
   - Cloud Scheduler job is configured and active.
3. **Accessibility**:
   - Senior-first tokens built into `base.html`: 18px base typography, 48x48px touch targets, >= 7:1 contrast, logical keyboard tab navigation with visible focus rings, and skip link.
   - Manual Lighthouse accessibility score of 95+.
4. **Security & Medical Boundaries**:
   - Zero hardcoded secrets anywhere; all keys injected via environment variables.
   - Defensive security headers (`CSP`, `X-Content-Type-Options`, `X-Frame-Options`, etc.) and Jinja2 auto-escaping.
   - Member re-read from database on every request (never trust role in cookie).
   - Zero medical advice or diagnostic instructions anywhere in code, UI, or prompts.
5. **Code & Repo Hygiene**:
   - Single branch (`main`), repository size under 10 MB.
   - Clean `ruff check` and `ruff format`.
   - Single-command test suite (`pytest`) passes cleanly.
   - README contains full scoring signal map, architecture details, and deployment verification.
   - Form submitted before 4:15 PM IST with verified public GitHub repo, live Cloud Run URL, and `https://` LinkedIn post.
