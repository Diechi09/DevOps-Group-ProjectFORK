"""
Custom middleware for FastAPI application
Structured logging for all requests and responses
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time
import logging
from typing import Dict, Any
from app.telemetry import telemetry_client

# Configure structured logging
logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests with structured payloads"""

    async def dispatch(self, request: Request, call_next):
        # Record start time
        start_time = time.time()
        endpoint = str(request.url.path)
        method = request.method
        status_code = 200

        try:
            # Process request
            response = await call_next(request)
            status_code = response.status_code

            # Calculate duration in milliseconds
            duration_ms = (time.time() - start_time) * 1000

            # Build structured log payload
            log_payload: Dict[str, Any] = {
                "endpoint": endpoint,
                "method": method,
                "status": status_code,
                "duration_ms": round(duration_ms, 2),
            }

            # Add error message if status code indicates error
            # The exception handlers will format the error response,
            # but we log the error details here for monitoring
            if status_code >= 400:
                # For structured logging, we log the status code as error indicator
                log_payload["error"] = f"HTTP {status_code}"
                logger.warning("Request completed with error", extra=log_payload)
            else:
                logger.info("Request processed", extra=log_payload)

            telemetry_client.record_request(
                duration_ms=duration_ms,
                status_code=status_code,
                endpoint=endpoint,
                method=method,
            )

            # Add process time to response headers
            response.headers["X-Process-Time"] = str(round(duration_ms, 2))

            return response

        except Exception as exc:
            # Catch any unhandled exceptions (should be rare with exception handlers)
            status_code = 500
            duration_ms = (time.time() - start_time) * 1000
            error_message = str(exc)

            # Log structured error payload
            log_payload = {
                "endpoint": endpoint,
                "method": method,
                "status": status_code,
                "duration_ms": round(duration_ms, 2),
                "error": error_message,
            }
            logger.error("Unhandled exception in middleware", extra=log_payload, exc_info=True)

            telemetry_client.record_request(
                duration_ms=duration_ms,
                status_code=status_code,
                endpoint=endpoint,
                method=method,
            )

            # Re-raise to let exception handlers deal with it
            raise


class CORSMiddleware(BaseHTTPMiddleware):
    """Custom CORS middleware (or use FastAPI's built-in)"""

    def __init__(self, app, allow_origins: list[str] = ["*"]):
        super().__init__(app)
        self.allow_origins = allow_origins

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        origin = request.headers.get("origin")
        if "*" in self.allow_origins or (origin and origin in self.allow_origins):
            response.headers["Access-Control-Allow-Origin"] = origin or "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"

        return response
