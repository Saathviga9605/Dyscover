# Production Deployment Guide

Dyscover ships as four Docker Compose services:

- `postgres`: PostgreSQL 16. Internal network only; no published port.
- `migrate`: a one-shot `alembic upgrade head`.
- `backend`: FastAPI on uvicorn, running as uid 10001. Internal only. Its healthcheck uses `/api/health/ready`.
- `web`: unprivileged nginx (uid 101). Serves the SPA, proxies `/api`, and publishes `${WEB_PORT}`.

TLS must be terminated by a reverse proxy in front of `web`. This guide names no real domain or server: replace `dyscover.example.org` with your own.

**What was verified on 2026-10-21 (Windows 11, Docker 29.8.0):**
- the images build;
- the stack reaches healthy;
- smoke tests pass through nginx;
- `pg_dump` / `pg_restore` round-trip;
- production refuses `RESEARCH_DEMO_ENABLED=true` and weak `SECRET_KEY`s.

**Not verified:** a real Linux server, a real TLS certificate, or real DNS.

## 1. Server preparation

- Use a Linux host with Docker Engine 24+ and the Compose plugin.
- Size: at least 2 vCPU, 2 GB RAM, plus disk for the database and backups.
- Firewall: allow only 80/443 from the internet. Do not expose `WEB_PORT` publicly; bind it to localhost behind the TLS proxy, or firewall it.
- Run the stack as a non-root user in the `docker` group.

```bash
git clone <your repository URL> dyscover && cd dyscover
git checkout <release tag or commit>
```

## 2. Configuration (`.env` next to `docker-compose.yml`, never committed)

```bash
cp .env.example .env
chmod 600 .env
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48))"        # paste into .env
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24))" # paste into .env
```

### Environment-variable checklist

| Variable | Where it is used | Production value |
|---|---|---|
| `POSTGRES_PASSWORD` | postgres, migrate, backend | Required; random |
| `SECRET_KEY` | backend (JWT signing) | Required; ≥ 32 random characters. Startup fails on empty, placeholder or short values |
| `PUBLIC_ORIGIN` | backend `CORS_ORIGINS` | Exact public origin, e.g. `https://dyscover.example.org`. `*` is refused |
| `WEB_PORT` | web published port | e.g. `8080`, reachable only by the TLS proxy |
| `REFRESH_COOKIE_SECURE` | backend | `true`. Use `false` only for a plain-HTTP trial on localhost |
| `GROQ_API_KEY`, `GROQ_MODEL` | backend (Lexi) | Optional. Without a key Lexi reports "not configured". Messages typed to Lexi are sent to Groq |
| `APP_ENV` | set by compose | `production` (also disables `/docs`) |
| `DATABASE_URL` | set by compose | Points at the `postgres` service |
| `RESEARCH_DEMO_ENABLED` | not set by compose | **Must stay unset/false.** Production startup refuses `true`. The image also does not contain the research artifacts |
| `SCREENING_MODEL_DIR` | backend | Default `models/screening`. Empty: the parent card shows "no validated model". Only models passing every eligibility check are used |
| `WEB_CONCURRENCY` | backend | uvicorn workers (default 2). The rate-limit state is per process |

## 3. Build and start

```bash
docker compose build
docker compose up -d --wait     # postgres (healthy) -> migrate (exits 0) -> backend (ready) -> web (healthy)
docker compose ps
```

Migrations run once, in order, before the API starts. The API itself refuses to start in production unless the schema is at head.

## 4. TLS reverse proxy (example; adapt to your proxy)

Caddy, which obtains certificates automatically:

```
dyscover.example.org {
    reverse_proxy 127.0.0.1:8080
}
```

The proxy must forward `X-Forwarded-For` and `X-Forwarded-Proto`. nginx inside `web` passes them on to the API, which trusts proxy headers only on the internal network. Set `PUBLIC_ORIGIN` to the HTTPS origin and keep `REFRESH_COOKIE_SECURE=true`.

## 5. Smoke test

```bash
curl -s https://dyscover.example.org/api/health/ready   # {"status":"ready","database":"ok","schema_revision":"0004_research_predictions",...}
curl -sI https://dyscover.example.org/ | grep -iE "content-security|x-frame|referrer"
curl -s -o /dev/null -w '%{http_code}\n' https://dyscover.example.org/api/children   # 401
```

Then, in a browser:
1. Register a parent and add a child.
2. Play one visual adventure.
3. Confirm the dashboard shows observations and **"No validated screening model yet"** with no percentage.

## 6. Backup

Back up daily, keep the dumps off the host, and encrypt them: they contain children's data.

```bash
docker compose exec -T postgres pg_dump -U dyscover -d dyscover -Fc > backups/dyscover-$(date +%F).dump
```

Example cron entry (02:30 daily, keeping 14 days):

```
30 2 * * * cd /srv/dyscover && docker compose exec -T postgres pg_dump -U dyscover -d dyscover -Fc > backups/dyscover-$(date +\%F).dump && find backups -name '*.dump' -mtime +14 -delete
```

## 7. Restore

**Check first:** restore into a scratch database (this procedure was verified):

```bash
docker compose exec -T postgres createdb -U dyscover restore_check
docker compose exec -T postgres pg_restore -U dyscover -d restore_check < backups/dyscover-YYYY-MM-DD.dump
docker compose exec -T postgres psql -U dyscover -d restore_check -c "select version_num from alembic_version"
docker compose exec -T postgres dropdb -U dyscover restore_check
```

**Real restore:** this replaces live data, so take a fresh backup first.

```bash
docker compose stop backend web
docker compose exec -T postgres pg_restore -U dyscover -d dyscover --clean --if-exists < backups/dyscover-YYYY-MM-DD.dump
docker compose up -d --wait
```

## 8. Upgrade

```bash
docker compose exec -T postgres pg_dump -U dyscover -d dyscover -Fc > backups/pre-upgrade-$(date +%F-%H%M).dump
git fetch && git checkout <new release>
docker compose build
docker compose up -d --wait        # migrate runs alembic upgrade head before the new backend starts
curl -s https://dyscover.example.org/api/health/ready
```

## 9. Rollback

- **Application only (no new migration in the release):** check out the previous release, then run `docker compose build && docker compose up -d --wait`.
- **Release included a migration:** the migrations have downgrade steps. `0004 → 0003` was verified on PostgreSQL. Downgrading drops the tables added by the downgraded migration (for `0004`, `research_predictions`).

  ```bash
  docker compose run --rm migrate alembic downgrade <previous revision>
  git checkout <previous release> && docker compose build && docker compose up -d --wait
  ```

- **Data problem:** restore the pre-upgrade dump (§7).

## 10. Logs and operations

- View logs with `docker compose logs -f backend web`.
- Request logs carry request IDs, not tokens or passwords. The smoke test found none of the secrets or the test password in the logs.
- Screening logs record only status, assessment ID and model ID, never feature values.
- Not included in this repository:
  - monitoring and alerting;
  - off-host backup storage;
  - a shared rate-limit store for multiple hosts.

  Provide these before public access (see `docs/readiness/project-completion-checklist.md`).

## Never do this on a server holding real data

- `docker compose down -v`: deletes the database volume.
- `RESEARCH_DEMO_ENABLED=true`: refused anyway.
- Committing `.env`.
