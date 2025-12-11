"""
Pytest configuration and fixtures for testing
"""

import pytest
import os
import tempfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Set test environment BEFORE importing any app modules
os.environ["SQL_CONNECTION_STRING"] = "sqlite:///:memory:"
os.environ["APP_ENV"] = "test"

# Now import app modules
from fastapi import Request, HTTPException, status  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from app.db import Base, get_db  # noqa: E402
from app.models import Product, Supermarket, Price  # noqa: E402
from app.config import settings  # noqa: E402
from app.routes import health, products, supermarkets, prices, compare, scraper  # noqa: E402
from app.middleware import LoggingMiddleware  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware as FastAPICORSMiddleware  # noqa: E402


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


# Compatibility constants for root-level tests (tests/test_prices.py)
PRODUCT_COUNT = 10
SUPERMARKET_COUNT = 3
PRICE_COUNT = 27


# Use a temporary file-based SQLite database to avoid threading issues
# In-memory SQLite databases are not shared across threads
_test_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
TEST_DATABASE_URL = f"sqlite:///{_test_db_file.name}"


def create_test_app():
    """Create a test FastAPI app"""
    test_app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )

    # Add middleware
    test_app.add_middleware(LoggingMiddleware)
    test_app.add_middleware(
        FastAPICORSMiddleware,
        allow_origins=settings.allowed_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers (matching main.py)
    @test_app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle validation errors (422)"""
        errors = exc.errors()
        error_messages = [f"{error['loc']}: {error['msg']}" for error in errors]
        message = "; ".join(error_messages) if error_messages else "Validation error"
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "UnprocessableEntity", "message": message},
        )

    @test_app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions with structured error responses"""
        error_type = _get_error_type(exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": error_type, "message": exc.detail},
        )

    @test_app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions (500)"""
        error_detail = "Internal server error" if not settings.debug else str(exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "InternalServerError", "message": error_detail},
        )

    # Include routers
    test_app.include_router(health.router, tags=["Health"])
    test_app.include_router(
        supermarkets.router, prefix=f"{settings.api_prefix}/supermarkets", tags=["Supermarkets"]
    )
    test_app.include_router(
        products.router, prefix=f"{settings.api_prefix}/products", tags=["Products"]
    )
    test_app.include_router(prices.router, prefix=f"{settings.api_prefix}/prices", tags=["Prices"])
    test_app.include_router(
        compare.router, prefix=f"{settings.api_prefix}/compare", tags=["Compare"]
    )
    test_app.include_router(scraper.router, prefix=f"{settings.api_prefix}/scraper", tags=["Scraper"])

    @test_app.get("/")
    async def root():
        return {
            "message": "Welcome to Product Comparison API",
            "version": settings.app_version,
            "docs": "/docs",
        }

    return test_app


# Create test app
app = create_test_app()


@pytest.fixture(scope="function")
def test_db():
    """
    Create a test database for each test function
    Uses file-based SQLite database to avoid threading issues with TestClient
    """
    # Create a new temporary file for each test to ensure isolation
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_url = f"sqlite:///{db_file.name}"

    # Create test engine with check_same_thread=False to allow cross-thread access
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    # Create all tables using Base from app.db
    Base.metadata.create_all(bind=engine)

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        # Clean up temp file
        try:
            os.unlink(db_file.name)
        except Exception:
            pass


@pytest.fixture(scope="function")
def test_client(test_db):
    """
    Create a test client with test database dependency override
    Uses the same engine/session factory as test_db to ensure consistency
    """
    # Get the bind (engine) from the test_db session
    engine = test_db.get_bind()

    # Create a new session factory bound to the same engine
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def seed_test_data(test_db):
    """
    Seed test database with 3 products × 3 stores
    Returns dict with created objects for easy access in tests
    """
    # Create 3 products
    products = [
        Product(name="Milk", category="Dairy"),
        Product(name="Bread", category="Bakery"),
        Product(name="Eggs", category="Dairy"),
    ]
    for product in products:
        test_db.add(product)
    test_db.commit()

    # Refresh to get IDs
    for product in products:
        test_db.refresh(product)

    # Create 3 supermarkets
    supermarkets = [
        Supermarket(name="Walmart", city="New York"),
        Supermarket(name="Target", city="New York"),
        Supermarket(name="Kroger", city="New York"),
    ]
    for supermarket in supermarkets:
        test_db.add(supermarket)
    test_db.commit()

    # Refresh to get IDs
    for supermarket in supermarkets:
        test_db.refresh(supermarket)

    # Create prices: 3 products × 3 stores = 9 prices
    # Product 1 (Milk): $2.99, $2.49, $2.79
    # Product 2 (Bread): $1.99, $2.19, $1.89
    # Product 3 (Eggs): $3.49, $3.29, $3.69
    prices = [
        # Milk prices
        Price(product_id=products[0].id, store_id=supermarkets[0].id, price=2.99),
        Price(product_id=products[0].id, store_id=supermarkets[1].id, price=2.49),  # Cheapest
        Price(product_id=products[0].id, store_id=supermarkets[2].id, price=2.79),
        # Bread prices
        Price(product_id=products[1].id, store_id=supermarkets[0].id, price=1.99),
        Price(product_id=products[1].id, store_id=supermarkets[1].id, price=2.19),
        Price(product_id=products[1].id, store_id=supermarkets[2].id, price=1.89),  # Cheapest
        # Eggs prices
        Price(product_id=products[2].id, store_id=supermarkets[0].id, price=3.49),
        Price(product_id=products[2].id, store_id=supermarkets[1].id, price=3.29),  # Cheapest
        Price(product_id=products[2].id, store_id=supermarkets[2].id, price=3.69),
    ]
    for price in prices:
        test_db.add(price)
    test_db.commit()

    return {"products": products, "supermarkets": supermarkets, "prices": prices}
