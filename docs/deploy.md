# Deploying

**First deployed on 17 Nov 2026**, from the command line rather than the dashboards; the commands are under "What was actually run" at the end. The dashboard steps below are the equivalent and were checked against Railway's and Vercel's documentation on 16 Nov 2026.

Backend on Railway, from `backend/Dockerfile`. Frontend on Vercel, from `frontend/`.

## Backend (Railway)

1. New Project, choose the **GitHub repo** option, pick the repo, then **Add variables**. Leave the service's root directory as the repo root: the image needs `data/` as well as `backend/`.
2. Service variables:

| Variable | Value |
|---|---|
| `RAILWAY_DOCKERFILE_PATH` | `/backend/Dockerfile` (Railway's own example of a Dockerfile in a subdirectory has the leading slash) |
| `ADMIN_TOKEN` | a new random string of at least 32 characters; not the one in your local `.env` |
| `ANTHROPIC_API_KEY` | your key |
| `ANTHROPIC_MODEL` | leave unset for `claude-haiku-5-5` |
| `FRONTEND_ORIGIN` | the Vercel URL, once you have it |
| `ASK_RATE_PER_MINUTE`, `ASK_DAILY_BUDGET_USD` | optional; defaults are 5 and 2 |

3. Variable changes are staged, not applied: click **Deploy** to apply them.
4. In the service settings, set the health check path to `/health`.
5. In the service settings, under Networking, Public Networking, choose **Generate Domain**. Vercel reaches the backend over the internet, so it must have one; the admin token is what keeps strangers out.

Railway injects `PORT` and the image listens on it. Do not set `EVENT_SOURCE` or `DEPLOYED`.

Settled by the first deploy: with `RAILWAY_DOCKERFILE_PATH=/backend/Dockerfile` the Docker build context is the repo root, as the image needs.

No Railway config file is committed. Railway's `railway.toml` format stops working for existing services on 1 December 2026 and cannot be used for new ones, so the settings above are made in the dashboard.

### What the image refuses

It sets `DEPLOYED=1`, and with that the app will not start if:

- `ANTHROPIC_API_KEY` is missing. Demo mode answers from recorded fixtures and is for local use only.
- `ADMIN_TOKEN` is missing or shorter than 32 characters.
- `EVENT_SOURCE` is anything but `file`.

The same refusals apply to anything running on Railway, image or not: Railway sets `RAILWAY_ENVIRONMENT_NAME` in every container, and the app treats that as deployed too. So a service that Railway built without this Dockerfile (a misspelt `RAILWAY_DOCKERFILE_PATH`, say) still cannot start in demo mode.

The start-up log names every problem at once. CI builds the image and checks the first refusal and a healthy start on every pull request.

## Frontend (Vercel)

1. Create New, Project, import the same repo. On the import screen, click **Edit** next to Root Directory and set it to `frontend`.
2. Environment variables: `BACKEND_URL` (the Railway domain, with `https://`) and `ADMIN_TOKEN` (the same value as on Railway). Neither name starts with `NEXT_PUBLIC_`, and neither may.
3. In the project's Environment Variables page, make sure **Enable access to System Environment Variables** is ticked. The Ask route trusts a visitor's address only when `VERCEL=1`, and Vercel sets that only with this option on.
4. A changed environment variable only applies to new deployments: redeploy after any change.

Then set `FRONTEND_ORIGIN` on Railway to the Vercel URL and click Deploy there to apply it.

## Check after the first deploy

- The page loads in under two seconds (the Phase 6 gate).
- The Ask box shows no "Demo mode" label.
- Two different networks get separate rate limits. This is the assumption that could not be tested locally: that Vercel sets `x-real-ip` itself, and that `X-Visitor-Address` arrives at Railway unchanged.
- `curl https://<railway-domain>/api/overview?window=7d` returns 401.

## The cache warm

It needs no platform schedule. The backend warms its cache at startup and every five minutes after, inside its own process. If Railway puts the service to sleep when idle, the first request after a sleep pays for a container start, which no cache can help; turn sleeping off for the demo if that matters.

## What was actually run (17 Nov 2026)

Both platforms were set up with their command-line tools, logged in by the owner. The first deploys were uploads from the working copy. Later the same day both services were connected to the GitHub repo, so **a merge to `main` deploys both** (see "Deploying on merge" below).

```
# Backend, from the repo root
railway init --name ask-analytics
railway add --service backend --variables RAILWAY_DOCKERFILE_PATH=/backend/Dockerfile --variables ASK_DAILY_BUDGET_USD=1
railway variable set ADMIN_TOKEN --stdin --skip-deploys -s backend        # a new 64-character token, not the local one
railway variable set ANTHROPIC_API_KEY --stdin --skip-deploys -s backend
railway up --ci -s backend
railway domain -s backend
railway variable set FRONTEND_ORIGIN=https://ask-analytics-five.vercel.app -s backend

# Frontend, from frontend/
vercel link --yes --project ask-analytics
vercel env add BACKEND_URL production
vercel env add ADMIN_TOKEN production --sensitive
vercel deploy --prod --yes
```

Secrets were piped in and never printed. The deployed admin token exists only on the two platforms; to rotate it, set a new value on both and redeploy both.

To deploy by hand without a merge: `railway up --ci -s backend` from the repo root, and `vercel deploy --prod --yes` from the repo root (the project's root directory is now `frontend`, so run it from the repo root, not from `frontend/`).

Railway needs a paid plan (Hobby) once its trial has ended; project creation is refused otherwise.

The health check path could not be set from the command line: `railway environment edit --service-config backend deploy.healthcheckPath /health` reports "No changes to apply" and the service's settings show none. Set it in the dashboard: the service's Settings, Deploy, Healthcheck Path, `/health`.

## Deploying on merge

Each platform's GitHub app must be installed on the account that owns the repo, with access to this repo; the connection is refused otherwise ("User does not have access to the repo").

```
railway service source connect --repo nkanyi-so/ask-analytics --branch main --service backend
vercel git connect https://github.com/nkanyi-so/ask-analytics        # from frontend/, where the project is linked
vercel api /v9/projects/<project-id> -X PATCH -F rootDirectory=frontend
```

Vercel's production branch is `main`. Vercel also builds a preview for each pull request; previews have no `BACKEND_URL` or `ADMIN_TOKEN` (both are set for production only), so a preview shows the "backend unreachable" view. That is deliberate: the token stays out of preview builds.

