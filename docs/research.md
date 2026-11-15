### 1. KEY POINTS
1. **Retention Driver:** Caregiver connectivity boosts 90-day medication adherence retention by **59%**.
2. **Burnout Risk:** Unfiltered missed-dose alerts cause caregiver notification fatigue and alert burnout.
3. **Identity Flaw:** Shared plain passcodes collapse audit accountability; role-based identity management is required.
4. **TOS Boundary:** Gemini API strictly forbids clinical diagnostic or treatment advice; stick to document structure and retrieval.
5. **Accessibility Standard:** Senior UIs require WCAG 2.0 Level AA compliance (200% text zoom, 4.5:1+ contrast, large touch targets).
6. **Vulnerability Gap:** Senior citizens face low digital literacy (e.g., 32% baseline 2-step verification awareness) and high scam exposure.
7. **Disqualification Guard:** A dead Cloud Run URL during Top 10 evaluation causes instant disqualification.
8. **Scoring Rule:** Only your **last submitted attempt** counts towards the final score.
9. **Repo Limits:** Repository must be public, **under 10 MB**, and contain exactly **one `main` branch**.
10. **Idempotent Crons:** Cloud Scheduler endpoints must handle retries idempotently to prevent duplicate email alerts.

---

### 2. ACTUAL PROBLEMS (Ranked by Severity)
1. **Critical — Health Deterioration:** Medication non-adherence leading to avoidable hospitalisations and mortality.
2. **High — Caregiver Notification Fatigue:** Excessive, low-value notifications causing caregivers to ignore critical alerts.
3. **High — Accountability Collapse:** Shared simple passcodes obscuring who changed schedules or logged doses.
4. **Medium — Visual & Sensory Friction:** Complex app menus, small text, and low contrast unsuited for age-related cognitive/vision decline.
5. **Medium — User Disillusionment:** Health platforms selling user data or locking core reminders behind sudden paywalls.

---

### 3. MISSED PROBLEMS
- **Conflicting Caregiver Edits:** Concurrent schedule updates by multiple caretakers without conflict locking *(General Knowledge /)*.
- **Dose Double-Logging:** Senior and caretaker both logging the exact same dose *(General Knowledge)*.
- **Time Zone Shifts:** Reminders misfiring across caregiver/senior time zones during travel.
- **Unauthorized Passcode Distribution:** Inability to revoke access once a passcode is leaked.
- **Intra-Family Privacy:** Seniors needing privacy for specific sensitive prescriptions (e.g. oncology/psychiatric).
- **Ignored Reminders:** Alerts delivered to the screen but unacknowledged due to notification fatigue.
- **Low Connectivity Use:** App breaking offline in low-coverage rural or indoor environments.
- **Medication Interactions:** Conflicting drug risks *(General Knowledge — must keep non-diagnostic to comply with Gemini ToS)*.
- **Unclear Accountability:** Absence of an immutable log to prove whether a dose was actually missed or just unrecorded.

---

### 4. WHAT COMPETITORS GET WRONG
- **Mandatory Subscriptions:** Wall off basic reminders behind paid plans, alienating long-term users.
- **Unfiltered Escalations:** Blasting caregivers on every single missed dose rather than evaluating behavioral patterns.
- **Privacy Violations:** Selling health telemetry and app activity data to third-party ad networks.
- **Overly Complex UIs:** Deep menu structures, tiny touch targets, and poor contrast unsuited for elderly vision and dexterity.

---

### 5. TRAPS
- **Dead Cloud Run URL:** Unreachable endpoint at Top 10 selection equals immediate DQ.
- **Overwriting Attempt 1:** Submitting a broken Attempt 2 discards a passing Attempt 1 score.
- **Hardcoding Secrets:** Committing API keys to a public repo ruins the Security score.
- **Repo Non-Compliance:** Exceeding 10 MB or leaving secondary git branches.
- **Medical TOS Violation:** Generating AI medical recommendations instead of structuring data.
- **Skipping Tests/README:** Omitted test suites tank evaluation parameters.

---

### 6. RECOMMENDED MVP
**Scope:** **"CareKavach"** — A senior-first medication & appointment companion.

- **Differentiating Features:**
  1. *Smart Adaptive Escalation (Gemini API):* AI evaluates dose logs to escalate email notifications to caregivers only when a risk pattern is detected, eliminating notification fatigue.
  2. *Role-Gated Passcode + Audit Trail:* Simplified senior view vs. Caretaker portal with change logging.
  3. *WCAG 2.0 Compliant High-Contrast Dashboard:* Large click targets, 200% font scaling, and simplified one-tap dose logging.
- **Google Services Used:** **Cloud Run** (deployment), **Gemini API** (smart alert filtering), **Firestore** (NoSQL document store with offline mode).
- **What to Cut:** Native mobile apps, real-time video calls, automated drug interaction engines.

---

### 7. SCORING MAP

| Scoring Signal | MVP Implementation Strategy |
| :--- | :--- |
| **Code Quality** | Modular TypeScript/Python architecture, strict typing, ESLint/Ruff clean. |
| **Security** | Keys via Cloud Run Env Vars (zero secrets in repo), input sanitisation, hashed passcodes. |
| **Efficiency** | Firestore real-time caching, minimal assets, fast Cloud Run cold start. |
| **Testing** | Automated unit test suite (Vitest/Pytest) covering double-logging & edge cases. |
| **Accessibility** | 7:1 contrast ratio, 200% text zoom support, ARIA labels, full keyboard nav. |
| **Problem Alignment** | Delivers medication CRUD, appointment tracking, passcode access, and email alerts. |
| **Google Services** | Deep integration of Cloud Run + Gemini API + Firestore. |

*Flagged Gaps:* None. Full coverage across all 7 signals.

---

### 8. REQUIREMENT TRACE

| Challenge Requirement | MVP Feature |
| :--- | :--- |
| **Shared Ecosystem** | Role-gated dashboard (Senior / Caretaker / Family). |
| **Passcode Access** | Passcode-authenticated profile sessions. |
| **Medication Management** | View, add, edit, and track daily dose adherence. |
| **Doctor Appointments** | Monitor upcoming medical appointments. |
| **Proactive Email Reminders** | Cloud Scheduler triggering email notifications for missed/upcoming doses. |
| **Elderly-Centric Innovation** | Gemini-powered adaptive alert escalation + WCAG 2.0 senior UI. |

---
