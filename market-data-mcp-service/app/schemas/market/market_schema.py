from typing import Literal

from pydantic import BaseModel, Field


class MarketQuoteIn(BaseModel):
    symbol: str = Field(description="종목 티커 또는 종목코드 (예: '005930', 'AAPL') — 단일 종목 시세 조회")


class MarketOhlcIn(BaseModel):
    symbol: str = Field(description="종목 티커 또는 종목코드 (예: '005930', 'AAPL')")
    interval: Literal["1d", "1w", "1mo"] = Field(default="1d", description="캔들 주기 (1d=일봉, 1w=주봉, 1mo=월봉)")
    count: int = Field(default=10, ge=1, le=120, description="조회할 캔들 개수 (최신순)")


class MarketIndexIn(BaseModel):
    index_code: str = Field(description="지수 코드 (예: 'KOSPI', 'KOSDAQ', 'SPX', 'IXIC') — 시장 대표 지수 현재값")


class MarketFxIn(BaseModel):
    pair: str = Field(description="통화쌍 (예: 'USD/KRW', 'EUR/KRW', 'JPY/KRW') — 환율 현재값")


class MarketSearchIn(BaseModel):
    keyword: str = Field(description="종목명·티커 일부 키워드 (예: '삼성', 'Apple', 'TSLA')")
    market: Literal["ALL", "KR", "US"] = Field(default="ALL", description="검색 시장 (ALL=전체, KR=국내, US=미국)")
    count: int = Field(default=10, ge=1, le=30, description="조회 건수")


class MarketDataOut(BaseModel):
    data: list[dict] = Field(default_factory=list, description="조회 결과 목록")
    total_count: int = Field(default=0, description="전체 결과 수")
