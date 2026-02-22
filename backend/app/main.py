"""Main FastAPI application"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from datetime import datetime
from pathlib import Path
import logging
import traceback
import time
import uuid

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

from app.config import settings
from app.core.database import init_db, SessionLocal
from app.core.exceptions import BaseAPIException
from app.api.v1 import auth, users, challenges, submissions, drafts, admin, terminal
from app.services.submission_worker import submission_worker

# Configure logging - ensure log directory exists
_log_dir = Path(settings.get_log_file()).parent
_log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.get_log_file()),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

REQUEST_COUNT = Counter(
    "codeclash_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "codeclash_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)
QUEUE_DEPTH_GAUGE = Gauge("codeclash_submission_queue_depth", "Number of queued submissions")
WORKER_UP_GAUGE = Gauge("codeclash_worker_up", "Worker liveness (1 running, 0 stopped)")

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None
)

# GZip compression for large responses
app.add_middleware(GZipMiddleware, minimum_size=500)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security headers + request timing middleware
@app.middleware("http")
async def add_headers_and_timing(request: Request, call_next):
    """Add security headers and log slow requests"""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Request-ID"] = request_id

    REQUEST_COUNT.labels(request.method, request.url.path, str(response.status_code)).inc()
    REQUEST_LATENCY.labels(request.method, request.url.path).observe(duration)

    if duration > 1.0:
        logger.warning(
            "Slow request: %s %s took %.2fs request_id=%s",
            request.method,
            request.url.path,
            duration,
            request_id,
        )

    return response


# Exception handlers
@app.exception_handler(BaseAPIException)
async def api_exception_handler(request: Request, exc: BaseAPIException):
    """Handle custom API exceptions"""
    logger.error(
        f"API Exception: {exc.message}",
        extra={
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.message,
            "details": exc.details,
            "path": request.url.path,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(
        f"Validation error: {errors}",
        extra={"path": request.url.path, "method": request.method}
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "Validation failed",
            "details": errors,
            "path": request.url.path,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handle database errors"""
    logger.error(
        f"Database error: {str(exc)}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "traceback": traceback.format_exc()
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "A database error occurred. Please try again later.",
            "path": request.url.path,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions"""
    logger.critical(
        f"Unhandled exception: {str(exc)}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "traceback": traceback.format_exc()
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "An unexpected error occurred. Our team has been notified.",
            "path": request.url.path,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    settings.validate_security_settings()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    # Initialize database
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Create admin user if doesn't exist
    try:
        from app.core.database import SessionLocal
        from app.services.user_service import user_service
        from app.schemas.user import UserCreate, UserRole
        
        db = SessionLocal()
        try:
            admin = user_service.get_user_by_username(db, settings.ADMIN_USERNAME)
            if not admin:
                user_service.create_user(
                    db,
                    UserCreate(
                        username=settings.ADMIN_USERNAME,
                        password=settings.ADMIN_PASSWORD,
                        role=UserRole.ADMIN
                    )
                )
                logger.info(f"Created admin user: {settings.ADMIN_USERNAME}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to create admin user: {e}")

    if settings.RUN_EMBEDDED_WORKER:
        submission_worker.start()
        WORKER_UP_GAUGE.set(1)


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if submission_worker.is_running():
        submission_worker.stop()
    WORKER_UP_GAUGE.set(0)
    logger.info(f"Shutting down {settings.APP_NAME}")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    db_ok = True
    db_error = None
    queue_depth = 0
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        queue_depth = submission_worker.queue_depth(db)
    except Exception as exc:
        db_ok = False
        db_error = str(exc)
    finally:
        db.close()

    QUEUE_DEPTH_GAUGE.set(queue_depth)
    worker_status = submission_worker.status()
    WORKER_UP_GAUGE.set(1 if worker_status["running"] else 0)

    return {
        "status": "healthy" if db_ok else "degraded",
        "version": settings.APP_VERSION,
        "timestamp": datetime.utcnow().isoformat(),
        "readiness": {
            "database": {"ok": db_ok, "error": db_error},
            "worker": worker_status,
            "queue_depth": queue_depth,
        },
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/api/docs" if settings.DEBUG else "disabled"
    }


# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(challenges.router, prefix="/api/v1/challenges", tags=["Challenges"])
app.include_router(submissions.router, prefix="/api/v1/submissions", tags=["Submissions"])
app.include_router(drafts.router, prefix="/api/v1/drafts", tags=["Drafts"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(terminal.router, prefix="/api/v1/terminal", tags=["Terminal"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS
    )
