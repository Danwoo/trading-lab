# schemas/nav/nav_schema.py
from pydantic import BaseModel


class NavPoint(BaseModel):
    timestamp: str
    nav: float | None = None
    benchmark: float | None = None
    daily_return: float | None = None
    drawdown: float | None = None


class NavHistoryOut(BaseModel):
    items: list[NavPoint]
    total_count: int
