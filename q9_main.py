import time
import uuid
from fastapi import FastAPI, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TOTAL_ORDERS = 52
RATE_LIMIT_R = 15
RATE_LIMIT_WINDOW_SECONDS = 10

idempotency_store = {}
rate_buckets = {}


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_id = request.headers.get("x-client-id", "anonymous")
    now = time.time()

    bucket = rate_buckets.setdefault(client_id, [])
    bucket[:] = [t for t in bucket if now - t < RATE_LIMIT_WINDOW_SECONDS]

    if len(bucket) >= RATE_LIMIT_R:
        return JSONResponse(
            status_code=429,
            content={"error": "rate limit exceeded"},
            headers={"Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)},
        )

    bucket.append(now)
    return await call_next(request)


@app.post("/orders")
async def create_order(
    request: Request,
    idempotency_key: str = Header(None, alias="Idempotency-Key"),
):
    if idempotency_key and idempotency_key in idempotency_store:
        return JSONResponse(status_code=201, content=idempotency_store[idempotency_key])

    order_id = str(uuid.uuid4())
    order = {"id": order_id}

    if idempotency_key:
        idempotency_store[idempotency_key] = order

    return JSONResponse(status_code=201, content=order)


@app.get("/orders")
async def list_orders(limit: int = 10, cursor: str = None):
    start = int(cursor) if cursor else 0
    start = max(0, start)

    all_ids = list(range(1, TOTAL_ORDERS + 1))
    page_ids = all_ids[start : start + limit]

    next_start = start + limit
    next_cursor = str(next_start) if next_start < TOTAL_ORDERS else None

    return {
        "items": [{"id": i} for i in page_ids],
        "next_cursor": next_cursor,
    }


@app.get("/")
async def root():
    return {"status": "ok", "endpoints": ["POST /orders", "GET /orders"]}
