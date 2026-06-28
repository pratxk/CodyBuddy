import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.enhance import router as enhance_router
from api.generate import router as generate_router, shutdown_executor
from api.projects import router as projects_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from db.database import create_tables
        create_tables()
        logger.info("DB tables ensured")
    except Exception as exc:  # noqa: BLE001  ponytail: DB hiccup must not stop boot
        logger.error("create_tables failed (non-fatal): %s", exc)
    yield
    shutdown_executor()


app = FastAPI(title="CodyBuddy Studio API", version="0.1.0", lifespan=lifespan)

_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate_router, prefix="/api")
app.include_router(enhance_router, prefix="/api")
app.include_router(projects_router, prefix="/api")


@app.get("/api/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "service": "CodyBuddy Studio API"}


if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)
