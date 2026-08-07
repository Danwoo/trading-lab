"""포트폴리오 활동 요약 스키마 — LLM 구조화 출력 모델."""

from pydantic import BaseModel, Field


class PortfolioSummary(BaseModel):
    portfolio: str = Field(description="계좌·포트폴리오명")
    items: list[str] = Field(description="요약된 활동 항목 목록 (매매·평가·배당 등)")


class ActivitySummaries(BaseModel):
    summaries: list[PortfolioSummary] = Field(description="포트폴리오별 활동 요약 목록")
