from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from schemas.vector_search.vector_search_schema import ImageSearchIn, ImageSearchOut, TopicSearchIn, TopicSearchOut
from services.vector_search.vector_search_service import VectorSearchService
from utils.common.few_shot import few_shot

# operation_id 가 MCP tool 이름의 SoT — multi-agent-service `agents/domains/*` 의 SUBAGENT_SPECS.mcp_tools
# 가 이 이름으로 바인딩 (변경 시 lockstep). docstring 이 tool description, Pydantic In/Out 이 tool 입출력 스키마.
# collection 인자 = Milvus 컬렉션명 = operation_id 에서 "doc_search_" 를 뗀 값과 동일.
router = APIRouter(prefix="/doc-search", dependencies=[Depends(verify_access_token)])


# ──────────────────────────── topic (텍스트) 14개 ────────────────────────────


@router.post(
    "/topic-filing",
    operation_id="doc_search_topic_filing",
    openapi_extra=few_shot(
        [{"질문": "삼성전자 사업보고서 사업의 내용", "호출": {"query": "삼성전자 사업보고서 사업의 내용"}}]
    ),
)
@inject
async def topic_search_filing(
    body: TopicSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> TopicSearchOut:
    """공시 분야 금융 문서 텍스트 검색 (Milvus topic_filing 컬렉션 hybrid: dense+BM25 sparse 가중합+rerank). 사업보고서·분기/반기보고서·증권신고서 등 정기·주요사항 공시 본문/Q&A 청크를 반환. source 로 html(공시 본문)·label(해설 Q&A) 필터 가능, 미지정 시 통합. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 결과가 0건이거나 score 가 낮으면 지어내지 말고 근거 없음을 밝혀라. 수치는 공시 원문에 근거할 때만 인용한다."""
    return await vector_search_service.topic_search("topic_filing", body)


@router.post("/topic-earnings", operation_id="doc_search_topic_earnings")
@inject
async def topic_search_earnings(
    body: TopicSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> TopicSearchOut:
    """실적 분야 금융 문서 텍스트 검색 (Milvus topic_earnings 컬렉션 hybrid: dense+BM25 sparse 가중합+rerank). 실적발표·어닝콜 스크립트·IR 자료·실적 리뷰 리포트 본문/Q&A 청크를 반환. source 로 html(리포트 본문)·label(해설 Q&A) 필터 가능, 미지정 시 통합. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 결과가 0건이거나 score 가 낮으면 지어내지 말고 근거 없음을 밝혀라. 매출·영업이익 등 수치는 출처 문서에 근거할 때만 인용한다."""
    return await vector_search_service.topic_search("topic_earnings", body)


@router.post("/topic-risk", operation_id="doc_search_topic_risk")
@inject
async def topic_search_risk(
    body: TopicSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> TopicSearchOut:
    """리스크 분야 금융 문서 텍스트 검색 (Milvus topic_risk 컬렉션 hybrid: dense+BM25 sparse 가중합+rerank). 사업·시장·신용·유동성 위험요인, 공시의 '위험요소'·리스크 관리 리포트 본문/Q&A 청크를 반환. source 로 html(리포트 본문)·label(해설 Q&A) 필터 가능, 미지정 시 통합. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 결과가 0건이거나 score 가 낮으면 지어내지 말고 근거 없음을 밝혀라."""
    return await vector_search_service.topic_search("topic_risk", body)


@router.post("/topic-valuation", operation_id="doc_search_topic_valuation")
@inject
async def topic_search_valuation(
    body: TopicSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> TopicSearchOut:
    """밸류에이션 분야 금융 문서 텍스트 검색 (Milvus topic_valuation 컬렉션 hybrid: dense+BM25 sparse 가중합+rerank). PER·PBR·EV/EBITDA·DCF·목표주가 산정 등 가치평가 방법론과 애널리스트 밸류에이션 리포트 본문/Q&A 청크를 반환. source 로 html(리포트 본문)·label(해설 Q&A) 필터 가능, 미지정 시 통합. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 결과가 0건이거나 score 가 낮으면 지어내지 말고 근거 없음을 밝혀라. 멀티플·목표가는 출처에 근거할 때만 인용한다."""
    return await vector_search_service.topic_search("topic_valuation", body)


@router.post("/topic-macro", operation_id="doc_search_topic_macro")
@inject
async def topic_search_macro(
    body: TopicSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> TopicSearchOut:
    """매크로 분야 금융 문서 텍스트 검색 (Milvus topic_macro 컬렉션 hybrid: dense+BM25 sparse 가중합+rerank). 금리·물가·GDP·고용 등 거시경제 지표, 통화정책(FOMC·한은)·경제전망 리포트 본문/Q&A 청크를 반환. source 로 html(리포트 본문)·label(해설 Q&A) 필터 가능, 미지정 시 통합. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 결과가 0건이거나 score 가 낮으면 지어내지 말고 근거 없음을 밝혀라."""
    return await vector_search_service.topic_search("topic_macro", body)


@router.post("/topic-sector", operation_id="doc_search_topic_sector")
@inject
async def topic_search_sector(
    body: TopicSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> TopicSearchOut:
    """섹터 분야 금융 문서 텍스트 검색 (Milvus topic_sector 컬렉션 hybrid: dense+BM25 sparse 가중합+rerank). 반도체·2차전지·금융·바이오 등 산업/섹터 분석, 업황·밸류체인·경쟁구도 리포트 본문/Q&A 청크를 반환. source 로 html(리포트 본문)·label(해설 Q&A) 필터 가능, 미지정 시 통합. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 결과가 0건이거나 score 가 낮으면 지어내지 말고 근거 없음을 밝혀라."""
    return await vector_search_service.topic_search("topic_sector", body)


@router.post("/topic-fixed-income", operation_id="doc_search_topic_fixed_income")
@inject
async def topic_search_fixed_income(
    body: TopicSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> TopicSearchOut:
    """채권 분야 금융 문서 텍스트 검색 (Milvus topic_fixed_income 컬렉션 hybrid: dense+BM25 sparse 가중합+rerank). 국채·회사채·크레딧 스프레드·듀레이션·신용등급·발행조건 등 채권/크레딧 리포트 본문/Q&A 청크를 반환. source 로 html(리포트 본문)·label(해설 Q&A) 필터 가능, 미지정 시 통합. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 결과가 0건이거나 score 가 낮으면 지어내지 말고 근거 없음을 밝혀라."""
    return await vector_search_service.topic_search("topic_fixed_income", body)


@router.post("/topic-fx", operation_id="doc_search_topic_fx")
@inject
async def topic_search_fx(
    body: TopicSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> TopicSearchOut:
    """외환 분야 금융 문서 텍스트 검색 (Milvus topic_fx 컬렉션 hybrid: dense+BM25 sparse 가중합+rerank). 환율 전망·달러/원·주요 통화 동향·환헤지·외환정책 리포트 본문/Q&A 청크를 반환. source 로 html(리포트 본문)·label(해설 Q&A) 필터 가능, 미지정 시 통합. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 결과가 0건이거나 score 가 낮으면 지어내지 말고 근거 없음을 밝혀라."""
    return await vector_search_service.topic_search("topic_fx", body)


@router.post("/topic-commodity", operation_id="doc_search_topic_commodity")
@inject
async def topic_search_commodity(
    body: TopicSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> TopicSearchOut:
    """원자재 분야 금융 문서 텍스트 검색 (Milvus topic_commodity 컬렉션 hybrid: dense+BM25 sparse 가중합+rerank). 원유·금·구리·천연가스 등 원자재 가격 전망과 수급·재고 분석 리포트 본문/Q&A 청크를 반환. source 로 html(리포트 본문)·label(해설 Q&A) 필터 가능, 미지정 시 통합. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 결과가 0건이거나 score 가 낮으면 지어내지 말고 근거 없음을 밝혀라."""
    return await vector_search_service.topic_search("topic_commodity", body)


@router.post("/topic-esg", operation_id="doc_search_topic_esg")
@inject
async def topic_search_esg(
    body: TopicSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> TopicSearchOut:
    """ESG 분야 금융 문서 텍스트 검색 (Milvus topic_esg 컬렉션 hybrid: dense+BM25 sparse 가중합+rerank). 지속가능경영보고서·ESG 평가·탄소배출·지배구조 등 비재무 정보 리포트 본문/Q&A 청크를 반환. source 로 html(리포트 본문)·label(해설 Q&A) 필터 가능, 미지정 시 통합. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 결과가 0건이거나 score 가 낮으면 지어내지 말고 근거 없음을 밝혀라."""
    return await vector_search_service.topic_search("topic_esg", body)


@router.post("/topic-compliance", operation_id="doc_search_topic_compliance")
@inject
async def topic_search_compliance(
    body: TopicSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> TopicSearchOut:
    """컴플라이언스 분야 금융 문서 텍스트 검색 (Milvus topic_compliance 컬렉션 hybrid: dense+BM25 sparse 가중합+rerank). 자본시장법·금융소비자보호·내부통제·공시규정·제재 사례 등 규제/준법 자료 본문/Q&A 청크를 반환. source 로 html(규정 본문)·label(해설 Q&A) 필터 가능, 미지정 시 통합. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 결과가 0건이거나 score 가 낮으면 지어내지 말고 근거 없음을 밝혀라."""
    return await vector_search_service.topic_search("topic_compliance", body)


@router.post("/topic-product-terms", operation_id="doc_search_topic_product_terms")
@inject
async def topic_search_product_terms(
    body: TopicSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> TopicSearchOut:
    """상품약관 분야 금융 문서 텍스트 검색 (Milvus topic_product_terms 컬렉션 hybrid: dense+BM25 sparse 가중합+rerank). 펀드·ETF 투자설명서, 예적금·보험·연금 상품 약관·수수료·중도해지 조건 등 상품 문서 본문/Q&A 청크를 반환. source 로 html(약관 본문)·label(해설 Q&A) 필터 가능, 미지정 시 통합. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 결과가 0건이거나 score 가 낮으면 지어내지 말고 근거 없음을 밝혀라. 수수료·조건은 약관 원문에 근거할 때만 인용한다."""
    return await vector_search_service.topic_search("topic_product_terms", body)


@router.post("/topic-faq", operation_id="doc_search_topic_faq")
@inject
async def topic_search_faq(
    body: TopicSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> TopicSearchOut:
    """FAQ 분야 금융 문서 텍스트 검색 (Milvus topic_faq 컬렉션 hybrid: dense+BM25 sparse 가중합+rerank). 계좌개설·매매·세금·서비스 이용 등 투자자 자주 묻는 질문/답변 청크를 반환. source 로 html(안내 본문)·label(Q&A) 필터 가능, 정의·절차형 질문엔 label 우선. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 결과가 0건이거나 score 가 낮으면 지어내지 말고 근거 없음을 밝혀라."""
    return await vector_search_service.topic_search("topic_faq", body)


@router.post("/topic-glossary", operation_id="doc_search_topic_glossary")
@inject
async def topic_search_glossary(
    body: TopicSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> TopicSearchOut:
    """용어집 분야 금융 문서 텍스트 검색 (Milvus topic_glossary 컬렉션 hybrid: dense+BM25 sparse 가중합+rerank). PER·ROE·듀레이션·공매도 등 금융/투자 용어 정의·해설 청크를 반환 — 용어 뜻을 물을 때 사용. source 로 html(설명 본문)·label(Q&A) 필터 가능, 정의형 질문엔 label 우선. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 결과가 0건이거나 score 가 낮으면 지어내지 말고 근거 없음을 밝혀라."""
    return await vector_search_service.topic_search("topic_glossary", body)


# ──────────────────────────── image (이미지) 14개 ────────────────────────────


@router.post(
    "/image-filing",
    operation_id="doc_search_image_filing",
    openapi_extra=few_shot([{"질문": "사업보고서 지배구조 도표 이미지", "호출": {"query": "지배구조 도표"}}]),
)
@inject
async def image_search_filing(
    body: ImageSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> ImageSearchOut:
    """공시 분야 금융 문서 이미지 검색 (Milvus image_filing 컬렉션, 이미지 캡션 hybrid+rerank). 공시 내 지배구조도·조직도·재무 도표 이미지의 file_url(이미지 URL)·summary_caption·detailed_caption·book_id 를 반환 — 도표/차트/구조도가 필요할 때 사용. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 0건이면 이미지가 없다고 답하라."""
    return await vector_search_service.image_search("image_filing", body)


@router.post("/image-earnings", operation_id="doc_search_image_earnings")
@inject
async def image_search_earnings(
    body: ImageSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> ImageSearchOut:
    """실적 분야 금융 문서 이미지 검색 (Milvus image_earnings 컬렉션, 이미지 캡션 hybrid+rerank). 실적/IR 자료의 매출·이익 추이 차트, 세그먼트 표 이미지의 file_url(이미지 URL)·summary_caption·detailed_caption·book_id 를 반환 — 도표/차트/구조도가 필요할 때 사용. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 0건이면 이미지가 없다고 답하라."""
    return await vector_search_service.image_search("image_earnings", body)


@router.post("/image-risk", operation_id="doc_search_image_risk")
@inject
async def image_search_risk(
    body: ImageSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> ImageSearchOut:
    """리스크 분야 금융 문서 이미지 검색 (Milvus image_risk 컬렉션, 이미지 캡션 hybrid+rerank). 리스크 히트맵·민감도/시나리오 분석 차트 이미지의 file_url(이미지 URL)·summary_caption·detailed_caption·book_id 를 반환 — 도표/차트/구조도가 필요할 때 사용. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 0건이면 이미지가 없다고 답하라."""
    return await vector_search_service.image_search("image_risk", body)


@router.post("/image-valuation", operation_id="doc_search_image_valuation")
@inject
async def image_search_valuation(
    body: ImageSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> ImageSearchOut:
    """밸류에이션 분야 금융 문서 이미지 검색 (Milvus image_valuation 컬렉션, 이미지 캡션 hybrid+rerank). 밴드 차트·멀티플 비교·DCF 민감도 표 이미지의 file_url(이미지 URL)·summary_caption·detailed_caption·book_id 를 반환 — 도표/차트/구조도가 필요할 때 사용. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 0건이면 이미지가 없다고 답하라."""
    return await vector_search_service.image_search("image_valuation", body)


@router.post("/image-macro", operation_id="doc_search_image_macro")
@inject
async def image_search_macro(
    body: ImageSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> ImageSearchOut:
    """매크로 분야 금융 문서 이미지 검색 (Milvus image_macro 컬렉션, 이미지 캡션 hybrid+rerank). 금리·물가·GDP 추이 그래프 등 거시지표 차트 이미지의 file_url(이미지 URL)·summary_caption·detailed_caption·book_id 를 반환 — 도표/차트/구조도가 필요할 때 사용. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 0건이면 이미지가 없다고 답하라."""
    return await vector_search_service.image_search("image_macro", body)


@router.post("/image-sector", operation_id="doc_search_image_sector")
@inject
async def image_search_sector(
    body: ImageSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> ImageSearchOut:
    """섹터 분야 금융 문서 이미지 검색 (Milvus image_sector 컬렉션, 이미지 캡션 hybrid+rerank). 산업 밸류체인도·점유율·업황 사이클 차트 이미지의 file_url(이미지 URL)·summary_caption·detailed_caption·book_id 를 반환 — 도표/차트/구조도가 필요할 때 사용. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 0건이면 이미지가 없다고 답하라."""
    return await vector_search_service.image_search("image_sector", body)


@router.post("/image-fixed-income", operation_id="doc_search_image_fixed_income")
@inject
async def image_search_fixed_income(
    body: ImageSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> ImageSearchOut:
    """채권 분야 금융 문서 이미지 검색 (Milvus image_fixed_income 컬렉션, 이미지 캡션 hybrid+rerank). 수익률 곡선·크레딧 스프레드 추이 차트 이미지의 file_url(이미지 URL)·summary_caption·detailed_caption·book_id 를 반환 — 도표/차트/구조도가 필요할 때 사용. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 0건이면 이미지가 없다고 답하라."""
    return await vector_search_service.image_search("image_fixed_income", body)


@router.post("/image-fx", operation_id="doc_search_image_fx")
@inject
async def image_search_fx(
    body: ImageSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> ImageSearchOut:
    """외환 분야 금융 문서 이미지 검색 (Milvus image_fx 컬렉션, 이미지 캡션 hybrid+rerank). 환율 추이·통화별 강도 차트 이미지의 file_url(이미지 URL)·summary_caption·detailed_caption·book_id 를 반환 — 도표/차트/구조도가 필요할 때 사용. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 0건이면 이미지가 없다고 답하라."""
    return await vector_search_service.image_search("image_fx", body)


@router.post("/image-commodity", operation_id="doc_search_image_commodity")
@inject
async def image_search_commodity(
    body: ImageSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> ImageSearchOut:
    """원자재 분야 금융 문서 이미지 검색 (Milvus image_commodity 컬렉션, 이미지 캡션 hybrid+rerank). 원유·금속 가격 추이·재고/수급 차트 이미지의 file_url(이미지 URL)·summary_caption·detailed_caption·book_id 를 반환 — 도표/차트/구조도가 필요할 때 사용. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 0건이면 이미지가 없다고 답하라."""
    return await vector_search_service.image_search("image_commodity", body)


@router.post("/image-esg", operation_id="doc_search_image_esg")
@inject
async def image_search_esg(
    body: ImageSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> ImageSearchOut:
    """ESG 분야 금융 문서 이미지 검색 (Milvus image_esg 컬렉션, 이미지 캡션 hybrid+rerank). 탄소배출 추이·ESG 등급·지배구조 도식 이미지의 file_url(이미지 URL)·summary_caption·detailed_caption·book_id 를 반환 — 도표/차트/구조도가 필요할 때 사용. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 0건이면 이미지가 없다고 답하라."""
    return await vector_search_service.image_search("image_esg", body)


@router.post("/image-compliance", operation_id="doc_search_image_compliance")
@inject
async def image_search_compliance(
    body: ImageSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> ImageSearchOut:
    """컴플라이언스 분야 금융 문서 이미지 검색 (Milvus image_compliance 컬렉션, 이미지 캡션 hybrid+rerank). 내부통제 흐름도·규제 절차도·제재 통계 차트 이미지의 file_url(이미지 URL)·summary_caption·detailed_caption·book_id 를 반환 — 도표/차트/구조도가 필요할 때 사용. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 0건이면 이미지가 없다고 답하라."""
    return await vector_search_service.image_search("image_compliance", body)


@router.post("/image-product-terms", operation_id="doc_search_image_product_terms")
@inject
async def image_search_product_terms(
    body: ImageSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> ImageSearchOut:
    """상품약관 분야 금융 문서 이미지 검색 (Milvus image_product_terms 컬렉션, 이미지 캡션 hybrid+rerank). 상품구조도·수수료 표·수익구조 그래프 이미지의 file_url(이미지 URL)·summary_caption·detailed_caption·book_id 를 반환 — 도표/차트/구조도가 필요할 때 사용. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 0건이면 이미지가 없다고 답하라."""
    return await vector_search_service.image_search("image_product_terms", body)


@router.post("/image-faq", operation_id="doc_search_image_faq")
@inject
async def image_search_faq(
    body: ImageSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> ImageSearchOut:
    """FAQ 분야 금융 문서 이미지 검색 (Milvus image_faq 컬렉션, 이미지 캡션 hybrid+rerank). 이용 절차 안내도·화면 캡처 등 안내 이미지의 file_url(이미지 URL)·summary_caption·detailed_caption·book_id 를 반환 — 도표/차트/구조도가 필요할 때 사용. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 0건이면 이미지가 없다고 답하라."""
    return await vector_search_service.image_search("image_faq", body)


@router.post("/image-glossary", operation_id="doc_search_image_glossary")
@inject
async def image_search_glossary(
    body: ImageSearchIn,
    vector_search_service: VectorSearchService = Depends(Provide[Container.vector_search_service]),
) -> ImageSearchOut:
    """용어집 분야 금융 문서 이미지 검색 (Milvus image_glossary 컬렉션, 이미지 캡션 hybrid+rerank). 용어 개념도·계산식 도식 이미지의 file_url(이미지 URL)·summary_caption·detailed_caption·book_id 를 반환 — 도표/차트/구조도가 필요할 때 사용. score 는 rerank 성공 시 relevance(0~1), 실패 시 hybrid 가중합 폴백(rerank=null). 0건이면 이미지가 없다고 답하라."""
    return await vector_search_service.image_search("image_glossary", body)
