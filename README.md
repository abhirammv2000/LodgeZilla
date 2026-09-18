# LodgeZilla

A short-term lodging marketplace. Hosts list properties, tourists search them by
destination and date range and reserve the ones that are free.

The stack is a FastAPI backend over MongoDB, a Create React App frontend, and a
Redis queue that carries an activity log to a worker. Kubernetes manifests for
the whole thing live in [deployments/](deployments/).

---

## Architecture

```
  React UI  ──HTTP/JWT──▶  FastAPI  ──▶  MongoDB   (listings + users)
 (port 3000)                (8000)   │
                                     └──▶  Redis   ──▶  consume_redis worker
                                          (queue)        (activity log)
```

- **Auth** — `POST /api/auth/token` returns a 30-minute HS256 JWT. The token's
  `sub` is the user id and its `userType` claim (`host` or `tourist`) decides
  which page the UI routes to after login.
- **Listings** — CRUD over property documents. Every write is authenticated.
- **Bookings** — search excludes any property whose `booking_history` overlaps
  the requested dates; reserving appends to that history and records the trip on
  the user.
- **Redis** — every request pushes a one-line activity message onto a list that
  [backend/app/util/consume_redis.py](backend/app/util/consume_redis.py) drains.
  It is a side channel: if Redis is unreachable the request still succeeds and a
  warning is logged.

---

## Prerequisites

- Python 3.11
- Node 20
- MongoDB (local `mongod` or an Atlas cluster)
- Redis (optional — the API runs without it)

---

## Running it locally

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # then edit it, see Configuration below
python run.py               # http://localhost:8000
```

Interactive API docs are served at <http://localhost:8000/docs>.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env        # only needed if the API is not on 127.0.0.1:8000
npm start                   # http://localhost:3000
```

### Activity-log worker

```bash
cd backend
python -m app.util.consume_redis
```

---

## Configuration

Both halves read configuration from the environment; neither carries a usable
secret in source. See `backend/.env.example` and `frontend/.env.example`.

### Backend

| Variable | Default | Purpose |
| --- | --- | --- |
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `JWT_SECRET_KEY` | `dev-only-insecure-secret` | Token signing key — **must** be overridden outside development |
| `JWT_ALGORITHM` | `HS256` | Token signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token lifetime |
| `REDIS_HOST` / `REDIS_PORT` | `localhost` / `6379` | Activity queue |
| `REDIS_KEY` | `toWorkers` | Queue name |
| `CORS_ORIGINS` | `http://localhost,http://localhost:3000,http://lodgezilla.com` | Comma-separated allowed browser origins |
| `LOG_LEVEL` | `INFO` | `DEBUG` … `CRITICAL` |
| `LOG_FILE` | unset (stdout) | Log destination |
| `PORT` | `8000` | Port uvicorn binds |

Database and collection names are not environment variables — they live in
[mongo_config.json](backend/app/config/mongo_config.json) so the API and the
ingest script cannot drift apart.

### Frontend

| Variable | Default | Purpose |
| --- | --- | --- |
| `REACT_APP_API_BASE_URL` | `http://127.0.0.1:8000/api` | Backend base URL |

Create React App inlines this at build time, so rebuild after changing it.

---

## Seeding the database

The app is seeded from [Inside Airbnb](http://insideairbnb.com/get-the-data/)
city exports, already checked in under `backend/app/data/`:

```bash
cd backend
python clean_and_ingest_data.py
```

This cleans the CSVs (strips HTML from descriptions, pulls the star rating out
of the listing name, demojizes review text), inserts listings and reviewers,
then randomly assigns each user a `host`/`tourist` role and gives every property
a host.

Two details worth knowing:

- Files are matched by prefix — `listings-{city}.csv` and `reviews-{city}.csv`.
  The Denver files are prefixed with `!`, so they are **skipped**; rename them to
  load Denver too.
- Reviewer accounts get randomly generated passwords that are printed nowhere.
  Create your own account through the UI's Sign Up form to log in.

---

## Tests

```bash
cd backend
pytest
```

19 tests, no external services required: `conftest.py` swaps in `mongomock`
and `fakeredis` before the app is imported, so the suite runs the same way
locally with nothing running as it does in CI. It used to need a real, hand-
seeded MongoDB and would silently *skip* instead of fail if login didn't
work, which is exactly the kind of thing that lets a real regression through
a CI gate looking green; that dependency is gone now.

Load testing:

```bash
cd backend
locust -f tests/locust_scripts.py --host http://localhost:8000
```

---

## API reference

All routes are prefixed `/api`. Locked routes require an
`Authorization: Bearer <token>` header.

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/` | — | Health/landing string |
| `POST` | `/auth/token` | — | Log in (JSON body: `name`, `password`), returns a JWT |
| `POST` | `/auth/create` | — | Create a user |
| `GET` | `/listings/list` | — | All properties |
| `GET` | `/listings/list/{user_id}` | — | Properties owned by one host |
| `POST` | `/listings/add` | yes | Create a property |
| `PUT` | `/listings/update/{property_id}` | yes | Update a property |
| `DELETE` | `/listings/delete/{property_id}` | yes | Delete a property |
| `GET` | `/bookings/search?destination=&from_date=&to_date=` | — | Properties free over the range |
| `POST` | `/bookings/reserve/{property_id}` | yes | Reserve a property |

The two `/listings/list` routes return a JSON-encoded *string* of JSON, so
clients parse the body twice. It is a wart, kept because the UI depends on it.

---

## Deployment

Images are built from `backend/Dockerfile` and `frontend/Dockerfile`:

```bash
docker build -t <registry>/backend_image:<tag> backend
docker build -t <registry>/frontend_image:<tag> frontend
```

Then, against a cluster with an nginx ingress controller and metrics-server:

```bash
# Create the secret the backend Deployment expects (see secrets.example.yaml)
kubectl create secret generic lodgezilla-secrets \
  --from-literal=mongo-uri='<your mongo uri>' \
  --from-literal=jwt-secret-key="$(openssl rand -hex 32)"

kubectl apply -f deployments/
```

| Manifest | Contents |
| --- | --- |
| `deploy_app.yaml` / `deploy_service.yaml` | Frontend Deployment + Service |
| `deploy_backend.yaml` / `deploy_service_backend.yaml` | Backend Deployment + Service |
| `deploy_redis.yaml` | Redis Deployment + ClusterIP Service |
| `ingress.yml` / `ingress_backend.yml` | Routes `/` to the UI and `/api` to the API |
| `frontend-hpa.yaml` / `backend-hpa.yaml` | Autoscale 1 to 5 pods at 50% CPU |
| `secrets.example.yaml` | Template for the secret above — do not commit real values |

Update the `image:` fields in the two Deployments to your own registry, and
build the frontend image with `REACT_APP_API_BASE_URL` pointed at the API's
public address.

---

## Project layout

```
backend/
  app/
    config/         settings.py (env-driven) + mongo_config.json
    data/           Inside Airbnb CSV exports
    db.py           shared MongoDB + Redis clients, activity queue helpers
    main.py         FastAPI app, CORS, logging
    model/          Pydantic models: Property, User
    routes/         auth, listings, bookings, home
    util/           helpers and the queue-draining worker
  tests/            pytest integration tests + locust script
  clean_and_ingest_data.py
  run.py
frontend/
  src/
    components/     LogoutButton, SignUp
    pages/          Login, HostPage, TouristPage
    services/       config.js (API base URL), AuthContext, per-domain API clients
deployments/        Kubernetes manifests
```

---

## Known limitations

This began as a course project, and a few things are demo-grade:

- **The JWT lives in React state only**, so a page refresh logs you out. There is
  no refresh-token flow, and no server-side revocation before a token's own
  30-minute expiry.
- **`/listings/list` returns every property** with no pagination. The frontend
  already paginates client-side (`TablePagination` in `HostPage.js`), but the
  whole collection still crosses the wire on every load, which won't hold up
  once there are enough listings for it to matter.
- **Frontend test coverage is minimal.** `HostPage.test.js` is the first
  frontend test in the repo (added alongside the double-encoding fix below) -
  it covers that one page's data flow, not the rest of the UI.
- **Dependency pins are still 2023-era** (fastapi 0.104.1, pydantic 2.5.2).
  CI runs on Python 3.12 specifically because that's the newest interpreter
  they still have prebuilt wheels for, not because they've been reviewed for
  a newer major version.

Fixed, not just documented:

- ~~Passwords are stored and compared in plaintext.~~ Hashed with Argon2id;
  an existing plaintext password from before this change is upgraded to a
  hash the next time that account logs in successfully.
- ~~Credentials travel as query parameters~~ on `POST /auth/token`. They are
  a JSON body now.
- ~~Search matches location by unanchored regex~~, both a correctness issue
  (a destination containing regex syntax matched as a pattern, not literal
  text) and a full-collection-scan DoS vector. Escaped now.
- ~~`/listings/list`'s response body was a JSON-encoded *string* of JSON~~,
  so the frontend had to `JSON.parse` it a second time. The backend now
  returns a plain array; `HostPage.js` parses it once, like any other
  fetch response.
- ~~No ownership checks.~~ Any authenticated user could update or delete any
  listing regardless of who owned it. `PUT`/`DELETE` on a listing now return
  403 unless the caller is the host that created it.
- ~~No CI/CD pipeline.~~ `.github/workflows/ci.yml` runs the backend test
  suite plus a `ruff` lint pass, and builds the frontend, on every push.
- ~~The frontend's "production" Docker image ran the CRA dev server.~~ It's
  a proper multi-stage build now: compile the static bundle, serve it with
  nginx.
- ~~No local dev environment short of four manually-started processes.~~
  `docker-compose.yml` brings up MongoDB, Redis, the backend and the
  frontend together.

---

## Credits

Built by [Anirudh Maiya](https://github.com/AnirudhMaiya),
[Kushal Nagarajan](https://github.com/Kush2104), and
[Abhiram MV](https://github.com/ABHIRAM1234).
Listing data from [Inside Airbnb](http://insideairbnb.com/).
