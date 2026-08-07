"""금융 뉴스 인메모리 목업 픽스처 — API 키 없이 즉시 동작.

여기 등장하는 발행사/티커는 모두 공개 상장사(공개 시장 엔티티)로 사내 기밀이 아니다.
수치(주가 영향·센티먼트·공시 항목)는 데모용 합성값이며 실제 시세·실적이 아니다.
실데이터는 USE_REAL_API=true + 뉴스 벤더 키로 NewsClient 의 real 경로가 담당한다.
"""

from __future__ import annotations

from datetime import timedelta

from utils.common.time_utils import now_kst

# 공개 상장사 샘플 — ticker → 표시명 별칭 (검색 정규화용)
COMPANY_ALIASES: dict[str, list[str]] = {
    "005930": ["삼성전자", "samsung", "samsung electronics"],
    "000660": ["sk하이닉스", "sk하이닉스", "sk hynix", "hynix"],
    "035420": ["naver", "네이버"],
    "AAPL": ["apple", "애플"],
    "MSFT": ["microsoft", "마이크로소프트", "msft"],
    "NVDA": ["nvidia", "엔비디아"],
}

# ticker → 카테고리·센티먼트가 부여된 합성 헤드라인 목록.
# sentiment: -1.0(부정) ~ +1.0(긍정), price_impact_pct = 데모용 추정 주가 영향(%).
# 날짜는 `days_ago`(읽는 시점 기준 며칠 전)로 두고 published_at 의 `{date}`(YYYY-MM-DD)·
# disclosure_id 의 `{ymd}`(YYYYMMDD)를 읽을 때 채운다 — 절대 날짜를 박으면 "최근 뉴스"가 영구히 낡는다.
_ARTICLES: dict[str, list[dict]] = {
    "005930": [
        {
            "article_id": "N000010001",
            "title": "삼성전자, 3분기 영업이익 시장 컨센서스 상회",
            "summary": "메모리 반도체 가격 반등과 HBM 출하 확대로 분기 영업이익이 시장 추정치를 웃돌았다고 공시했다.",
            "category": "실적",
            "company_name": "삼성전자",
            "days_ago": 4,
            "published_at": "{date}T08:30:00+09:00",
            "source": "샘플경제뉴스",
            "url": "https://news.example.com/article/N000010001",
            "sentiment": 0.62,
            "sentiment_label": "긍정",
            "price_impact_pct": 2.1,
            "disclosure_linked": True,
            "disclosure_type": "실적",
            "disclosure_id": "D{ymd}-005930-001",
        },
        {
            "article_id": "N000010002",
            "title": "삼성전자 이사회, 분기 배당 결의",
            "summary": "이사회가 보통주 1주당 분기 배당금을 전분기와 동일 수준으로 결의했다고 밝혔다.",
            "category": "배당",
            "company_name": "삼성전자",
            "days_ago": 6,
            "published_at": "{date}T16:00:00+09:00",
            "source": "샘플파이낸스",
            "url": "https://news.example.com/article/N000010002",
            "sentiment": 0.18,
            "sentiment_label": "중립",
            "price_impact_pct": 0.3,
            "disclosure_linked": True,
            "disclosure_type": "배당",
            "disclosure_id": "D{ymd}-005930-002",
        },
        {
            "article_id": "N000010003",
            "title": "삼성전자 파운드리, 일부 고객사 주문 지연 우려",
            "summary": "시황 둔화로 일부 고객사의 신규 주문이 지연될 수 있다는 시장 관측이 제기됐다.",
            "category": "시장",
            "company_name": "삼성전자",
            "days_ago": 9,
            "published_at": "{date}T10:10:00+09:00",
            "source": "샘플마켓워치",
            "url": "https://news.example.com/article/N000010003",
            "sentiment": -0.34,
            "sentiment_label": "부정",
            "price_impact_pct": -1.2,
            "disclosure_linked": False,
            "disclosure_type": None,
            "disclosure_id": None,
        },
    ],
    "000660": [
        {
            "article_id": "N000020001",
            "title": "SK하이닉스, HBM 공급 계약 확대 발표",
            "summary": "주요 AI 가속기 고객향 고대역폭 메모리(HBM) 공급 물량을 확대한다고 공시했다.",
            "category": "공시",
            "company_name": "SK하이닉스",
            "days_ago": 2,
            "published_at": "{date}T09:00:00+09:00",
            "source": "샘플경제뉴스",
            "url": "https://news.example.com/article/N000020001",
            "sentiment": 0.71,
            "sentiment_label": "긍정",
            "price_impact_pct": 3.4,
            "disclosure_linked": True,
            "disclosure_type": "기타",
            "disclosure_id": "D{ymd}-000660-001",
        },
        {
            "article_id": "N000020002",
            "title": "SK하이닉스, CAPEX(자본적지출) 확대에 따른 현금흐름 부담 분석",
            "summary": "대규모 자본적지출 확대로 단기 잉여현금흐름이 둔화될 수 있다는 증권가 분석이 나왔다.",
            "category": "거시",
            "company_name": "SK하이닉스",
            "days_ago": 5,
            "published_at": "{date}T11:20:00+09:00",
            "source": "샘플파이낸스",
            "url": "https://news.example.com/article/N000020002",
            "sentiment": -0.12,
            "sentiment_label": "중립",
            "price_impact_pct": -0.4,
            "disclosure_linked": False,
            "disclosure_type": None,
            "disclosure_id": None,
        },
    ],
    "035420": [
        {
            "article_id": "N000030001",
            "title": "네이버, 광고·커머스 매출 성장세 지속",
            "summary": "검색 광고와 커머스 부문이 두 자릿수 성장을 이어갔다고 분기 실적에서 밝혔다.",
            "category": "실적",
            "company_name": "NAVER",
            "days_ago": 3,
            "published_at": "{date}T08:00:00+09:00",
            "source": "샘플마켓워치",
            "url": "https://news.example.com/article/N000030001",
            "sentiment": 0.45,
            "sentiment_label": "긍정",
            "price_impact_pct": 1.5,
            "disclosure_linked": True,
            "disclosure_type": "실적",
            "disclosure_id": "D{ymd}-035420-001",
        },
    ],
    "AAPL": [
        {
            "article_id": "N000040001",
            "title": "Apple, 서비스 부문 매출 사상 최대",
            "summary": "앱스토어·구독 서비스 매출이 분기 기준 사상 최대를 기록했다고 발표했다.",
            "category": "실적",
            "company_name": "Apple",
            "days_ago": 4,
            "published_at": "{date}T22:00:00+09:00",
            "source": "Sample Global Wire",
            "url": "https://news.example.com/article/N000040001",
            "sentiment": 0.58,
            "sentiment_label": "긍정",
            "price_impact_pct": 1.9,
            "disclosure_linked": True,
            "disclosure_type": "실적",
            "disclosure_id": "F{ymd}-AAPL-10Q",
        },
        {
            "article_id": "N000040002",
            "title": "Apple, 자사주 매입 프로그램 확대 의결",
            "summary": "이사회가 추가 자사주 매입 한도를 승인했다고 공시했다.",
            "category": "공시",
            "company_name": "Apple",
            "days_ago": 7,
            "published_at": "{date}T22:30:00+09:00",
            "source": "Sample Global Wire",
            "url": "https://news.example.com/article/N000040002",
            "sentiment": 0.33,
            "sentiment_label": "긍정",
            "price_impact_pct": 0.8,
            "disclosure_linked": True,
            "disclosure_type": "기타",
            "disclosure_id": "F{ymd}-AAPL-8K",
        },
    ],
    "MSFT": [
        {
            "article_id": "N000050001",
            "title": "Microsoft, 클라우드 부문 두 자릿수 성장 유지",
            "summary": "애저(Azure) 매출 성장률이 시장 기대에 부합했다고 분기 실적에서 밝혔다.",
            "category": "실적",
            "company_name": "Microsoft",
            "days_ago": 5,
            "published_at": "{date}T22:00:00+09:00",
            "source": "Sample Global Wire",
            "url": "https://news.example.com/article/N000050001",
            "sentiment": 0.49,
            "sentiment_label": "긍정",
            "price_impact_pct": 1.3,
            "disclosure_linked": True,
            "disclosure_type": "실적",
            "disclosure_id": "F{ymd}-MSFT-10Q",
        },
    ],
    "NVDA": [
        {
            "article_id": "N000060001",
            "title": "NVIDIA, 데이터센터 매출 가이던스 상향",
            "summary": "차세대 AI 가속기 수요 강세로 다음 분기 데이터센터 매출 가이던스를 상향했다.",
            "category": "실적",
            "company_name": "NVIDIA",
            "days_ago": 1,
            "published_at": "{date}T22:00:00+09:00",
            "source": "Sample Global Wire",
            "url": "https://news.example.com/article/N000060001",
            "sentiment": 0.77,
            "sentiment_label": "긍정",
            "price_impact_pct": 4.2,
            "disclosure_linked": True,
            "disclosure_type": "실적",
            "disclosure_id": "F{ymd}-NVDA-8K",
        },
        {
            "article_id": "N000060002",
            "title": "NVIDIA, 수출 규제 관련 불확실성 지속",
            "summary": "일부 지역향 수출 규제 변동이 매출에 영향을 줄 수 있다는 리스크가 거론됐다.",
            "category": "거시",
            "company_name": "NVIDIA",
            "days_ago": 8,
            "published_at": "{date}T22:00:00+09:00",
            "source": "Sample Global Wire",
            "url": "https://news.example.com/article/N000060002",
            "sentiment": -0.41,
            "sentiment_label": "부정",
            "price_impact_pct": -1.8,
            "disclosure_linked": False,
            "disclosure_type": None,
            "disclosure_id": None,
        },
    ],
}


def _resolve(article: dict) -> dict:
    """days_ago 를 읽는 시점 날짜로 채운 사본 (published_at 의 {date}, disclosure_id 의 {ymd}).

    치환은 읽을 때마다 한다 — import 시점에 굳히면 오래 떠 있는 프로세스가 날짜를 넘기며 다시 낡는다.
    """
    day = (now_kst() - timedelta(days=article["days_ago"])).date()
    parts = {"date": day.isoformat(), "ymd": day.strftime("%Y%m%d")}
    resolved = {key: value for key, value in article.items() if key != "days_ago"}
    resolved["published_at"] = resolved["published_at"].format(**parts)
    if resolved.get("disclosure_id"):
        resolved["disclosure_id"] = resolved["disclosure_id"].format(**parts)
    return resolved


def all_articles() -> list[dict]:
    """전체 기사 평탄화 목록 (published_at 내림차순)."""
    flat = [_resolve(a) for arts in _ARTICLES.values() for a in arts]
    return sorted(flat, key=lambda a: a["published_at"], reverse=True)


def resolve_ticker(ticker: str | None, company_name: str | None) -> str | None:
    """ticker 또는 종목명(별칭)으로 표준 ticker 해석. 매칭 실패 시 None."""
    if ticker and ticker.upper() in {t.upper(): t for t in _ARTICLES}:
        return {t.upper(): t for t in _ARTICLES}[ticker.upper()]
    if company_name:
        needle = company_name.strip().lower()
        for tk, aliases in COMPANY_ALIASES.items():
            if needle in [a.lower() for a in aliases] or any(needle in a.lower() for a in aliases):
                return tk
    return None


def articles_for(ticker: str) -> list[dict]:
    """ticker 의 기사 목록 (published_at 내림차순)."""
    resolved = [_resolve(a) for a in _ARTICLES.get(ticker, [])]
    return sorted(resolved, key=lambda a: a["published_at"], reverse=True)


def article_by_id(article_id: str) -> dict | None:
    """기사 ID 단건 조회. 본문(body) 필드를 합성해 상세로 반환."""
    for a in all_articles():
        if a["article_id"] == article_id:
            return {**a, "body": f"{a['summary']} (목업 본문 — USE_REAL_API=true 로 실데이터 연동)"}
    return None
