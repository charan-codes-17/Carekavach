# Decisions (override docs/research.md where they conflict)

- Stack: Python 3.12, FastAPI, Jinja2 server-rendered templates, minimal JS.
- Google services: Cloud Run (deploy), Firestore (data), Cloud Scheduler (calls
  /tasks/run-reminders), Gemini API via google-genai (summaries only),
  Secret Manager or Cloud Run env vars (secrets).
- Email: SMTP with credentials from env vars.
- Alert escalation is DETERMINISTIC (dose 60+ min overdue, or 2 misses in 3
  days). Gemini only writes a short, non-clinical pattern summary for the
  email. If Gemini fails or times out, the email is sent without the summary.
- Auth: one salted-hash passcode PER MEMBER, each with a role (senior,
  caretaker, family). Login rate limiting. The senior can revoke members and
  mark a medication "private" (hidden from family).
- Audit log for every change and dose log (who, what, when).
- Dose logging must prevent double-logging of the same dose slot.
- Reminder endpoint must be idempotent and protected by a shared secret header.
- Accessibility target: WCAG 2.1 AA (aim for 7:1 contrast), 18px base font,
  48px touch targets, keyboard use, visible focus, lang attribute.
- Cut: Firestore offline mode, native apps, drug-interaction engine, video.
- No medical advice, diagnosis, dosing or interaction checks anywhere.
- Verify the "59%" statistic before using it in the README.
- Repo: public, under 10 MB, one branch (main), no secrets, no build output.

## Amendments (override everything else)

- Login = member name + passcode. Names are unique per care profile. Look up
  the member by name, then verify the salted PBKDF2 hash with constant-time
  comparison (`secrets.compare_digest`). Remove `get_member_by_passcode_hash`;
  add `get_member_by_name`. Passcode minimum 6 characters. Rate-limit per IP
  (use the first `X-Forwarded-For` value) and per name. Generic error messages.
- Member has: email (optional, validated), role, can_edit (bool, set by the
  senior; defaults true for caretaker, false for family), is_active.
- Single care profile per deployment; keep `profile_id` on all models.
- Bootstrap: `/setup` creates the profile and the senior. It is guarded by a
  `SETUP_CODE` env var and disabled once a profile exists.
- Profile timezone defaults to `Asia/Kolkata`. Store UTC timestamps. Medication
  times are wall-clock in the profile timezone (`zoneinfo`). Inject a `Clock`
  dependency so tests can fix the time.
- Missed doses are DERIVED (no log and 60+ minutes past slot), not stored.
  Stored dose statuses: `TAKEN`, `SKIPPED`. Escalation rule B counts derived
  misses.
- Dose logs and reminder notifications use deterministic document IDs
  (`{medication_id}_{date}_{time}` and a reminder key) written with Firestore
  `create()`, which fails if the document exists. The memory repository must
  mimic this with an explicit `AlreadyExists` error.
- Medications are deactivated (`is_active: bool`), never hard-deleted.
- Private medications never appear in emails to family members. Gemini
  receives only aggregated schedule facts: no names, no emails.
- `GEMINI_MODEL` is an env var. Call Gemini with the async client or
  `asyncio.to_thread`, with a 3 second timeout.
- Cookie: signed, with an expiry. Secure flag controlled by `COOKIE_SECURE`
  setting. Re-read the member (role, is_active) from the repository on every
  request; never trust the role in the cookie.
- Base layout and CSS tokens (18px font, 48px targets, focus ring, contrast)
  are built in Phase 1.3 so every template inherits them. Phase 7 is polish.
- Dependencies: install, then freeze actual resolved versions. Do not invent
  version numbers.
- Cut order if behind: (1) Gemini summary, (2) appointment creation form
  (seed instead), (3) can_edit for family, (4) live SMTP (log fallback).
  Firestore is NEVER cut.
