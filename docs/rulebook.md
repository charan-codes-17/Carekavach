# HACKATHON RULEBOOK v2: PromptWars x Catalyst

Solo vibe-coding hackathon by **MnM (Makers Need More)** x **PromptWars / Hack2skill** (with Google for Developers).
Read Sections 1, 2, 3 and 10 first.

**What changed in v2:** a new organizer slide deck added a 7th scoring signal (**Google Services usage**), the rule that **only your last submission counts**, a retry rule for technical failures, and a **Top 10 disqualification rule if your Cloud Run link is dead**.

## Source legend (nothing here is invented)

| Tag | Meaning |
|---|---|
| **[S1]** | Read from your first screenshots (Submission page, Resources page, Event page). |
| **[S2]** | Read from your new organizer slides (Evaluation Framework, Attempts & Limits, Leaderboard and Final Ranking). |
| **[W]** | From the parent PromptWars program pages and third-party summaries. **Not Catalyst-specific.** A hint, not a rule. |
| **[R]** | My engineering recommendation. **Not an official rule.** |
| **[?]** | Unclear, unreadable, or contradictory. Verify with the organizers. |

**Verification limits.** The official page (`hack2skill.com/event/promptwars-x-catalyst`) blocks automated access, and the Unstop link returned no content. Your screenshots and slides are the only verified Catalyst sources. Where a slide and an earlier screenshot differ, I flag it in Section 8 and treat the slides as the newer and more specific source [?].

---

## 1. Time-critical snapshot (Sun 15 Nov 2026, IST)

| Item | Detail | Source |
|---|---|---|
| Format | Virtual, **solo only**, free | [S1] |
| Opening & challenge reveal | 9:00 – 9:30 AM | [S1] |
| Build / hacking | 9:30 AM – 4:30 PM | [S1] |
| Submission window | 4:30 – 5:00 PM (module runs 9:00 AM – 5:00 PM) | [S1] |
| Finale | 6:00 – 7:30 PM | [S1] |
| Winner announcement & closing | 7:30 – 8:00 PM | [S1] |
| Scored submissions | **Up to 2**, and **only the last one counts** | [S1] [S2] |
| Prize shown | INR 15,000 (T&C asterisk) | [S1] |

**Suggested time plan [R]:**
- 9:30–10:00: pick a scope you can finish.
- 10:00–1:30: core build.
- By about 12:30: deploy to Cloud Run and test (a dead link means disqualification, see 2.5).
- 1:30–2:30: Google services integration, tests, README.
- 2:30–3:30: security cleanup, accessibility pass.
- 3:30–4:00: LinkedIn post, final checks.
- By 4:15: submit attempt 1.
- Submit attempt 2 only if you are sure it will score higher (see 2.3).

---

## 2. Hard rules and requirements

### 2.1 Repository rules [S1]
1. The repository must be **public**.
2. The repository size must be **under 10 MB**.
3. The repository must contain **only one branch**. Multiple branches are not allowed.

### 2.2 Submission form fields (all required *) [S1]
| Field | What it needs |
|---|---|
| **Challenges** | Dropdown selection. Pick the correct challenge (it was "To Be Announced" before the 9:00 AM reveal). |
| **Public GitHub Repository Link** | URL of the public repo. |
| **Deployed Link (Cloud Run URL)** | A live URL. The label says Cloud Run. |
| **LinkedIn Post** | URL of your LinkedIn post. Must start with `https` or `http`. |

### 2.3 Attempts and scoring of attempts [S2]
- **Up to 2 submissions** (scored) per challenge.
- **Only the last submitted attempt in a challenge is the final score.** "The best attempt score is not used."
- Code assessment scores count toward the leaderboard **only for the challenge**.

**What this means for you [R]:**
- **A second attempt can lower your score.** If attempt 2 is worse, you cannot go back.
- Submit attempt 1 as a solid safety net. Submit attempt 2 **only** if it is clearly better, and test it locally and on Cloud Run first.
- Do not use attempt 2 to experiment.

### 2.4 Retry mechanism for technical failures [S2]
- If an attempt fails due to a **connectivity issue or temporary technical failure**, you get **one chance to retry the same attempt**.
- It applies **only** when the failure is technical (the submission or evaluation could not proceed).
- It does **not** apply when the evaluation completes successfully, even if the score is bad.

**Practical steps [R]:** if a submission errors out, screenshot the error with the time, and contact support (`support@Hack2skill.com`) or the event WhatsApp group right away. It is unclear whether the retry is automatic or must be requested [?].

### 2.5 Leaderboard and Top 10 rule [S2]
- Rankings are determined **exclusively by the platform's parameters**, evaluated against the defined problem statement.
- Parameters named: code quality, security practices, **effective use of Google services**, accessibility, and overall efficiency.
- A **live leaderboard** during the event reflects **Code Assessment scores only**.
- The **Top 10 are selected on the basis of the leaderboard AND the working status of their Cloud Run deployed project.**
- **If your project's deployed link is not working, you will be disqualified (DQed), even if you are in the Top 10.**

**What this means for you [R]:**
- Your Cloud Run service must stay **up and publicly reachable** at least until the results are announced (8 PM) and ideally beyond.
- Do **not** delete or redeploy it carelessly, pause billing, or let free-credit limits stop it.
- Test the URL in an incognito window right after submitting, again at about 5:30 PM, and again before 6:00 PM.
- Whether the Top 10 are the finalists at the 6:00 PM finale is **not stated** [?].

### 2.6 Prerequisites and workflow stated by organizers [S1]
- Google **Antigravity** downloaded and set up.
- **Git** installed and configured.
- An active **GitHub** account.
- Official steps:
  1. Create a new **public** repo on GitHub.
  2. Open Antigravity.
  3. **Clone** the repo inside Antigravity.
  4. **Prompt and code** using Antigravity.
  5. Push your code, with **no multiple branches**.
  6. Copy the public repo link.
  7. Submit via the **Submissions tab**.

### 2.7 Eligibility and conduct
- Solo only: "strictly for individual participants" [S1].
- Audience: "students, developers, designers, and emerging builders across India" [S1]. Hard eligibility conditions are **not stated** [?].
- **[W]** The parent program forbids plagiarism, cheating and **multiple accounts**, and may terminate participation and revoke prizes. Assume this applies here.
- **[W]** Organizers may shortlist and confirm participants at their discretion.

---

## 3. Judging criteria: Code Assessment (automated platform scoring)

The slides say code assessment is **performed automatically on the platform** and checks these signals [S2]:

1. Code Quality
2. Security
3. Efficiency
4. Testing
5. Accessibility
6. Problem Statement Alignment
7. **Google Services usage** (new in the slides; it is **not** among the six parameter chips on the Submission page [S1])

No weights or point values are published [?].

**[W]** A third-party summary of the parent program's Challenge 4 explainer lists the first six and says top scores reward engineering-style solutions, not just a fancy model.

### 3.1 Criteria broken into actionable points

> "Do" and "Avoid" items are **[R]**. They translate the named criteria into concrete work.

#### 1) Code Quality
- **Do:** clear folder structure, small single-purpose modules, meaningful names, consistent formatting (ESLint/Prettier or Ruff/Black), brief comments only where logic is non-obvious, no dead code or leftover scaffolding.
- **Avoid:** one giant file, copy-pasted blocks, unused imports, `console.log` debris, commented-out code.

#### 2) Security
- **Do:** keep **all secrets out of the repo** (it is public). Use `.env` + `.gitignore`, commit a `.env.example`. Inject keys on Cloud Run through environment variables or Secret Manager. Validate and sanitize all user input. Escape output (prevent XSS). Add input-size limits or basic rate limiting on any API. Keep dependencies minimal.
- **Avoid:** hard-coded API keys (even "temporary"), keys in git history, `eval`, string-built SQL, verbose error messages that leak internals, exposing your Gemini/Google key in front-end code.
- **Warning:** a key pushed once stays in history. Rotate it and rewrite history.

#### 3) Efficiency
- **Do:** sensible algorithms and data structures, avoid redundant API or model calls, cache where useful, lazy-load heavy assets, keep the bundle small and the repo lean.
- **Avoid:** N+1 loops, re-fetching on every render, bundling huge libraries for one function, committing media or build output.
- **[W]** The explainer cited "optimize code" improvements (e.g. binary search) as efficiency gains.

#### 4) Testing
- **Do:** an **automated test suite** (Jest/Vitest/pytest) covering core logic **and edge cases**: empty input, invalid input, boundary values, API-failure paths. One-command run (`npm test` / `pytest`), documented in the README.
- **Avoid:** no tests, or trivial tests that assert nothing.
- **[W]** The explainer said testing scores drop when edge cases are not covered.

#### 5) Accessibility
- **Do:** semantic HTML, labels on every input, alt text, keyboard navigation and visible focus, sufficient colour contrast, `aria-*` where needed, responsive layout, `lang` attribute, don't rely on colour alone, respect reduced motion.
- **Avoid:** click-only `<div>` buttons, placeholder-only labels, low-contrast text, auto-playing media.

#### 6) Problem Statement Alignment
- **Do:** after the reveal, turn every explicit requirement in the challenge text into a checklist and build to **that**. Make the first screen visibly address the problem. Use the problem's own terms in the UI.
- **Avoid:** building your favourite idea that only loosely fits, or over-scoping.
- **[W]** In the parent program, GenAI doing real reasoning or generation was valued over plain rules. This is not confirmed for Catalyst [?].

#### 7) Google Services usage (new)
- **Do:** integrate real Google services where they serve the problem. Cloud Run is already required. Likely candidates [R]: **Gemini API** (via AI Studio or Vertex AI) for the core intelligence, **Secret Manager** for keys, **Firebase** for auth or storage if needed, **Google Maps/Places** if the challenge is location-based, **Cloud Logging**.
- **Avoid:** adding a Google service just to name-drop it. Unused or decorative integrations may not count and add attack surface.
- **[?]** The slides do not say which services count or how deeply. Pick services that fit the challenge. Say in the README which ones you used and why.

### 3.2 Priority guidance (weights unknown)
Treat all seven as roughly equal [?].
1. **Problem alignment.** A wrong target wastes everything.
2. A **working, publicly reachable Cloud Run app.** A dead link means disqualification.
3. **Effective Google services use** (real, not decorative).
4. **Security hygiene** (cheap to get right, costly to get wrong).
5. **Tests + README.**
6. Accessibility pass.
7. Efficiency and code-quality polish.

---

## 4. Development guidelines (what to build, prioritize, avoid)

All [R] unless stated.

**Build**
- A **small, finished, deployed** solution over a large half-working one (build window is about 7 hours [S1]).
- A single clear user flow that demonstrates the challenge end to end, with at least one meaningful Google service doing real work.
- One repo, one branch (`main`), one deploy target (Cloud Run).

**Prioritize**
- Scope decision within the first 30 minutes after the reveal.
- **Deploying early** (around 12:30 PM) so you find Cloud Run problems while there is time.
- Writing tests as features land.
- Specific, single-responsibility prompts to Antigravity (e.g. "add input validation to X with tests"), then **reviewing what it generated**.

**Avoid**
- Large datasets, models, videos or `node_modules` in the repo (10 MB limit).
- Feature branches "just to try something".
- Anything that needs your local machine to run.
- Last-minute framework or dependency swaps.
- Redeploying or deleting the Cloud Run service after you submit.

**Cloud Run practicalities**
- The service must listen on `$PORT` on `0.0.0.0`.
- Allow public (unauthenticated) access so the platform and judges can open it. A login-walled URL looks like a dead link [?].
- Consider a cold-start-safe setup (for example min instances of 1) so the first request after idle time does not time out. This may cost credits [?].
- Check the "Google Cloud Credit Claim Instructions" link in Quick Links [S1] now. Its contents were not visible [?].

---

## 5. Compliance checklist (disqualification guard)

- [ ] Working **solo**, with no collaborators [S1].
- [ ] **One** account only [W].
- [ ] Repo is **public** [S1].
- [ ] Repo is **under 10 MB** [S1]. Check on GitHub or run `git count-objects -vH`.
- [ ] Repo has **exactly one branch** [S1]. Run `git branch -a`, and delete extras locally and on the remote.
- [ ] Built with **Antigravity** per the official workflow [S1]. Strict enforcement is not stated [?].
- [ ] Code is original, and any third-party code or assets are licensed or credited [W].
- [ ] No secrets or API keys in the repo or git history [R].
- [ ] **Cloud Run URL is live, public, and stays up** through results and after [S1] [S2].
- [ ] LinkedIn post exists, is public, and the URL starts with `https://` [S1].
- [ ] Correct **challenge** selected in the dropdown [S1].
- [ ] Attempts used: ____ / 2. **The last submitted attempt is the one that counts** [S2].
- [ ] Submitted **before 5:00 PM IST** (aim for 4:15 PM) [S1].

---

## 6. Common mistakes that cost points or cause disqualification

| Mistake | Why it hurts | Source |
|---|---|---|
| **Cloud Run link not working at Top 10 selection** | Disqualification, even from the Top 10 | [S2] |
| **Submitting a weaker attempt 2** | Only the last attempt counts. Your better first score is discarded | [S2] |
| Treating a completed-but-poor evaluation as a "technical failure" | The retry applies only when evaluation could not proceed | [S2] |
| Extra branches left in the repo | Violates the one-branch rule | [S1] |
| Repo over 10 MB (build output, images, `node_modules`, `.venv`) | Violates the size rule. Add `.gitignore` from the first commit | [S1] |
| Private repo | Violates the public-repo rule | [S1] |
| No real Google services use (or only name-dropped) | Loses the Google Services usage signal | [S2] |
| API key committed or shipped in front-end code | Security score, plus a public leak | [R] |
| Wrong challenge in the dropdown | Evaluated against the wrong brief | [S1] |
| LinkedIn URL missing `https://`, or a profile link instead of a post link | Form validation or invalid proof. Use your **post** link and confirm [?] | [S1] |
| Starting submission at 4:55 PM | No recovery time for GitHub, Cloud Run, or form hiccups | [R] |
| No tests / no README | Testing score loss, and judges cannot run your project | [R] |
| Ignoring details in the problem statement | Problem Alignment score | [S1] [S2] |
| Multiple accounts, copied code | Possible termination | [W] |

---

## 7. Discrepancies between sources

| # | Discrepancy | Handling |
|---|---|---|
| 1 | The FAQ says registration is open **7 Oct – 7 Nov** and the hackathon is on **8 Nov**. The Timeline and Submission page say **15 Nov** (registration until 08:50 AM IST). | **Follow the Timeline and Submission page.** The FAQ looks stale. |
| 2 | The Submission page lists **6** parameters. The slides list **7** (adding **Google Services usage**). | Plan for all 7 [S2]. Ask organizers if it matters [?]. |
| 3 | The leaderboard slide names code quality, security, Google services, accessibility and efficiency, and does not mention testing or problem alignment. The framework slide lists testing too, and says scoring is "evaluated against the defined problem statement". | Treat the framework slide's full list as the scored signals. The leaderboard slide is likely a summary [?]. |
| 4 | The slides say "each **phase**" and "challenge". The event is a single-day event. | Likely generic program wording. Treat "phase = this challenge" [?]. |
| 5 | The Timeline's submission block is 9:00 AM – 5:00 PM, but the sub-schedule says "Submission" 4:30–5:00 PM. | Unclear if early submissions are accepted [?]. The Submission module showed open earlier. Submit early only if the build is final, and remember that a later attempt 2 replaces it. |
| 6 | Prize shows **INR 15,000**. The FAQ says the pool is **₹15,000–₹50,000** depending on valid participants and submissions. | Consistent (₹15,000 is the floor). The split across ranks is not stated [?]. |
| 7 | The parent PromptWars Virtual page says Antigravity is required and the program is India-residents-only. | Not confirmed for Catalyst. Catalyst's Resources page lists Antigravity as a prerequisite [S1], so use it. |

---

## 8. Unclear, unreadable or unverified (do not assume)

- **Scoring weights or maximum points** per signal.
- **Meaning of the coloured dots** on the parameter chips on the Submission page.
- **The actual challenge(s):** "To Be Announced" in the first screenshots.
- **Which Google services count** for the "Google Services usage" signal, and how it is scored.
- **Whether the Top 10 go to the finale**, and the finale format (pitch, demo, none).
- **Whether the technical-failure retry is automatic or must be requested.**
- **Whether Antigravity use is verified or merely recommended** for Catalyst.
- **Whether "Cloud Run" is mandatory** or any public host is accepted. The field label and the DQ rule both say Cloud Run, so **use Cloud Run**.
- **LinkedIn content requirements** (tags, hashtags, length). [W] A sibling PromptWars event required tagging Google for Developers and Hack2skill. It is a free precaution, but not a stated Catalyst rule.
- **Full prize terms:** the "Initiative Terms & Conditions" link was not readable.
- **The Drive guide link** ("How to make a submission?") and **Google Cloud Credit Claim Instructions** link: truncated or unread.
- **Eligibility details:** age, residency, ID verification are not stated.
- **Contacts:** the page header shows two emails without labels. Footer support email: `support@Hack2skill.com`. The parent program lists `promptwarssupport@hack2skill.com` [W].
- **Slide provenance:** the slides are unlabeled in the images you sent. I assume they are official organizer slides for this event [?].

---

## 9. Final pre-submission checklist

**Code and repo**
- [ ] App runs from a clean clone using README steps only.
- [ ] `.gitignore` covers `node_modules`, `.env`, build output, venvs.
- [ ] Repo size well under 10 MB.
- [ ] `git branch -a` shows **only** `main`.
- [ ] No secrets in files **or** history. `.env.example` is present.
- [ ] Tests exist, pass, and cover edge cases. The test command is in the README.
- [ ] Lint is clean, with no dead code or debug logs.
- [ ] README includes: problem, approach, features, **Google services used and why**, tech stack, setup, test command, deployed URL, and how Antigravity was used.

**Quality pass (per signal)**
- [ ] Code Quality: structure and naming are clean.
- [ ] Security: inputs validated, secrets only via env or Secret Manager.
- [ ] Efficiency: no redundant calls, lean assets.
- [ ] Testing: failure paths tested.
- [ ] Accessibility: keyboard use, labels, contrast, alt text checked.
- [ ] Problem Alignment: every requirement in the challenge text is ticked off.
- [ ] Google Services: at least one integration does real work in the core flow.

**Deployment**
- [ ] Cloud Run URL opens in an **incognito window** without login.
- [ ] Core flow works on the live URL, not just locally.
- [ ] The URL is the final revision.
- [ ] You know not to touch, delete, or stop the service afterward.

**Submission form**
- [ ] Correct **Challenge** selected.
- [ ] GitHub URL pasted, and it opens while signed out.
- [ ] Cloud Run URL pasted.
- [ ] LinkedIn **post** URL is public and starts with `https://`.
- [ ] Attempt 1 submitted by 4:15 PM.
- [ ] Attempt 2 **only if** it is clearly better, since the last attempt is final.
- [ ] Screenshot of the confirmation and the attempt history.

**After submitting**
- [ ] Re-test the Cloud Run URL at about 5:30 PM and again before 6:00 PM.
- [ ] Watch the live leaderboard (Code Assessment only).
- [ ] If a submission fails technically, screenshot it and contact support immediately.

---

## 10. Sources

- Your first screenshots: Submission page, Resources page, event About/FAQ/Timeline page **[S1]**
- Your new organizer slides: Evaluation Framework, Attempts & Limits, Leaderboard and Final Ranking **[S2]**
- Official event page (could not be fetched, blocked by robots.txt): https://hack2skill.com/event/promptwars-x-catalyst
- Unstop listing (returned no readable content): https://unstop.com/o/HQWfREC
- Parent program, PromptWars Virtual (conduct, FAQs) **[W]**: https://promptwars.in/promptwarsVirtual.html
- Third-party summary of the Challenge 4 explainer (evaluation dimensions, testing and deployment tips) **[W]**: https://youtubesummary.com/summary/9-forxKsm0E

**Recommended:** email `support@Hack2skill.com` or use the WhatsApp group (link on the event page) to confirm the items in Section 8, especially the scoring weights, what counts as Google services usage, and the Top 10 and finale details.