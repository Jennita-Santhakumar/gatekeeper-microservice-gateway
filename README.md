# Flask Microservice API Gateway

> **Maintained by [Jennita S](https://github.com/Jennita-Santhakumar)** · [LinkedIn](https://linkedin.com/in/jennitas) · jennitasanthakumar0@gmail.com

A Flask-based API gateway that fronts two independent FastAPI microservices with JWT
authentication, Redis-backed rate limiting, circuit-breaker-protected proxying, correlation-ID
request tracking, and end-to-end distributed tracing (OpenTelemetry → Jaeger) and metrics
(Prometheus) — with a React dashboard for live observability.

```
                          ┌──────────────────────────┐
   React Dashboard ─────▶ │   Flask API Gateway       │
   (Vite/TS, :5183)       │   ├─ JWT auth              │
                          │   ├─ Redis rate limiting   │
                          │   ├─ Correlation IDs       │
                          │   ├─ Circuit breaker       │
                          │   └─ Service routing       │
                          └─────────┬────────┬─────────┘
                                    │        │
                     ┌──────────────┘        └──────────────┐
                     ▼                                       ▼
           users-service (FastAPI)                  posts-service (FastAPI)
           + its own Postgres DB                     + its own Postgres DB

   Observability: OpenTelemetry → Jaeger (traces)     Gateway /metrics → Prometheus
```

## Why this project

Portfolio piece demonstrating the API-gateway pattern for real: not a routing stub, but a gateway
that actually authenticates, rate-limits, circuit-breaks, and traces requests across genuinely
separate services — each proxy call is independently authenticated, capped, and observable, and a
downstream outage degrades gracefully (fast 503s, not hangs) instead of taking the whole system
down with it.

## Stack

| Layer | Choice |
|---|---|
| API Gateway | Flask 3 + Gunicorn |
| Downstream services | FastAPI (users-service, posts-service), each with its own Postgres |
| Auth | PyJWT + passlib(bcrypt) |
| Rate limiting | Redis (fixed-window INCR/EXPIRE) |
| Resilience | `circuitbreaker` package around downstream HTTP calls |
| Tracing | OpenTelemetry, exported via OTLP/HTTP to Jaeger |
| Metrics | `prometheus_client`, scraped by Prometheus |
| Frontend | React + TypeScript + Vite + Tailwind |
| Tests | pytest (gateway + both services), Vitest (frontend) |
| CI | GitHub Actions (lint, test, Docker build) |

## Quickstart (Docker)

```bash
docker compose up --build
```

This builds and starts nine containers: the gateway, both microservices, a Postgres instance per
service, Redis, Jaeger, Prometheus, and the frontend.

| Service | URL |
|---|---|
| Frontend dashboard | http://localhost:5183 |
| Gateway | http://localhost:8100 |
| users-service (direct) | http://localhost:8101 |
| posts-service (direct) | http://localhost:8102 |
| Jaeger UI | http://localhost:16687 |
| Prometheus | http://localhost:9091 |

Try it end to end:

```bash
# Register (also creates a business record in users-service and returns a JWT)
curl -X POST http://localhost:8100/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"a-real-password"}'

# Use the returned access_token to create a post through the gateway
curl -X POST http://localhost:8100/api/posts \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"user_id":1,"title":"Hello","content":"Routed through the gateway"}'
```

Then open http://localhost:5183, log in with the same credentials, and watch live metrics and
downstream health update every 5 seconds. Open http://localhost:16687 to see the resulting trace
spanning the gateway, the service, and its database query.

## Local development (without Docker)

**Gateway:**

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate    # Windows
pip install -r requirements-dev.txt
python app.py   # http://localhost:8000, needs Redis reachable at REDIS_HOST/REDIS_PORT
```

**Each microservice** (`services/users-service`, `services/posts-service`):

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000   # needs its own Postgres reachable at DATABASE_URL
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev   # http://localhost:5183, set VITE_GATEWAY_URL if the gateway isn't on :8100
```

Copy each `.env.example` to `.env` and adjust as needed; every default matches local (non-Docker)
dev out of the box.

## API reference

### Gateway (`http://localhost:8100`)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | — | Create a credential + business record, returns a JWT |
| POST | `/auth/login` | — | Exchange email/password for a JWT |
| GET | `/health` | — | Gateway liveness (no downstream calls) |
| GET | `/services/health` | — | Live aggregated health of users-service + posts-service |
| GET | `/metrics` | — | Prometheus exposition format |
| ANY | `/api/users[/...]` | JWT | Rate-limited (1000/60s), circuit-breaker-protected proxy to users-service |
| ANY | `/api/posts[/...]` | JWT | Rate-limited (500/60s), circuit-breaker-protected proxy to posts-service |

### users-service (`http://localhost:8101`, normally reached via the gateway)

| Method | Path | Description |
|---|---|---|
| POST | `/users` | Register a user (email, username, password) |
| GET | `/users/{id}` | Fetch a user |
| GET | `/users` | List users (paginated) |
| GET | `/health` | Liveness + DB connectivity |

### posts-service (`http://localhost:8102`, normally reached via the gateway)

| Method | Path | Description |
|---|---|---|
| POST | `/posts` | Create a post (user_id, title, content) |
| GET | `/posts/{id}` | Fetch a post |
| GET | `/posts` | List posts (paginated, filterable by `user_id`) |
| DELETE | `/posts/{id}` | Delete a post |
| GET | `/health` | Liveness + DB connectivity |

## Design decisions & trade-offs

The source PRD describes a larger system than what's built here; each deviation below is
deliberate, not an oversight, and is called out for anyone comparing this repo against the PRD:

- **2 downstream services, not "5+".** The PRD's own success metric asks for routing across 5+
  services. Two real, independently-databased FastAPI services (users, posts) are enough to
  demonstrate genuine proxying, circuit breaking per service, and cross-service tracing — adding
  three more near-identical CRUD stubs would inflate the file count without adding a new pattern.
- **ELK dropped in favor of structured JSON logs + correlation IDs.** The gateway emits one JSON
  log line per request (`correlation_id`, `method`, `path`, `status`, `latency_ms`) to stdout — a
  drop-in input for any log aggregator, without running Elasticsearch/Logstash/Kibana for a
  portfolio-sized deployment.
- **`/services/health` was added, not in the PRD's sample code.** The PRD's own dashboard fetches
  this endpoint, but the PRD's Flask sample never defines it. It's implemented here as a live
  aggregation of both downstream services' `/health` endpoints.
- **JWT auth was added, despite the PRD's sample code omitting it.** The PRD's architecture diagram
  shows a JWT auth stage that the accompanying code never implements. It's implemented here:
  `/auth/register` and `/auth/login` issue tokens (PyJWT, bcrypt-hashed passwords), and
  `/api/users/*` / `/api/posts/*` require a valid bearer token.
- **The gateway keeps its own small credentials table, separate from users-service's business
  data.** `gateway_users` (email + password hash) lets the gateway issue/validate JWTs
  independently of users-service's availability. Registration best-effort syncs a matching business
  record to users-service; if that service is briefly unreachable, local auth still works and the
  records are correlated later by email — this is a real, working example of the resilience the
  circuit breaker is meant to provide, not just a slogan.
- **OTLP/HTTP exporter, not the PRD's thrift-based `JaegerExporter`.** The PRD's sample imports
  `opentelemetry.exporter.jaeger.thrift`, which is on a legacy path in current OpenTelemetry
  releases. This project exports via OTLP/HTTP directly to Jaeger's OTLP receiver instead, which is
  the currently recommended integration and was verified end-to-end (see Testing below).
  Tracing setup is wrapped defensively everywhere — an unreachable collector logs a warning and
  never prevents the app from starting.
- **`Base.metadata.create_all()` instead of Alembic migrations.** Each service owns a single, small
  table with no schema evolution needs at this scope. A production service handling real schema
  changes would use Alembic instead.
- **Frontend links out to the Jaeger UI rather than embedding trace data.** Jaeger's query API
  doesn't send permissive CORS headers by default, so pulling trace JSON directly into the
  dashboard would need a reverse-proxy just to work around a networking detail unrelated to the
  gateway itself. The dashboard instead surfaces live metrics and service health in-page, with a
  direct link to Jaeger for trace inspection.
- **Gateway's downstream request path preserves the resource prefix.** `/api/posts/<id>` forwards
  to `{POSTS_SERVICE_URL}/posts/<id>`, not a bare `/<id>` — matching how each FastAPI service
  actually mounts its routes. (This was caught and fixed by actually running the stack and hitting
  it with real requests — see Testing.)

## Testing

Every claim in this README was verified by actually running the stack, not just reading the code:

- **Unit + integration tests, run locally:** gateway 26/26 passing (pytest, fakeredis in place of a
  real Redis, in-memory SQLite), users-service 6/6, posts-service 8/8 (both against in-memory
  SQLite locally; CI runs them against a real Postgres service container). Frontend: 9/9 Vitest
  tests (the Prometheus text-format parser and `LoginForm`), plus a clean `tsc -b && vite build`
  and `eslint .`.
- **`docker compose up --build`** was run for real: all nine containers reach a healthy state.
- **Live API calls against the running stack:** registered a user (created a JWT + synced a
  business record to users-service), logged in, created/listed/fetched a post through the
  authenticated gateway proxy.
- **Rate limiting:** 520 concurrent requests against a 500/60s-limited route returned exactly 500
  `200`s and 20 real `429`s.
- **Circuit breaking:** stopping `posts-service` and hitting its proxy route produced real `503`s;
  once the breaker opened, failing requests returned in ~60-90ms instead of hanging for the full
  5s downstream timeout. Restarting the service and re-checking `/services/health` confirmed a
  clean recovery.
- **Tracing:** Jaeger reports all three services (`api-gateway`, `users-service`,
  `posts-service`); a single trace for `POST /api/posts` spans the gateway request, the proxied
  call, the FastAPI handler, and the SQL insert — real cross-service context propagation, not a
  demo of the gateway in isolation.
- **Metrics:** Prometheus's target list shows `api-gateway` as `up`, and
  `gateway_requests_total` returns real, non-zero series.
- **Gateway overhead, measured (not the PRD's aspirational "<10ms"):** 20 sequential GETs directly
  against users-service averaged ~9.2ms; the same route through the authenticated gateway proxy
  averaged ~11.1ms — roughly 2ms of real, measured overhead for auth + rate-limit check + proxy
  hop, on this dev machine.

To run the test suites yourself:

```bash
# Gateway
cd backend && pip install -r requirements-dev.txt && pytest --cov=core --cov=routes

# Each microservice
cd services/users-service && pip install -r requirements-dev.txt && pytest --cov=app
cd services/posts-service && pip install -r requirements-dev.txt && pytest --cov=app

# Frontend
cd frontend && npm install && npm test
```

## Project layout

```
flask-microservice-api-gateway/
├── backend/                  # Flask API gateway
│   ├── app.py                 # App factory: logging, tracing, metrics, blueprint wiring
│   ├── core/
│   │   ├── security.py        # JWT create/decode, password hashing, require_auth decorator
│   │   ├── rate_limit.py       # Redis-backed rate-limit decorator
│   │   ├── circuit.py          # Circuit-breaker-wrapped downstream HTTP client
│   │   ├── db.py / models.py   # Gateway's own credentials table
│   ├── routes/
│   │   ├── auth.py             # /auth/register, /auth/login
│   │   ├── proxy.py            # /api/users/*, /api/posts/*
│   │   └── health.py           # /health, /services/health
│   └── tests/
├── services/
│   ├── users-service/          # FastAPI + Postgres
│   └── posts-service/          # FastAPI + Postgres
├── frontend/                  # React + TypeScript + Vite + Tailwind dashboard
│   └── src/
│       ├── components/        # LoginForm, GatewayDashboard
│       └── lib/                # API client, Prometheus text-format parser
├── docker-compose.yml
├── prometheus.yml
└── .github/workflows/ci.yml
```

## License

MIT — see [LICENSE](LICENSE).

## Credits

Developed by Kabilesh Rajaselvan with contributions from Jennita S.
