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

- **Auth**: `POST /api/auth/token` returns a 30-minute HS256 JWT. The token's
  `sub` is the user id and its `userType` claim (`host` or `tourist`) decides
  which page the UI routes to after login.
- **Listings**: CRUD over property documents. Every write is authenticated.
- **Bookings**: search excludes any property whose `booking_history` overlaps
  the requested dates; reserving appends to that history and records the trip on
  the user.
- **Redis**: every request pushes a one-line activity message onto a list that
  [backend/app/util/consume_redis.py](backend/app/util/consume_redis.py) drains.
  It is a side channel: if Redis is unreachable the request still succeeds and a
  warning is logged.

---

## Prerequisites

- Python 3.11
- Node 20
- MongoDB (local `mongod` or an Atlas cluster)
- Redis (optional, the API runs without it)

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
| `JWT_SECRET_KEY` | `dev-only-insecure-secret` | Token signing key, **must** be overridden outside development |
| `JWT_ALGORITHM` | `HS256` | Token signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token lifetime |
| `REDIS_HOST` / `REDIS_PORT` | `localhost` / `6379` | Activity queue |
| `REDIS_KEY` | `toWorkers` | Queue name |
| `CORS_ORIGINS` | `http://localhost,http://localhost:3000,http://lodgezilla.com` | Comma-separated allowed browser origins |
| `LOG_LEVEL` | `INFO` | `DEBUG` … `CRITICAL` |
| `LOG_FILE` | unset (stdout) | Log destination |
| `PORT` | `8000` | Port uvicorn binds |

Database and collection names are not environment variables; they live in
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

- Files are matched by prefix: `listings-{city}.csv` and `reviews-{city}.csv`.
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

39 tests need no external services: `conftest.py` swaps in `mongomock`
and `fakeredis` before the app is imported, so they run the same way
locally with nothing running as they do in CI. Four more tests race 24
simultaneous reservations against a real MongoDB and are skipped unless you
set `LODGEZILLA_TEST_MONGO_URI` (see [Double booking](#double-booking)). It used to need a real, hand-
seeded MongoDB and would silently *skip* instead of fail if login didn't
work, which is exactly the kind of thing that lets a real regression through
a CI gate looking green; that dependency is gone now.

### Double booking

`POST /bookings/reserve/{id}` used to push a booking without looking at the
existing ones, so the same dates could be sold twice, even one request after
the other. It also failed with a 500 on any listing created through the API,
because those have `booking_history: null` and MongoDB cannot `$push` onto
null. Both are fixed, and the dates are now checked (`YYYY-MM-DD`, end not
before start, otherwise 422).

The check and the write are one `find_one_and_update` whose filter only
matches a listing with no overlapping booking, so two requests cannot both
pass the check. An overlap answers 409. The handler is also a plain `def`
now, so FastAPI runs it on a worker thread and a database call no longer
blocks the event loop.

mongomock cannot say whether MongoDB really applies that update atomically, so
the race tests need a server:

```bash
docker run -d -p 27017:27017 mongo:7
LODGEZILLA_TEST_MONGO_URI=mongodb://localhost:27017 pytest tests/test_booking_concurrency.py
```

One of them is a control: the old unconditional push, through the same threads,
double-booked in all 15 rounds. CI runs these against a MongoDB service
container.

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
| `GET` | `/` | no | Health/landing string |
| `POST` | `/auth/token` | no | Log in (JSON body: `name`, `password`), returns a JWT |
| `POST` | `/auth/create` | no | Create a user |
| `GET` | `/listings/list` | no | All properties |
| `GET` | `/listings/list/{user_id}` | no | Properties owned by one host |
| `POST` | `/listings/add` | yes | Create a property |
| `PUT` | `/listings/update/{property_id}` | yes | Update a property |
| `DELETE` | `/listings/delete/{property_id}` | yes | Delete a property |
| `GET` | `/bookings/search?destination=&from_date=&to_date=` | no | Properties free over the range |
| `POST` | `/bookings/reserve/{property_id}` | yes | Reserve a property |

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
| `secrets.example.yaml` | Template for the secret above, do not commit real values |

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
- **A refused reservation is invisible in the UI.** The tourist page only logs a
  failed reservation to the console, so the new 409 reaches the browser but not
  the user.
- **Frontend test coverage is minimal.** `HostPage.test.js` is the only
  frontend test. It covers that one page's data flow, not the rest of the UI.
- **No rate limiting** on the login or signup routes.
- **No load-test results are recorded.** `tests/locust_scripts.py` is there to
  run, and the HPAs scale 1 to 5 pods at 50% CPU, but no throughput or uptime
  numbers have been measured.
- **Dependency pins are still 2023-era** (fastapi 0.104.1, pydantic 2.5.2).
  CI runs on Python 3.12 specifically because that's the newest interpreter
  they still have prebuilt wheels for, not because they've been reviewed for
  a newer major version.

## Security

- Passwords are hashed with Argon2id. An account that still has a plaintext
  password from the seed data is upgraded to a hash the next time it logs in.
- Login sends the name and password in a JSON body, not in the URL.
- `PUT` and `DELETE` on a listing return 403 unless the caller is the host who
  created it. Both cases have tests.
- Destination search escapes the input, so a search string is matched as text
  and never as a regex.
- The JWT secret, database URI and CORS origins come from the environment. The
  default secret is for local development only.

---

## Credits

Built by [Anirudh Maiya](https://github.com/AnirudhMaiya),
[Kushal Nagarajan](https://github.com/Kush2104), and
[Abhiram MV](https://github.com/ABHIRAM1234).
Listing data from [Inside Airbnb](http://insideairbnb.com/).

After the course ended, Abhiram added the password hashing, the ownership
checks, the offline test suite, CI, the nginx frontend image and the
docker-compose setup.
