"""인프라(Milvus/Redis/임베딩/리랭커) 없이도 서비스가 동작하도록 하는 MOCK 금융 문서 스냅샷 (순수함수, IO 없음).

`USE_REAL_API=false`(기본) 이거나 실 인프라 연결이 실패하면 service 가 이 픽스처로 폴백한다 — 컬렉션(분야)별로
몇 개의 그럴듯한 공시/리포트/약관 청크·이미지 캡션을 반환해 28개 tool 이 단독 기동만으로 비어있지 않은 결과를 낸다.
픽스처에 담긴 발행사는 모두 공개시장 well-known 종목(샘플) — 비공개 정보가 아니다. 수치는 예시이며 실제 공시가 아니다.
"""

from __future__ import annotations

from schemas.vector_search.vector_search_schema import (
    ImageSearchItem,
    ImageSearchOut,
    TopicSearchItem,
    TopicSearchOut,
)

# 컬렉션명(operation_id 에서 doc_search_ 제거) → (분야 한글 라벨, 샘플 발행사, 본문 청크, Q&A)
_TOPIC_FIXTURES: dict[str, tuple[str, str, str, str, str]] = {
    "topic_filing": (
        "공시",
        "삼성전자",
        "삼성전자 사업보고서 '사업의 내용'은 DX·DS·SDC·Harman 부문별 주요 제품과 매출 구성을 기재한다. (예시 데이터)",
        "사업보고서는 어디서 확인하나요?",
        "정기공시는 금융감독원 전자공시시스템(DART)에서 회사명으로 조회할 수 있습니다. (예시 데이터)",
    ),
    "topic_earnings": (
        "실적",
        "Apple Inc.",
        "분기 실적 발표는 매출·영업이익·EPS 가이던스와 세그먼트별 성장률을 다루며, 어닝콜에서 경영진 Q&A가 이어진다. (예시 데이터)",
        "어닝 서프라이즈란 무엇인가요?",
        "실제 발표 실적이 시장 컨센서스를 상회(상회 서프라이즈)하거나 하회하는 것을 말합니다. (예시 데이터)",
    ),
    "topic_risk": (
        "리스크",
        "현대차",
        "사업보고서의 '위험요소'는 시장위험·신용위험·유동성위험·환위험을 구분해 기재하고 헤지 정책을 설명한다. (예시 데이터)",
        "유동성 위험이란 무엇인가요?",
        "보유 자산을 적시에 적정 가격으로 현금화하지 못해 채무를 이행하기 어려운 위험을 말합니다. (예시 데이터)",
    ),
    "topic_valuation": (
        "밸류에이션",
        "NAVER",
        "목표주가는 12개월 forward EPS에 목표 PER를 적용하거나 DCF로 산정하며, 동종업계 멀티플과 비교한다. (예시 데이터)",
        "PER와 PBR의 차이는?",
        "PER는 주가/주당순이익, PBR은 주가/주당순자산으로, 각각 이익·자산 대비 가치를 봅니다. (예시 데이터)",
    ),
    "topic_macro": (
        "매크로",
        "한국은행",
        "기준금리 동결/인상 결정은 물가상승률·성장률·환율·가계부채를 종합해 통화정책방향 의결문으로 공표된다. (예시 데이터)",
        "기준금리 인상이 주식시장에 미치는 영향은?",
        "할인율 상승으로 밸류에이션 부담이 커져 성장주에 비우호적인 경향이 있습니다(일반론, 예시). (예시 데이터)",
    ),
    "topic_sector": (
        "섹터",
        "SK하이닉스",
        "반도체 업황은 메모리 가격 사이클·재고 수준·AI 수요에 좌우되며 밸류체인은 설계·파운드리·패키징/테스트 단계로 나뉜다. (예시 데이터)",
        "반도체 사이클이란?",
        "수요·공급 불균형으로 메모리 가격이 상승·하락을 반복하는 산업 특유의 주기를 말합니다. (예시 데이터)",
    ),
    "topic_fixed_income": (
        "채권",
        "대한민국 국고채",
        "국고채 금리는 기준금리·기간프리미엄·수급에 따라 결정되며 회사채는 신용스프레드가 더해진다. (예시 데이터)",
        "듀레이션이 의미하는 것은?",
        "금리 1%p 변동 시 채권가격의 민감도(연 단위)를 나타내는 지표입니다. (예시 데이터)",
    ),
    "topic_fx": (
        "외환",
        "달러/원",
        "달러/원 환율은 미 연준 통화정책·무역수지·위험선호도에 영향받으며 수출입 기업 실적과 연동된다. (예시 데이터)",
        "환헤지란 무엇인가요?",
        "선물환·통화옵션 등으로 환율 변동에 따른 손익 불확실성을 줄이는 전략입니다. (예시 데이터)",
    ),
    "topic_commodity": (
        "원자재",
        "WTI 원유",
        "WTI 유가는 OPEC+ 감산·미국 재고·달러 강세에 영향받으며 정유·항공·화학 업종 마진과 직결된다. (예시 데이터)",
        "콘탱고와 백워데이션의 차이는?",
        "선물가격이 현물보다 높은 상태가 콘탱고, 낮은 상태가 백워데이션입니다. (예시 데이터)",
    ),
    "topic_esg": (
        "ESG",
        "포스코홀딩스",
        "지속가능경영보고서는 온실가스 배출량(Scope 1·2·3)·탄소중립 로드맵·이사회 다양성을 공시한다. (예시 데이터)",
        "ESG 평가등급은 어떻게 매겨지나요?",
        "환경·사회·지배구조 항목을 평가기관이 점수화해 등급(AAA~D 등)으로 부여합니다. (예시 데이터)",
    ),
    "topic_compliance": (
        "컴플라이언스",
        "금융위원회",
        "자본시장법상 미공개중요정보 이용·시세조종은 금지되며 위반 시 형사처벌·과징금 대상이 된다. (예시 데이터)",
        "내부자거래란 무엇인가요?",
        "미공개 중요정보를 이용해 해당 회사 증권을 거래하는 불공정거래 행위를 말합니다. (예시 데이터)",
    ),
    "topic_product_terms": (
        "상품약관",
        "KODEX 200 ETF",
        "ETF 투자설명서는 기초지수·보수율·괴리율·분배금 지급 기준과 환매 절차를 명시한다. (예시 데이터)",
        "ETF 총보수란?",
        "운용·지정참가·신탁 보수를 합산한 연환산 비용으로, 순자산에서 매일 차감됩니다. (예시 데이터)",
    ),
    "topic_faq": (
        "FAQ",
        "샘플증권",
        "해외주식 매매 시 환전·결제일(T+2 내외)·양도소득세(연 250만원 기본공제) 안내가 제공된다. (예시 데이터)",
        "해외주식 양도소득세는 언제 신고하나요?",
        "매도 차익에 대해 다음 해 5월 종합소득세 신고기간에 확정신고합니다(일반 안내, 예시). (예시 데이터)",
    ),
    "topic_glossary": (
        "용어집",
        "용어집",
        "ROE(자기자본이익률)는 당기순이익을 자기자본으로 나눈 값으로 자본 효율성을 나타낸다. (예시 데이터)",
        "공매도란 무엇인가요?",
        "주식을 빌려 매도한 뒤 가격 하락 시 되사서 차익을 얻는 거래 기법입니다. (예시 데이터)",
    ),
}

_IMAGE_FIXTURES: dict[str, tuple[str, str]] = {
    "image_filing": (
        "지배구조 현황 도표 (예시)",
        "사업보고서 내 지배구조도 — 최대주주·계열사 지분 관계를 도식화한 표 (예시 캡션)",
    ),
    "image_earnings": (
        "분기 매출·영업이익 추이 차트 (예시)",
        "최근 8개 분기 매출과 영업이익률을 막대·선 혼합으로 표현한 실적 차트 (예시 캡션)",
    ),
    "image_risk": (
        "리스크 히트맵 (예시)",
        "발생가능성×영향도 축의 리스크 매트릭스로 주요 위험요인을 분류한 도식 (예시 캡션)",
    ),
    "image_valuation": (
        "PER 밴드 차트 (예시)",
        "과거 5년 주가를 PER 배수 밴드(하단~상단) 위에 겹쳐 그린 밸류에이션 차트 (예시 캡션)",
    ),
    "image_macro": (
        "기준금리·물가 추이 그래프 (예시)",
        "기준금리와 소비자물가 상승률을 동일 축에 그린 시계열 그래프 (예시 캡션)",
    ),
    "image_sector": (
        "반도체 밸류체인도 (예시)",
        "설계·파운드리·패키징/테스트로 이어지는 반도체 산업 밸류체인 다이어그램 (예시 캡션)",
    ),
    "image_fixed_income": (
        "국고채 수익률 곡선 (예시)",
        "만기별(3M~30Y) 국고채 금리를 연결한 일드커브 그래프 (예시 캡션)",
    ),
    "image_fx": ("달러/원 환율 추이 (예시)", "최근 1년 달러/원 종가를 일별로 그린 환율 추이 차트 (예시 캡션)"),
    "image_commodity": ("WTI 유가·재고 차트 (예시)", "WTI 가격과 미국 원유 재고를 함께 표시한 수급 차트 (예시 캡션)"),
    "image_esg": ("온실가스 배출 추이 (예시)", "Scope 1·2·3 배출량을 연도별 누적 막대로 표현한 ESG 차트 (예시 캡션)"),
    "image_compliance": (
        "내부통제 절차 흐름도 (예시)",
        "주문-심사-모니터링-보고로 이어지는 준법감시 프로세스 다이어그램 (예시 캡션)",
    ),
    "image_product_terms": (
        "ETF 상품구조도 (예시)",
        "기초지수 추종·설정/환매·분배금 흐름을 도식화한 상품구조 그림 (예시 캡션)",
    ),
    "image_faq": (
        "계좌개설 절차 안내도 (예시)",
        "본인인증-약관동의-계좌개설-입금으로 이어지는 단계별 안내 이미지 (예시 캡션)",
    ),
    "image_glossary": ("ROE 계산식 도식 (예시)", "ROE = 순이익 ÷ 자기자본 관계를 시각화한 개념 도식 (예시 캡션)"),
}

_MOCK_IMAGE_BASE = "https://example.com/mock/finance/doc-search"


def _topic_item(
    label: str, issuer: str, body: str, q: str, a: str, source: str | None, score: float
) -> TopicSearchItem:
    eff_source = source or "label"
    return TopicSearchItem(
        score=score,
        rerank=None,
        hybrid=score,
        dense=score,
        doc_sparse_score=score,
        meta_sparse_score=0.0,
        source=eff_source,
        book_id=0 if eff_source == "label" else 1,
        primary_code=label,
        topic_codes=[label],
        l1l2_codes=[label],
        file_nm=f"{issuer} {label} 샘플 문서.pdf",
        header_chain=f"{label}>{issuer}",
        text=body if eff_source == "html" else "",
        question=q if eff_source == "label" else "",
        answer=a if eff_source == "label" else "",
    )


def mock_topic_out(collection: str, source: str | None, top_k: int) -> TopicSearchOut:
    """컬렉션(분야)별 MOCK 텍스트 결과 — source 필터를 존중하며 html/label 청크를 합쳐 반환."""
    label, issuer, body, q, a = _TOPIC_FIXTURES.get(
        collection, ("금융", "샘플", "관련 금융 문서 본문 (예시 데이터)", "샘플 질문", "샘플 답변 (예시 데이터)")
    )
    items: list[TopicSearchItem] = []
    if source in (None, "label"):
        items.append(_topic_item(label, issuer, body, q, a, "label", 0.92))
    if source in (None, "html"):
        items.append(_topic_item(label, issuer, body, q, a, "html", 0.81))
    items = items[:top_k]
    return TopicSearchOut(data=items, total_count=len(items))


def mock_image_out(collection: str, top_k: int) -> ImageSearchOut:
    """컬렉션(분야)별 MOCK 이미지 결과 — file_url 은 example.com 더미, 캡션은 분야별 그럴듯한 설명."""
    summary, detailed = _IMAGE_FIXTURES.get(collection, ("금융 도표 (예시)", "관련 금융 도표 이미지 (예시 캡션)"))
    item = ImageSearchItem(
        score=0.88,
        rerank=None,
        hybrid=0.88,
        book_id=1,
        seq=1,
        file_url=f"{_MOCK_IMAGE_BASE}/{collection}/1.png",
        file_nm=f"{collection} 샘플 도표.pdf",
        primary_code=collection.replace("image_", ""),
        topic_codes=[collection.replace("image_", "")],
        summary_caption=summary,
        detailed_caption=detailed,
    )
    return ImageSearchOut(data=[item][:top_k], total_count=min(1, top_k))
