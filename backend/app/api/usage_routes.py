from __future__ import annotations

from fastapi import APIRouter
from app.core.usage_tracker import usage_tracker

router = APIRouter(prefix="/api/v1/usage")


@router.get("")
async def get_usage():
    return usage_tracker.get_all()
