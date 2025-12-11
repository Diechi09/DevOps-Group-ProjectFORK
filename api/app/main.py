"""
FastAPI main application file
"""

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware as FastAPICORSMiddleware
from app.config import settings
from app.db import engine, Base
from app.middleware import LoggingMiddleware
from app.routes import health, products, supermarkets, prices, compare, scraper
from app.telemetry import telemetry_client, get_connection_string
import logging

# Application Insights imports (optional - graceful fallback if not available)
try:
    from opencensus.ext.azure.trace_exporter import AzureExporter
    from opencensus.ext.fastapi.fastapi_middleware import FastAPIMiddleware
    from opencensus.trace.samplers import ProbabilitySampler

    OPENCENSUS_AVAILABLE = True
except ImportError:
    OPENCENSUS_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Database migrations are managed via Alembic
# In production: migrations are run by start.sh before the app starts
# In development: run `alembic upgrade head` manually or use start.sh
# In tests: tables are created by conftest.py using create_all()
if settings.app_env == "development":
    # In development, optionally create tables if migrations haven't been run
    # This is a fallback for local development convenience
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables ensured (development mode)")
    except Exception as e:
        logger.warning(f"Could not create tables: {e}")

# Initialize FastAPI app
# OpenAPI is automatically enabled by FastAPI (available at /docs, /redoc, /openapi.json)
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

# Add logging middleware for structured request/response logging
app.add_middleware(LoggingMiddleware)

# Add CORS middleware
# Use allowed_cors_origins property to support environment variable configuration
app.add_middleware(
    FastAPICORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Application Insights telemetry middleware
APPINSIGHTS_KEY = get_connection_string()
if APPINSIGHTS_KEY and OPENCENSUS_AVAILABLE:
    try:
        app.add_middleware(
            FastAPIMiddleware,
            exporter=AzureExporter(connection_string=APPINSIGHTS_KEY),
            sampler=ProbabilitySampler(1.0),  # Sample 100% of requests
        )
        logger.info("Application Insights telemetry enabled")
    except Exception as e:
        logger.warning(f"Failed to initialize Application Insights: {e}")
elif not APPINSIGHTS_KEY:
    logger.info("Application Insights disabled (no APPINSIGHTS_INSTRUMENTATIONKEY set)")
elif not OPENCENSUS_AVAILABLE:
    logger.warning("Application Insights disabled (opencensus packages not installed)")


# Exception handlers for structured error responses
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors (422)"""
    errors = exc.errors()
    error_messages = [f"{error['loc']}: {error['msg']}" for error in errors]
    message = "; ".join(error_messages) if error_messages else "Validation error"

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "UnprocessableEntity", "message": message},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with structured error responses"""
    error_type = _get_error_type(exc.status_code)

    return JSONResponse(
        status_code=exc.status_code, content={"error": error_type, "message": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions (500)"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)

    error_detail = "Internal server error" if not settings.debug else str(exc)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "InternalServerError", "message": error_detail},
    )


def _get_error_type(status_code: int) -> str:
    """Map status code to error type"""
    error_types = {
        400: "BadRequest",
        401: "Unauthorized",
        403: "Forbidden",
        404: "NotFound",
        422: "UnprocessableEntity",
        500: "InternalServerError",
        502: "BadGateway",
        503: "ServiceUnavailable",
    }
    return error_types.get(status_code, "Error")


# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(
    supermarkets.router, prefix=f"{settings.api_prefix}/supermarkets", tags=["Supermarkets"]
)
app.include_router(products.router, prefix=f"{settings.api_prefix}/products", tags=["Products"])
app.include_router(prices.router, prefix=f"{settings.api_prefix}/prices", tags=["Prices"])
app.include_router(compare.router, prefix=f"{settings.api_prefix}/compare", tags=["Compare"])
app.include_router(scraper.router, prefix=f"{settings.api_prefix}/scraper", tags=["Scraper"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Product Comparison API",
        "version": settings.app_version,
        "docs": "/docs",
    }
