import os
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.conversation_messages import router as conversation_messages_router
from app.api.v1.routes.conversations import router as conversations_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.knowledge import router as knowledge_router
from app.api.v1.routes.memories import router as memories_router
from app.api.v1.routes.memory import router as memory_router
from app.api.v1.routes.organizations import router as organizations_router
from app.api.v1.routes.projects import router as projects_router
from app.api.v1.routes.tasks import router as tasks_router
import importlib
import sys
from pathlib import Path

from app.core.exceptions import EnterpriseException, enterprise_exception_handler
from app.middleware.request_context import RequestContextMiddleware
from app.logging_utils import get_logger
from settings import get_settings

backend_root = Path(__file__).resolve().parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

importlib.import_module("logging")

settings = get_settings()
logger = get_logger("tetracrest")

start_time = time.time()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="TetraCrest Enterprise Intelligence Operating System",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(RequestContextMiddleware)
app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(organizations_router, prefix=settings.api_prefix)
app.include_router(projects_router, prefix=settings.api_prefix)
app.include_router(knowledge_router, prefix=settings.api_prefix)
app.include_router(memory_router, prefix=settings.api_prefix)
app.include_router(tasks_router, prefix=settings.api_prefix)
app.include_router(memories_router, prefix=settings.api_prefix)
app.include_router(conversations_router, prefix=settings.api_prefix)
app.include_router(conversation_messages_router, prefix=settings.api_prefix)


@app.exception_handler(EnterpriseException)
async def handle_enterprise_exception(request: Request, exc: EnterpriseException):
    return enterprise_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    logger.info("request_received", extra={"path": request.url.path, "method": request.method})
    response = await call_next(request)
    logger.info("request_completed", extra={"status_code": response.status_code})
    return response


@app.get("/")
async def root() -> dict:
    return {"message": "TetraCrest Enterprise Intelligence Operating System"}
