import os
import json
import logging
from fastapi import APIRouter, HTTPException
from pathlib import Path

router = APIRouter(
    prefix="/api/v1/metrics",
    tags=["metrics"],
)

logger = logging.getLogger(__name__)

# Locate the metrics file relative to this file
BASE_DIR = Path(__file__).parent.parent.parent
METRICS_PATH = BASE_DIR / "data" / "model_metrics.json"

@router.get("/")
async def get_metrics():
    """
    Get machine learning model performance and comparison metrics.
    """
    try:
        if not METRICS_PATH.exists():
            raise FileNotFoundError(f"Metrics file not found at {METRICS_PATH}")
            
        with open(METRICS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Error loading model metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to load model metrics")
