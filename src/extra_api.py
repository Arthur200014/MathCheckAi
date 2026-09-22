from __future__ import annotations

from fastapi import HTTPException

from src import api
from src.tools.core import load_review, metrics_summary


@api.app.get("/metrics-summary")
def get_metrics_summary(limit: int = 200):

    return metrics_summary(limit=limit)


@api.app.get("/api/reviews/{review_id}")
def get_saved_review(review_id: str):

    review = load_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Проверка не найдена.")
    return review
# fix
