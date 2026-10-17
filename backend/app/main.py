from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from .database import init_db
from .config import PRICE_CHECK_INTERVAL_MINUTES
from .schemas import ProductCreate, ProductUpdate
from . import agent
from .claude_service import summarize_product

scheduler = BackgroundScheduler(daemon=True)

def scheduled_checks():
    for product in agent.list_products():
        try: agent.check_product(product["id"])
        except Exception: continue

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if not scheduler.running:
        scheduler.add_job(scheduled_checks, "interval", minutes=PRICE_CHECK_INTERVAL_MINUTES,
                          id="price_checks", replace_existing=True, max_instances=1, coalesce=True)
        scheduler.start()
    yield
    if scheduler.running: scheduler.shutdown(wait=False)

app = FastAPI(title="Price Tracker Agent API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173","http://127.0.0.1:5173","http://localhost:5174"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/api/health")
def health(): return {"status":"ok","scheduler_interval_minutes":PRICE_CHECK_INTERVAL_MINUTES}

@app.get("/api/products")
def products(): return agent.list_products()

@app.post("/api/products")
def create_product(payload: ProductCreate):
    try: return agent.add_product(str(payload.url), payload.target_price, payload.title)
    except Exception as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc

@app.post("/api/products/{product_id}/check")
def check_product(product_id: int):
    try: return agent.check_product(product_id)
    except LookupError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc: raise HTTPException(status_code=502, detail=str(exc)) from exc

@app.get("/api/products/{product_id}/history")
def product_history(product_id: int):
    if not agent.get_product(product_id): raise HTTPException(status_code=404, detail="Product not found.")
    return agent.history(product_id)

@app.patch("/api/products/{product_id}/target")
def set_target(product_id: int, payload: ProductUpdate):
    product = agent.update_target(product_id, payload.target_price)
    if not product: raise HTTPException(status_code=404, detail="Product not found.")
    return product

@app.delete("/api/products/{product_id}")
def remove_product(product_id: int):
    if not agent.delete_product(product_id): raise HTTPException(status_code=404, detail="Product not found.")
    return {"deleted":True}

@app.post("/api/products/{product_id}/insights")
def product_insights(product_id: int):
    try: return {"summary": summarize_product(product_id)}
    except LookupError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc: raise HTTPException(status_code=503, detail=str(exc)) from exc
