# Standing Agent Rules: CareKavach

These rules apply to all future automated and manual development in this repository. In any conflict between prior documentation and `docs/decisions.md`, `docs/decisions.md` governs.

---

## 1. Scoring Signals to Optimise

All work must actively optimise the seven evaluation signals:

1. **Code Quality**
   - Clean, modular architecture with small, single-purpose files and functions.
   - Comprehensive Python type hints on all function signatures, parameters, and return values.
   - Zero dead code, no commented-out code blocks, and no stray debug statements (e.g., `print()`, debug loggers).
   - Strict adherence to `ruff` rules (formatting and linting).
2. **Security**
   - Zero hardcoded secrets, tokens, or credentials anywhere in code, configuration, or git history.
   - All secrets injected via environment variables (`.env` locally, Cloud Run environment variables or Secret Manager in production).
   - Strict input validation and sanitisation across all request models and route handlers.
   - Output escaping across all templates to prevent Cross-Site Scripting (XSS).
   - Salted-hash passcodes per member, session protection, and login rate limiting.
   - Protected internal endpoints (e.g., scheduler tasks) using a shared secret header.
3. **Efficiency**
   - Lean dependencies and small application footprint.
   - Sensible algorithms with no redundant database or API calls.
   - Fast cold-start handling for Cloud Run deployment.
   - Keeping total repository size well under the 10 MB limit.
4. **Testing**
   - Automated test suite using `pytest`.
   - Comprehensive test coverage of core domain logic, edge cases, boundary inputs, double-logging prevention, and API failure paths.
   - Single-command execution: `pytest`.
5. **Accessibility (WCAG 2.1 AA)**
   - Target senior-friendly interfaces: 18px base font size, 48px minimum touch targets.
   - High contrast ratios (aim for 7:1 where feasible, minimum 4.5:1).
   - Full keyboard navigability with visible focus indicators.
   - Semantic HTML elements, valid `lang` attribute, clear labels on all form inputs, and proper ARIA landmarks.
6. **Problem Alignment**
   - Address every requirement in the challenge prompt: medication scheduling, adherence tracking, appointment monitoring, role-based shared ecosystem (Senior, Caretaker, Family), and proactive email notifications.
   - Keep the senior at the center: senior empowerment, privacy controls (e.g., private medications hidden from family), and member revocation.
7. **Google Services Usage**
   - Genuine, purposeful integrations of Google Cloud technologies:
     - **Cloud Run**: Serverless container hosting and public endpoint.
     - **Firestore**: Scalable NoSQL persistence for members, medications, logs, and appointments.
     - **Cloud Scheduler**: Cron triggers for proactive reminder jobs.
     - **Gemini API (`google-genai`)**: Non-clinical pattern summaries and email communication tone assistance, with deterministic fallback when unavailable.

---

## 2. Hard Repository Rules

- **Public Repository**: Must remain safe for public viewing at all times.
- **Repository Size Limit**: Must stay strictly under 10 MB (no heavy binaries, datasets, or build outputs).
- **Single Branch (`main`)**: The repository must contain only one branch (`main`). Never create, switch to, or push feature branches.
- **Zero Secrets**: No real secrets, passwords, or API keys in files, commits, or git history.

---

## 3. Git Workflow Rules

- **Never create or switch branches.** All commits and work remain strictly on `main`.
- **Never commit or push unless explicitly requested by the user.** Always wait for explicit instructions before running `git commit` or `git push`.

---

## 4. Coding Standards

- **Tech Stack**: Python 3.12, FastAPI, Jinja2 server-rendered templates, minimal vanilla JavaScript.
- **Structure**: Small, single-purpose modules arranged cleanly in `app/routes/`, `app/services/`, and `app/repositories/`.
- **Type Annotations**: Explicit type hints across all functions and classes.
- **Cleanliness**: No unused imports, no dead code, and no temporary debug logging.
- **Linting & Formatting**: Code must pass `ruff check` and `ruff format` cleanly.

---

## 5. Security & Privacy Rules

- Use `.env` for local testing (never committed; included in `.gitignore`).
- Maintain an accurate `.env.example` with variable names only (no secrets).
- Ensure all user-supplied content rendered in Jinja2 templates is auto-escaped.
- Ensure dose logging logic prevents duplicate records for the same scheduled slot.
- Ensure reminder endpoints are idempotent and authenticated via a secret header.

---

## 6. Accessibility Rules (Senior-First)

- Strict adherence to WCAG 2.1 AA standards.
- High contrast (7:1 target for text).
- Large legible typography (18px base).
- Large interactive hit areas (minimum 48x48px).
- Logical tab order and persistent focus rings for keyboard users.
- Clear error states and status messages accessible to screen readers.

---

## 7. Medical Boundary (Zero Medical Advice)

- **Strict Restriction**: Under no circumstances should the application, its codebase, or any Gemini API prompts produce medical advice, diagnoses, treatment recommendations, drug interaction checks, or clinical dosing instructions.
- All reminder alerts and notifications are purely scheduling and adherence logistical messages.
- Gemini is strictly restricted to drafting concise, non-clinical pattern summaries. If Gemini is unreachable or errors out, reminders must still send immediately without AI content.

---

## 8. Phase Completion Protocol

After completing any development phase or task, the response MUST provide:
1. **Files Changed**: Complete list of all created, updated, or removed files.
2. **How to Run Tests**: Explicit commands to execute the test suite locally.
3. **Assumptions Made**: Clear, transparent list of any design or implementation assumptions.
