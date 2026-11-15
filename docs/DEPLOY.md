# Deploying CareKavach to Render

## Prerequisites

- A GitHub account with the CareKavach repository pushed to `main`.
- A [Render](https://render.com) account (free tier is sufficient).
- A Firestore database provisioned in Google Cloud (or leave `USE_FIRESTORE=false`
  to use the in-memory repository for demos).

---

## Steps

### 1. Create a New Web Service

1. Log in to Render → **Dashboard** → **New +** → **Web Service**.
2. Connect your GitHub account and select the **CareKavach** repository.
3. Set the following options:

   | Setting | Value |
   |---|---|
   | **Name** | `carekavach` (or your choice) |
   | **Region** | Singapore (`sgp1`) |
   | **Branch** | `main` |
   | **Runtime** | **Docker** |
   | **Instance Type** | Free (512 MB RAM, 0.1 CPU) |
   | **Health Check Path** | `/health` |

4. Render auto-detects the `Dockerfile` at the repo root. No build command is needed.

### 2. Set Environment Variables

In **Environment → Environment Variables**, add each variable below.
**Never paste real secrets into this file — use Render's secret vault.**

| Variable | Required | Description |
|---|---|---|
| `USE_FIRESTORE` | Yes | `true` to use Cloud Firestore; `false` for in-memory (demo only) |
| `GOOGLE_CLOUD_PROJECT` | If Firestore | GCP project ID, e.g. `my-gcp-project` |
| `FIREBASE_CREDENTIALS_JSON` | If Firestore | Full JSON string of a GCP service-account key with Firestore access |
| `SETUP_CODE` | Yes | Secret one-time code used to call `/setup` and bootstrap the profile |
| `SESSION_SECRET` | Yes | Random 32+ character string for HMAC session signing |
| `SCHEDULER_SECRET` | Yes | Shared secret header for `/tasks/run-reminders` (Cloud Scheduler) |
| `COOKIE_SECURE` | Yes | Set to `true` — Render always serves over HTTPS |
| `GEMINI_API_KEY` | Recommended | Google AI Studio key for Gemini pattern summaries |
| `GEMINI_MODEL` | Optional | Gemini model name (default `gemini-2.5-flash`) |
| `SMTP_HOST` | For email | SMTP server hostname, e.g. `smtp.gmail.com` |
| `SMTP_PORT` | For email | SMTP port (default `587`) |
| `SMTP_USER` | For email | SMTP login username / email address |
| `SMTP_PASSWORD` | For email | SMTP password or app-specific password |

> [!IMPORTANT]
> `SESSION_SECRET` must be at least 32 random characters. Generate one with:
> ```
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

> [!NOTE]
> `SMTP_*` and `GEMINI_API_KEY` are optional — the app starts and `/health` responds
> correctly when they are empty. Email reminders and AI summaries are disabled in
> that mode.

### 3. Deploy

Click **Create Web Service**. Render builds the Docker image, runs the container,
and routes HTTPS traffic through its proxy. The first deploy takes ~2 minutes.

### 4. Bootstrap the Care Profile

Once the service is live, visit:

```
https://<your-app>.onrender.com/setup
```

Enter your `SETUP_CODE`, the senior's name, passcode, and timezone. This creates
the care profile and the SENIOR account. The `/setup` route is permanently
disabled afterwards.

### 5. Verify

| Check | URL | Expected |
|---|---|---|
| Health probe | `/health` | `{"status":"healthy","service":"carekavach"}` |
| DB probe (if Firestore) | `/health/db` | `{"status":"healthy","database":"firestore",...}` |
| Login page | `/login` | Renders accessible login form |
| Incognito test | `/` | Redirects to `/login` |

---

## Proxy and Cookie Notes

The `Dockerfile` starts uvicorn with:

```
--proxy-headers --forwarded-allow-ips='*'
```

This tells uvicorn to trust `X-Forwarded-For` and `X-Forwarded-Proto` headers
set by Render's load balancer, so:

- **`COOKIE_SECURE=true`** works correctly (the app sees the request as HTTPS).
- **Rate limiting** reads the real client IP from the first value in
  `X-Forwarded-For`, not the load-balancer IP.

---

## Cloud Scheduler (Optional — Reminders)

If you want proactive medication reminders, configure a Cloud Scheduler job
(or any cron provider) to POST to:

```
POST https://<your-app>.onrender.com/tasks/run-reminders
Header: X-Scheduler-Secret: <your SCHEDULER_SECRET>
```

Recommended schedule: every 5 minutes (`*/5 * * * *`).

---

## Keeping the Free Instance Warm

Render free instances spin down after 15 minutes of inactivity. To keep the
app warm, configure an external uptime monitor (e.g. UptimeRobot) to ping
`/health` every 10 minutes.
