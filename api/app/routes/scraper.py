"""
Scraper API routes for triggering price updates from supermarkets.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.config import settings
from app.db import get_db
from app.services.scraper_service import ScraperService
from app.telemetry import telemetry_client
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class ScrapeRequest(BaseModel):
    """Request body for scraping specific products"""

    queries: Optional[List[str]] = None


class ScrapeResponse(BaseModel):
    """Response from scrape operation"""

    status: str
    message: str
    total_products_updated: int = 0
    queries_processed: int = 0
    errors: List[dict] = []
    products: List[dict] = []


# Track if a scrape is in progress
_scrape_in_progress = False


@router.post("/trigger", response_model=ScrapeResponse)
async def trigger_scrape(request: Optional[ScrapeRequest] = None, db: Session = Depends(get_db)):
    """
    Trigger a price scrape from Mercadona.

    If no queries are provided, scrapes common grocery items.
    This is a synchronous operation - waits for scraping to complete.

    Note: Requires Playwright browsers to be installed.
    Run: playwright install chromium
    """
    global _scrape_in_progress

    if _scrape_in_progress:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A scrape operation is already in progress"
        )

    try:
        _scrape_in_progress = True
        service = ScraperService(db)

        queries = request.queries if request else None
        results = await service.scrape_all_products(queries)

        return ScrapeResponse(
            status="completed",
            message=f"Successfully processed {results['queries_processed']} queries",
            total_products_updated=results["total_products_updated"],
            queries_processed=results["queries_processed"],
            errors=results["errors"],
            products=results["products"],
        )
    except Exception as e:
        logger.error(f"Scrape failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Scrape failed: {str(e)}"
        )
    finally:
        _scrape_in_progress = False


@router.post("/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh_prices(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Background refresh endpoint to resync product data."""

    global _scrape_in_progress

    if _scrape_in_progress:
        telemetry_client.record_refresh(success=False)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A scrape operation is already in progress",
        )

    if settings.app_env == "test":
        telemetry_client.record_refresh(success=True)
        return {
            "status": "queued",
            "message": "Refresh skipped in test environment.",
        }

    background_tasks.add_task(_run_background_scrape, db, None)
    telemetry_client.record_refresh(success=True)

    return {
        "status": "queued",
        "message": "Refresh started in background. Check /scraper/status for progress.",
    }


async def _run_background_scrape(db: Session, queries: Optional[List[str]]):
    """Background task for scraping"""
    global _scrape_in_progress
    try:
        _scrape_in_progress = True
        service = ScraperService(db)
        await service.scrape_all_products(queries)
        logger.info("Background scrape completed")
    except Exception as e:
        logger.error(f"Background scrape failed: {e}")
    finally:
        _scrape_in_progress = False


@router.post("/trigger-async", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scrape_async(
    background_tasks: BackgroundTasks,
    request: Optional[ScrapeRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Trigger a background price scrape from Mercadona.

    Returns immediately with 202 Accepted.
    Check /scraper/status for progress.
    """
    global _scrape_in_progress

    if _scrape_in_progress:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A scrape operation is already in progress"
        )

    queries = request.queries if request else None
    background_tasks.add_task(_run_background_scrape, db, queries)

    return {
        "status": "started",
        "message": "Scrape started in background. Check /scraper/status for progress.",
    }


@router.get("/status")
async def scrape_status():
    """Check if a scrape is currently in progress"""
    return {
        "in_progress": _scrape_in_progress,
        "message": "Scrape is running" if _scrape_in_progress else "No scrape in progress",
    }


@router.post("/search/{query}")
async def search_product(query: str, db: Session = Depends(get_db)):
    """
    Search and scrape a specific product from Mercadona.
    Updates the database with found prices.

    Example: POST /scraper/search/leche
    """
    try:
        service = ScraperService(db)
        results = await service.scrape_mercadona_product(query)

        if not results:
            return {
                "status": "no_results",
                "message": f"No products found for: {query}",
                "products": [],
            }

        return {
            "status": "success",
            "message": f"Found {len(results)} products",
            "products": results,
        }
    except Exception as e:
        logger.error(f"Search failed for {query}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Search failed: {str(e)}"
        )
