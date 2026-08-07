<!--
  M2 워커 오더 3/3 — 시세 데이터 계층과 provider 추상화.
  이 파일은 오더의 **보관본**이다. 실제 배정 시에는 대상 이슈 코멘트로 옮겨 게시하고
  `human: plan` 승인을 받는다. 이슈 번호는 배정 시 제목 줄에 채운다.
-->

# 오더: 시세 적재 계층 — 스키마 · provider 추상화 · 적재 워커

**목표**: 종목 마스터와 캔들을 로컬에 쌓는 계층을 만들고, 소스가 2~3개로 늘어도 어댑터 하나 추가로 끝나는 경계를 세운다.

**입력**: [PRD](prd.md) FR-008 ~ FR-015 · FR-046 ~ FR-049 · NFR-003 · NFR-004 · NFR-006 · NFR-007 · 설계 문서 [시세적재 구현설계](../4-아키텍처/시세적재-구현설계.md) **MD-AD-13 ~ MD-AD-26**(MD-AD-21~26 은 #279 — 거래일 캘린더·미완성 캔들·갭 검출·중복 정리·별칭 유효기간·분봉 interval 불변식) · [시세 데이터 파이프라인](../4-아키텍처/시세-데이터-파이프라인.md) — 수행자는 이 셋을 먼저 읽는다.

**전제**: Phase 1(T1·T2·T3)은 오더 2 와 **병렬 가능**하다 — 시세 테이블은 워크스페이스 스코프가 없고(M2-AD-10) 전부 새 파일이다. Phase 2 이후는 오더 2 완료가 필요하다. (원문은 「API 키가 워크스페이스 설정이다」를 근거로 들었는데, 그 근거는 2026-08-07 리드 결정으로 사라졌다 — 키는 `.env` 전역 설정이다.)

## 수용 기준 (AC)

1. 종목 마스터와 일봉이 로컬 DB 에 쌓이고, 마지막 적재 시각과 실패 내역이 조회된다 (FR-008 · FR-009 · FR-010)
2. 같은 구간을 다시 적재해도 중복 행이 생기지 않는다 (FR-014)
3. 저장된 각 행이 어느 소스에서 왔는지와 어떤 수정주가 정책을 적용했는지를 갖는다 (FR-011 · FR-015)
4. 소스 이름이 `providers/` 밖에서 등장하지 않는다 — 어댑터를 하나 더 붙여도 소비자 코드가 바뀌지 않는다
5. 적재 중 소스 한도에 걸리면 어디까지 받았는지가 기록되고, 다음 실행이 이어받는다 (NFR-007)
6. 데이터 소스 키가 없어도 기동되고, 어떤 기능이 왜 비어 있는지가 데이터로 노출된다 (FR-013 · FR-021)

## 전역 제약

- `원시 시세 데이터는 저장소에 커밋되지 않아야 한다` [Source: .docs/specs/prd.md#NFR-003]
- `외부 데이터 소스의 이용 약관 제약(비상업·제3자 제공 금지 등)을 위반하지 않아야 한다` [Source: .docs/specs/prd.md#NFR-004]
- `백테스트는 같은 입력에 대해 같은 결과를 내야 한다` [Source: .docs/specs/prd.md#NFR-006]
- `외부 소스 호출 한도를 초과하지 않아야 하며, 한도 도달 시 조용히 실패하지 않아야 한다` [Source: .docs/specs/prd.md#NFR-007]
- `데이터 소스 키는 코드·저장소에 포함되지 않고 사용자가 자기 것을 넣는 구조여야 한다` [Source: .docs/specs/prd.md#NFR-002]
- `5·15·30·60분봉은 1분봉에서 합성한다 — 별도 적재하지 않는다` [Source: .docs/specs/prd.md#가정]
- `업무 DB 접근이 SQLAlchemy 동기 Engine (PostgreSQL + psycopg) 기반이라 Service/Repository 의 DB 메서드는 sync def + engine.connect() 가 표준 패턴` [Source: .claude/docs/anti-patterns-backend.md#12]
- `앱 수명 백그라운드 루프 (시세 틱 스트림 poller / Kafka consumer 등) → lifespan 에서 asyncio.create_task + instance attr (self.task) 보관 + shutdown 시 task.cancel() + await task` [Source: .claude/docs/anti-patterns-backend.md#13]
- `테이블명=소문자 snake_case` [Source: CONTEXT.md#결정 로그 2026-07-25] · `Prisma 테이블 접두사: TN_(일반)` [Source: CLAUDE.md#네이밍 규칙]
- 외부 계정 생성·가입·결제는 수행자가 하지 않는다 — 필요하면 절차만 조사해 보고한다

## 태스크

### Phase 1: 기반 (Foundational) — 오더 2 와 병렬 가능

#### T1 (AC: 1) 종목 마스터와 별칭 스키마

**범위**: `tn_instrument` 와 `tn_symbol_alias` 를 만든다. 통합 키는 대리키다 (MD-AD-13).

**Files**
- Modify: `backend-service/app/models/schema.py` (모델 `Instrument`·`SymbolAlias` 추가)
- Create: `backend-service/alembic/versions/0006_instrument_master.py`

**Interfaces**
- Produces: `tn_instrument(instrument_id IDENTITY PK, country VarChar(2), market VarChar(20), symbol VarChar(20), issuer_nm VarChar(200), currency VarChar(5), sector_code VarChar(20), listed_dt Date, delisted_dt Date, is_active VarChar(1), reg_dt, reg_id, mod_dt, mod_id)`
  - 유니크 `ux_instrument_market_symbol (market, symbol)` · 인덱스 `idx_instrument_country_active (country, is_active)`
  - `symbol` 은 **문자열**이다 — 국내 6자리 코드의 선행 0 이 죽지 않게
  - `country` 는 `KR`·`US`, `market` 은 `KOSPI`·`KOSDAQ`·`KONEX`·`NASDAQ`·`NYSE`·`AMEX`
- Produces: `tn_symbol_alias(instrument_id Int, alias_kind VarChar(30), alias_value VarChar(50), valid_from Date, valid_to Date NULL, reg_dt, reg_id, mod_dt, mod_id)`
  - PK `(instrument_id, alias_kind, valid_from)` · 부분 유니크 `ux_symbol_alias_current (alias_kind, alias_value) WHERE valid_to IS NULL`(MD-AD-25 — 티커 재사용 시 과거 캔들이 엉뚱한 종목에 붙는 것을 막는다. 상세: 구현설계 §1.2)
  - `alias_kind` 는 `isin`·`cik`·`cusip`·`figi`·`source:<소스명>`
  - 과거(닫힌) 구간끼리의 겹침은 이 시점엔 DB 제약(`EXCLUDE USING gist`)으로 강제하지 않는다 — `btree_gist` 확장 설치 여부가 배포 환경에 달려 **미결**이다. 애플리케이션 계층에서 삽입 전 겹침을 검사한다

**선행조건**: 오더 1 완료 (통합 앱의 `models/schema.py` 가 하나여야 한다)

**증명 의무**
- `alembic upgrade head` 후 두 테이블의 컬럼·인덱스·제약 목록을 조회해 위 정의와 일치함을 보인다
- 같은 `(alias_kind, alias_value)` 를 **`valid_to IS NULL` 상태로** 서로 다른 종목에 넣으려 시도해 부분 유니크 위반으로 거부되는 것을 보인다 (MD-AD-25)
- 같은 `(alias_kind, alias_value)` 를 한 종목엔 `valid_to` 를 채워 닫고, 다른 종목엔 `valid_to IS NULL` 로 새로 넣어 **성공함**을 보인다(과거 매핑을 닫으면 그 값이 재사용 가능해지는 것이 의도된 동작)

**위험**: `alias_kind` 를 `source:<소스명>` 처럼 합성 문자열로 쓰면 소스 이름이 DB 에 남는다. 이것은 의도된 것이다 — 소스 표기 매핑이 이 표의 존재 이유다. 다만 **애플리케이션 코드가 이 문자열을 파싱하게 두면 안 된다**. 상수는 `providers/` 안에서만 만든다. 추가로 **과거(닫힌) 구간끼리의 겹침은 DB 가 막아주지 않는다** — 겹치는 유효기간을 넣지 않도록 `IngestService`(또는 별칭 등록 경로)가 삽입 전 검사해야 한다(구현설계 §1.2 미결 항목).

#### T2 (AC: 1, 2, 3) 캔들과 적재 이력 스키마

**범위**: 일봉은 단일 테이블(MD-AD-14), 분봉은 월 단위 파티션드(MD-AD-15)로 만든다. 적재 이력은 잡 레코드를 겸한다(M2-AD-12).

**Files**
- Modify: `backend-service/app/models/schema.py` (모델 `DailyBar`·`MinuteBar`·`IngestRun` 추가)
- Create: `backend-service/alembic/versions/0007_market_bars.py` (분봉 파티션드 테이블은 **손으로 작성** — autogenerate 가 다루지 못한다)

**Interfaces**
- Produces: `tn_daily_bar(instrument_id Int, trade_date Date, open/high/low/close Numeric(18,4), volume BigInt, trade_value Numeric(20,2), source VarChar(30), adj_policy VarChar(20), ingest_run_id Int, ingested_at Timestamp)`
  - PK `(instrument_id, trade_date)` · 인덱스 `idx_daily_bar_date (trade_date)` · 인덱스 `idx_daily_bar_run (ingest_run_id)`
  - **감사 컬럼 4종을 두지 않는다** (룰 5 의 "스키마 양쪽 모두 컬럼 정의 안 됨 = 의도된 설계" 예외 — `source`·`ingest_run_id`·`ingested_at` 가 provenance 를 담는다)
  - `adj_policy` 는 `raw`·`adj_split`·`adj_split_div`
- Produces: `tn_minute_bar(instrument_id Int, ts Timestamp, interval_min SmallInt, open/high/low/close Numeric(18,4), volume BigInt, source VarChar(30), adj_policy VarChar(20), ingest_run_id Int, ingested_at Timestamp)`
  - `PARTITION BY RANGE (ts)` · PK `(instrument_id, ts)` · 마이그레이션이 **향후 12개월 파티션을 선행 생성**한다
  - `interval_min` 은 `NOT NULL DEFAULT 1` + `CHECK (interval_min = 1)`(MD-AD-26) — **1분봉 전용**이 PRD 가정(`prd.md#가정` "5·15·30·60분봉은 1분봉에서 합성 — 별도 적재하지 않는다")이다. `IngestService` 는 저장 목적으로 `fetch_minute` 을 항상 `interval_min=1` 로만 호출한다. PK 는 바꾸지 않는다 — 이 컬럼은 방어용 CHECK 이지 새 축이 아니다. 상세: 구현설계 §3.3
- Produces: `tn_ingest_run(run_id IDENTITY PK, source VarChar(30), job_kind VarChar(30), scope VarChar(200), period_from Date, period_to Date, status VarChar(20), cursor VarChar(200), written_rows Int, skipped_rows Int, failed_reason VarChar(1000), workspace_id Int, started_dt Timestamp, finished_dt Timestamp, reg_dt, reg_id, mod_dt, mod_id)`
  - `status` 는 `queued`·`running`·`succeeded`·`failed`·`rate_limited` · `job_kind` 는 `instrument_master`·`daily_bar`·`minute_bar`
  - 인덱스 `idx_ingest_run_source_status (source, status)` · `idx_ingest_run_started (started_dt)`

**선행조건**: 오더 1 완료. T1 과 같은 `models/schema.py` 를 건드리므로 **T1 다음에** 수행한다

**증명 의무**
- `tn_minute_bar` 의 파티션 목록을 조회해 12개월분이 존재함을 보인다
- 파티션 범위 밖 시각의 행을 넣으려 시도해 거부되는 것을 보인다 (런타임 DDL 없이 fail-fast 하는지 확인)
- 같은 `(instrument_id, trade_date)` 를 두 번 넣어 `ON CONFLICT DO UPDATE` 로 갱신되는 것을 보인다 (행 수 불변)
- `tn_minute_bar` 에 `interval_min=5` 인 행을 넣으려 시도해 `CHECK` 위반으로 거부되는 것을 보인다 (MD-AD-26)

**위험**
- 파티션드 테이블의 유니크·PK 는 **파티션 키를 포함해야 한다**. `(instrument_id, ts)` 는 `ts` 를 포함하므로 성립하지만, 나중에 `(instrument_id)` 만의 제약을 추가하려 하면 실패한다.
- `include_object` 필터가 "내 모델에 없는 reflected 테이블"을 제외하므로, 파티션 자식 테이블이 autogenerate 에 잡히지 않는다. 이후 리비전이 파티션을 지우는 diff 를 만들지 않는지 한 번 확인한다.

#### T3 [P] (AC: 4, 6) provider 계약 — 어댑터 0개, 인터페이스만

**범위**: 정규화 모델과 어댑터 Protocol, capability 표현을 정의한다. **이 태스크에는 실제 소스 호출이 없다.**

**Files**
- Create: `backend-service/app/providers/__init__.py` (레지스트리 — 소스명 → 어댑터 팩토리)
- Create: `backend-service/app/providers/models.py` (정규화 모델)
- Create: `backend-service/app/providers/base.py` (Protocol · 도메인 예외)

**Interfaces**
- Produces: 정규화 모델 (Pydantic)
  - `NormalizedInstrument(country: str, market: str, symbol: str, issuer_nm: str, currency: str, sector_code: str | None, aliases: dict[str, str])`
  - `NormalizedBar(symbol: str, market: str, ts: datetime, open: Decimal, high: Decimal, low: Decimal, close: Decimal, volume: int, trade_value: Decimal | None, adj_policy: str)`
  - `NormalizedQuote(symbol: str, market: str, price: Decimal, change: Decimal, change_rate: Decimal, volume: int, asof: datetime)`
  - `Capability(market: str, data_kind: str, available: bool, reason: str | None)` — `data_kind` 는 `instrument_master`·`daily_bar`·`minute_bar`·`quote`·`orderbook`
- Produces: `class MarketDataProvider(Protocol)` — 메서드
  - `capabilities() -> list[Capability]`
  - `list_instruments(market: str) -> list[NormalizedInstrument]`
  - `fetch_daily(symbol: str, market: str, date_from: date, date_to: date) -> list[NormalizedBar]`
  - `fetch_minute(symbol: str, market: str, ts_from: datetime, ts_to: datetime, interval_min: int) -> list[NormalizedBar]`
  - `fetch_quotes(symbols: list[tuple[str, str]]) -> list[NormalizedQuote]`
- Produces: 도메인 예외 `RateLimitExhausted(cursor: str)` · `ProviderResponseInvalid(detail: str)` — 둘 다 `core/exceptions.py` 의 기존 예외 체계를 따른다 (`fastapi.HTTPException` 을 쓰지 않는다 — 룰 10)
- Produces: `get_provider(source: str, api_key: str | None) -> MarketDataProvider` — **키를 인자로 받는다.** 어댑터가 `settings.` 를 읽지 않는다 (MD-AD-20)

**선행조건**: 없음 (T1·T2 와 파일이 겹치지 않아 병렬 가능)

**증명 의무**
- 모든 메서드가 정규화 모델을 반환하도록 타입이 선언돼 있고 `dict` 반환이 없음을 보인다
- `git grep -nE "from providers\." -- 'backend-service/app/services' 'backend-service/app/repositories' 'backend-service/app/routers'` 가 이 시점에 0 hit 임을 기록한다 (이후 태스크의 기준선)

**위험**: Protocol 을 너무 크게 잡으면 소스 하나가 못 채우는 메서드가 생겨 `NotImplementedError` 가 늘어난다. **못 하는 것은 예외가 아니라 `capabilities()` 의 `available=False` 로 표현**한다 — 그래야 화면이 이유를 보여줄 수 있다(FR-021).

**Checkpoint**: 스키마와 계약이 서고, 아직 아무 소스도 붙지 않았다. 이 시점에서 기동이 정상이어야 한다.

---

### Phase 2: 첫 소스와 적재 (AC: 1, 2, 3, 5, 6) — 오더 2 완료 필요

#### T4 (AC: 6) 데이터 소스 키 — ~~워크스페이스 저장~~ → **`.env`** (2026-08-07 리드 결정으로 대체됨)

> 원래 이 태스크는 워크스페이스별 키 표 + 암호화 컬럼을 짓는 것이었다. **짓지 않는다.**
> 제품 정의가 바뀐 것이 근거다 — 2026-07-28 결정으로 이 제품은 오픈소스 로컬 배포판 우선이고
> 「각자 자기 컴퓨터에서 자기 계좌로」 굴린다. 1인 로컬 설치에서 워크스페이스마다 키를 따로 두는
> 것은 의미가 없고, `.env` 가 그 배포 형태의 관용구다. 저장하지 않으므로 저장 암호화(Q6)의
> 대상도 없어졌다 — `.env` 값을 다시 암호화하면 복호화 키를 둘 자리가 결국 같은 `.env` 다.
>
> **감수**: 이 선택은 호스팅 모드에서 성립하지 않는다. 여러 사람이 한 인스턴스를 쓰면 한 사람의
> 키로 전원이 조회하게 되고, 그것은 원 결정의 근거였던 「data.go.kr·KRX 등이 비상업·제3자
> 제공을 금지한다」와 충돌한다. 호스팅 모드를 열 때 다시 판단한다 (`CONTEXT.md` 결정 로그).

**범위**: `.env` 의 키를 읽어 어댑터에 넘기는 자리 하나 (`services/data_key/`). 표·마이그레이션·라우트 없음.

**Files**
- Modify: `backend-service/app/core/config.py` (`MARKET_DATA_GOKR_SERVICE_KEY`·`MARKET_DATA_ALPACA_KEY`·`MARKET_DATA_OPENFIGI_KEY`)
- Modify: `backend-service/app/services/data_key/data_key_service.py` · `app/.env.example`

**Interfaces**
- Produces: `DataKeyService.get_key(workspace_id: int | None, source: str) -> str | None` — `.env` 값. 비면 `None`
  (`workspace_id` 인자는 호출부 시그니처를 흔들지 않으려고 남긴다. 위 감수를 되돌릴 때 값이 들어올 자리이기도 하다)
- Produces: `DataKeyService.unavailable_reason(source)` — 「`.env` 의 어느 항목을 채워라」 + 발급 경로. **키 값도 앞자리도 싣지 않는다**

**선행조건**: T3 (레지스트리·어댑터 계약). 오더 2·Q6 선행은 해소됐다 — 워크스페이스도 암호화도 쓰지 않는다.

**증명 의무** (저장이 아니라 **유출** 축으로 옮겨갔다)
- 가짜 키를 꽂고 실제 코드 경로를 태워, 그 키 문자열이 **로그·API 응답·예외 메시지**에 나타나지 않음을 보인다
- 그물을 빼면 빨개지는 것을 뮤테이션으로 보인다
- `.env.*` 가 실제로 gitignore 되고 추적 중인 env 파일이 `.env.example` 뿐임을 보인다

**위험**
- 저장 암호화를 하지 않으므로 `.env` 의 **파일 권한과 gitignore 가 방어의 전부**다. 그 둘이 실제로 성립하는지를 매 실행이 다시 확인해야 한다 (`scripts/verify_data_key_env_boundary.py`).
- data.go.kr 은 인증키를 **쿼리스트링**으로 받는다 — 상류 오류 문자열에 URL 이 통째로 실리므로 로그·트레이스백이 주 유출 경로다.

#### T5 (AC: 1, 3, 4) 첫 어댑터 — 국내 공공 데이터 API

**범위**: 국내 종목 마스터와 일봉을 가져오는 어댑터 하나를 만든다. 소스 사정(인증·페이지네이션·한도)은 전부 이 안에서 끝난다. 대상 소스는 **data.go.kr 금융위 API** 다 — #230 이 #224 의 KRX 오픈API 권고를 "제3자 제공 금지 조항 때문에 오픈소스 배포에 부적합"으로 뒤집었다.

**Files**
- Create: `backend-service/app/providers/data_go_kr/__init__.py` · `client.py` · `adapter.py` · `mapper.py`

**Interfaces**
- Consumes: `MarketDataProvider` Protocol · 정규화 모델 (T3)
- Produces: `DataGoKrProvider` — `capabilities()` 가 `KOSPI`·`KOSDAQ`·`KONEX` × `instrument_master`·`daily_bar` 를 `available=True`, `minute_bar`·`quote`·`orderbook` 을 `available=False` + 사유로 반환한다
- Produces: 레지스트리 등록 — `get_provider("data_go_kr", key)` 로 얻는다. 이 문자열 상수는 `providers/__init__.py` 안에서만 정의된다
- Produces: `mapper.py` 가 정규화 모델로 변환하기 **직전** 응답 내 중복 타임스탬프를 병합한다(MD-AD-24 — `open=first·high=max·low=min·close=last·volume=max`, 구현설계 §4.4)

**선행조건**: T3, T4

**증명 의무**
- 실제 소스에서 종목 마스터 1회, 특정 종목 일봉 1개월을 받아 정규화 모델로 변환한 결과를 제시한다. **원시 응답은 저장소에 커밋하지 않는다**(NFR-003) — 건수와 몇 행의 값만 본문에 적는다
- 받은 값 3건을 소스 웹 화면 값과 대조해 일치함을 보인다 (SC-004 의 사전 확인)
- 잘못된 형태의 응답(필드 누락)을 만들어 `ProviderResponseInvalid` 로 거부되고 그 행만 버려지는 것을 보인다
- `capabilities()` 출력 표를 제시한다
- 소스가 제공하는 식별자(단축코드·ISIN 등)가 `NormalizedInstrument.aliases` 로 채워지는 것을 보인다
- 같은 타임스탬프가 두 번 든 응답을 인위로 만들어 병합 규칙대로 한 행으로 합쳐지는 것을 보인다 (MD-AD-24)

**위험**
- API 키 발급에 가입이 필요하다. **수행자는 가입하지 않는다** — 필요한 절차만 정리해 보고하고, 키는 사용자가 넣는다.
- 한도는 10,000/일이다(#230). 개발 중 반복 호출로 한도를 소진하면 그날 검증이 막힌다 — 응답을 로컬 파일로 한 번 받아 두고 반복 검증은 그 파일로 한다(그 파일은 커밋하지 않는다).
- 이 소스가 무수정 원본을 주는지 수정주가를 주는지 확인하고, 그 결과를 `adj_policy` 값에 반영한다. 확인하지 않고 `raw` 로 박으면 백테스트가 조용히 틀어진다.

#### T6 (AC: 1, 2, 5) 적재 워커와 잡 실행

**범위**: `tn_ingest_run` 을 잡으로 삼아 폴링·실행·재개하는 백그라운드 워커를 만든다 (M2-AD-12).

**Files**
- Create: `backend-service/app/managers/ingest/ingest_worker_manager.py`
- Create: `backend-service/app/services/ingest/ingest_service.py` · `app/repositories/ingest/ingest_repository.py` · `app/schemas/ingest/ingest_schema.py`
- Create: `backend-service/app/routers/ingest/ingest_router.py`
- Create: `backend-service/app/core/calendar.py` — `get_market_calendar(market: str) -> ExchangeCalendar`, `exchange_calendars` 를 감싸는 유일한 진입점(MD-AD-21, 구현설계 §1.3)
- Modify: `backend-service/app/core/container.py` · `app/modules.py`
- Modify: `backend-service/pyproject.toml` — `exchange_calendars`(Apache-2.0) 의존성 추가. 라이선스 판정 전문: [시세-데이터-파이프라인 §1.1](../4-아키텍처/시세-데이터-파이프라인.md)

**Interfaces**
- Consumes: `get_provider(source, key)` (T3) · `DataKeyService.get_key` (T4) · `tn_ingest_run`·`tn_daily_bar`·`tn_minute_bar` (T2) · `tn_instrument`·`tn_symbol_alias` (T1) · `get_market_calendar(market)`
- Produces: `IngestService.enqueue(job_kind: str, source: str, scope: str, period_from: date, period_to: date, workspace_id: int) -> int` — `run_id` 반환, `status='queued'`
- Produces: `IngestService.list_runs(skip: int, take: int, filters: dict) -> tuple[list, int]` — 라우터가 `{items, total_count}` wrapper 로 감싼다 (룰 6·7)
- Produces: **심볼 해석의 소유자는 `IngestService` 다** — `NormalizedBar.symbol`·`market` 을 `tn_instrument`(그리고 필요 시 `tn_symbol_alias`)로 `instrument_id` 에 매핑한다. 매핑되지 않는 심볼은 버리지 않고 `skipped_rows` 로 집계하고 `failed_reason` 에 건수를 남긴다
- Produces: **일봉 적재는 매 실행마다 DB 상 마지막 저장 거래일을 재요청한다**(MD-AD-22, 구현설계 §4.5) — `fetch_daily` 의 `date_from` 을 "이 종목의 마지막 저장 `trade_date`"로 잡는다. upsert(MD-AD-16)가 갱신한다
- Produces: `IngestService.find_gaps(instrument_id: int, date_from: date, date_to: date) -> list[date]` — 캘린더 세션 목록과 `tn_daily_bar.trade_date` 를 대조한 차집합, **저장하지 않고 매 호출 계산**(MD-AD-23, 구현설계 §7.5)
- Produces: 라우트 `POST /ingest/run` (수동 적재 요청) · `GET /ingest/run` (적재 상태 목록) · `GET /ingest/gaps`(`instrument_id`·기간 쿼리 — MD-AD-23)

**선행조건**: T1, T2, T5

**증명 의무**
- 적재 1회 실행 후 `tn_ingest_run` 의 `written_rows` 와 실제 테이블 증가 행 수가 일치함을 보인다
- 같은 구간을 다시 적재해 **행 수가 늘지 않고** `skipped_rows` 가 증가함을 보인다 (AC-2)
- 종목 마스터에 없는 심볼이 섞인 입력을 넣어 그 행만 `skipped_rows` 로 집계되고 나머지는 적재되는 것을 보인다
- 한도 소진을 강제로 발생시켜(어댑터에 임시 한도를 걸어) `status='rate_limited'` 와 `cursor` 가 기록되고, 다음 실행이 그 지점부터 이어받는 것을 보인다. 임시 변경은 되돌린 커밋을 남긴다 (AC-5)
- 워커가 도는 동안 API 응답이 지연되지 않음을 확인한다 — 벌크 insert 가 `run_in_threadpool` 로 감싸져 있음을 코드로 보이고, 적재 중 다른 엔드포인트 호출이 정상 응답함을 보인다
- 앱을 두 번 기동해도 같은 잡이 중복 실행되지 않음을 보인다 (advisory lock)
- 이미 적재된 종목의 마지막 거래일 값을 의도적으로 바꾼 뒤 재적재를 1회 더 돌려, **그 거래일 행이 최신 값으로 덮어써지는 것**을 보인다 (MD-AD-22)
- 캘린더상 거래일인데 `tn_daily_bar` 에 없는 날짜를 인위로 만들어 `find_gaps` 가 그 날짜를 반환하고, 휴장일은 반환하지 않는 것을 보인다 (MD-AD-23)

**위험**
- `asyncio.create_task` 로 만든 태스크를 참조 없이 두면 GC 되어 조용히 죽는다. `lifespan` 에서 instance attr 로 보관하고 shutdown 에 `cancel()` + `await` 한다 [Source: anti-patterns 룰 13 관련 가이드].
- 잡 폴링 루프에서 예외가 한 번 나면 워커 전체가 멈출 수 있다. 룰 9 의 "Daemon loop continuation" 예외(로그 + back-off + continue)를 적용하되, **원본 예외를 마스킹하지 않는다**.
- `find_gaps` 를 전 종목에 대해 상시 배치로 돌리면 캘린더 대조 비용이 누적된다 — M2 는 온디맨드(종목 선택 시)로 한정한다. 상시 리포트가 필요해지면 별도 태스크로 분리한다.

#### T7 (AC: 1) 스케줄 적재 — 스케줄러 job_kind 확장

**범위**: 기존 스케줄러가 리포트 발송 외의 잡도 걸 수 있게 확장하고, 일봉 적재를 정기 잡으로 등록한다.

**Files**
- Modify: `backend-service/app/models/schema.py` (`Scheduler` 에 `job_kind` VarChar(30) default `activity_report` · `job_params` JSONB 추가)
- Create: `backend-service/alembic/versions/0009_scheduler_job_kind.py`
- Modify: `backend-service/app/managers/scheduler_manager.py` (`job_kind` 로 실행 대상 분기)
- Modify: `backend-service/app/services/scheduler/scheduler_service.py`
- Modify: `backend-service/app/schemas/scheduler/scheduler_schema.py`

**Interfaces**
- Consumes: `IngestService.enqueue(...)` (T6)
- Produces: `job_kind='daily_bar_ingest'` 스케줄이 지정 시각에 적재 잡을 큐에 넣는다

**선행조건**: T6, 오더 1 완료(스케줄러가 통합 앱에 있어야 한다)

**증명 의무**
- 기존 `activity_report` 스케줄이 컬럼 추가 후에도 그대로 동작함을 보인다 (추가 우선 — 기존 행은 기본값으로)
- 적재 스케줄을 1~2분 뒤로 등록해 실제로 잡이 큐에 들어가는 것을 보인다
- 요청 밖(cron) 실행에서 하류 호출이 fail-closed 로 막히지 않음을 보인다 — 스케줄 행의 워크스페이스가 컨텍스트에 실리는지 확인한다

**위험**: `job_params` 를 JSONB 로 두면 스키마 검증이 사라진다. `job_kind` 별 Pydantic 모델로 파싱한 뒤 쓰고, 파싱 실패 시 그 잡만 건너뛴다(부팅 전체를 막지 않는다 — 기존 매니저의 행별 격리와 같은 방침).

**Checkpoint**: 국내 종목 마스터와 일봉이 실제로 쌓이고, 적재 상태가 조회되며, 정기 적재가 걸린다.

---

### Phase 3: 소비 경로 (AC: 4, 6)

#### T8 [P] (AC: 4) 적재본 읽기 — 갈래 1

**범위**: 차트·백테스트·봇이 쓰는 캔들 조회 경로를 만든다. **이 경로는 provider 를 주입받지 않는다** (MD-AD-19).

**Files**
- Create: `backend-service/app/repositories/bar/bar_repository.py` · `app/services/bar/bar_service.py` · `app/routers/bar/bar_router.py` · `app/schemas/bar/bar_schema.py`
- Modify: `backend-service/app/core/container.py` · `app/modules.py`

**Interfaces**
- Consumes: `tn_daily_bar`·`tn_minute_bar`·`tn_instrument` (T1·T2)
- Produces: `BarService.daily(symbol: str, market: str, date_from: date, date_to: date, limit: int) -> BarsOut` — 내부에서 `(market, symbol)` 을 `instrument_id` 로 해석한다. 미등록 종목은 `NotFoundError`
- Produces: `BarService.minute(symbol: str, market: str, ts_from: datetime, ts_to: datetime, interval_min: int, limit: int) -> BarsOut` — `interval_min` 이 1 이 아니면 1분봉에서 **합성**한다 (별도 적재하지 않는다)
- Produces: `BarsOut(items: list[BarOut], total_count: int, source: str, adj_policy: str, asof: datetime)` — 화면이 출처·기준 시각을 표시할 수 있게 한다 (FR-019)
- Produces: 라우트 `GET /bar/daily` · `GET /bar/minute` — `date_from`·`date_to`(또는 `ts_from`·`ts_to`) 필수, `limit` 상한 초과 시 400

**선행조건**: T2 (T5·T6 없이도 착수 가능 — DB 만 읽는다. 값 대조 검증만 적재 이후로 미룬다)

**증명 의무**
- 적재된 종목의 일봉을 조회해 값이 소스와 일치함을 보인다 (SC-004)
- 응답에 `source` 와 `adj_policy` 가 실려 있음을 보인다
- 5분봉 합성 결과를 같은 구간 1분봉으로 직접 계산한 값과 대조해 일치함을 보인다
- `limit` 상한을 넘는 요청이 거부됨을 보인다
- 이 모듈의 DI 등록에 provider 가 없음을 코드로 보인다

**위험**: 캔들은 리스트 응답이라 룰 6(페이지네이션)과 룰 7(list wrapper) 대상이다. 차트는 페이지가 아니라 기간 윈도로 자르므로 `skip/take` 대신 **기간 + 상한**이 페이지네이션 역할을 한다 — 이 해석을 라우터 docstring 에 남기고 리뷰에서 근거로 제시한다.

#### T9 [P] (AC: 4, 6) 일괄 조회와 실시간 슬롯 — 갈래 3 · 갈래 2

**범위**: 사이드바 다종목 시세와 봇 주기 조회를 위한 일괄 조회를 만들고(FR-048·049), 실시간 구독은 **슬롯 1개 자료구조**로 자리를 만든다(FR-047).

**Files**
- Create: `backend-service/app/services/quote/quote_batch_service.py` · `app/routers/quote/quote_router.py` · `app/schemas/quote/quote_schema.py`
- Create: `backend-service/app/managers/realtime/single_subscription.py`
- Modify: `backend-service/app/core/container.py` · `app/modules.py`

**Interfaces**
- Consumes: `get_provider(source, key)` (T3) · `DataKeyService.get_key` (T4)
- Produces: `QuoteBatchService.quotes(symbols: list[tuple[str, str]]) -> QuotesOut` — TTL 캐시 포함. **구독 API 를 갖지 않는다**
- Produces: `SingleSubscription.switch(symbol: str, market: str) -> None` — 새 구독이 들어오면 기존을 해제하고 교체한다. **동시에 두 종목을 구독하는 메서드가 존재하지 않는다**
- Produces: `SingleSubscription.current() -> tuple[str, str] | None`
- Produces: 라우트 `POST /quote/batch`

**선행조건**: T5

**증명 의무**
- 같은 종목을 TTL 안에 여러 번 조회해 외부 호출이 1회임을 보인다 (호출 카운터 로그)
- `SingleSubscription` 에 두 종목을 연속 `switch` 해 이전 구독이 해제되는 것을 보인다
- 브로커 계좌가 없는 상태에서 실시간 패널이 `capabilities()` 의 사유("계좌 미연동")를 화면에 표시할 수 있게 데이터가 흐르는지 확인한다 (AC-6)

**위험**: 실시간 채널은 증권사 계좌·API 신청이 전제다. **수행자는 계좌를 개설하지 않는다.** 이 태스크는 슬롯 구조와 capability 사유 전달까지이며, 실제 브로커 어댑터는 계좌 확보 후 별도 작업이다.

**Checkpoint**: 세 갈래가 각각 자기 경로로 동작하고, 소비자가 provider 를 주입받지 못하는 것이 배선으로 확인된다.

---

### Phase 4: 마무리 (Polish)

#### T10 (AC: 4) 경계 규율 문서화와 검출 추가

**범위**: provider 경계와 대용량 시계열 예외를 룰 SoT 에 반영하고, 살아있는 문서를 갱신한다.

**Files**
- Modify: `.claude/docs/anti-patterns-backend.md` (룰 5 예외에 "대용량 시계열 테이블" 추가 · 「provider 경계 침범」 룰 신설)
- Modify: `.claude/agents/review-backend.md` · `backend-service/CLAUDE.md` (헤더 일치 규칙상 3곳 동시)
- Modify: `.docs/4-아키텍처/시세-데이터-파이프라인.md` (§5 열린 항목 중 해소된 것 갱신 — 캔들 조회 계약 분리)
- Modify: `.docs/4-아키텍처/시세적재-구현설계.md` (완료 단계 표시)
- Modify: `.docs/specs/prd.md` (FR-008~015·046~049 완료 반영)
- Modify: `.gitignore` (적재 원시 응답 캐시 경로)

**선행조건**: T8, T9

**증명 의무**
- 신설 룰의 Detection 명령을 실행해 0 hit 임을 보인다 — `git grep -nE "from providers\.[a-z_]+" -- 'backend-service/app/services' 'backend-service/app/repositories' 'backend-service/app/routers'`
- anti-patterns 전 룰의 Detection 을 실행해 hit 표를 제시한다
- `git status` 로 원시 시세 파일이 추적되지 않음을 보인다 (NFR-003)

**위험**: 룰 번호는 오더 1 이 추가하는 「모듈 경계 침범」 다음 번호다. 착수 시점에 현재 룰 번호를 확인하고 다음 번호를 쓴다 — 하드코딩된 번호를 그대로 쓰면 충돌한다.

## Dev Notes — 수행자가 알아야 할 맥락

- **백테스트가 로컬 DB 를 읽는 이유**: 외부 API 는 호출 한도로도 불가능하고, 더 중요하게는 소스가 수정주가를 나중에 재계산하므로 **재현되지 않는다**. 무수정 원본을 우리가 보관하는 것이 NFR-006 의 근거다. [Source: .docs/4-아키텍처/시세-데이터-파이프라인.md#0, #3]
- **국내는 전 종목이 오히려 싸다**: 국내 공식 오픈API 는 날짜별 전종목 스냅샷이라 종목 수가 늘어도 호출 수가 늘지 않는다. 미국은 종목당 조회라 유니버스 크기가 곧 비용이다. [Source: .docs/4-아키텍처/시세-데이터-파이프라인.md#1]
- **소스별 한도**: data.go.kr 금융위 10,000/일 · OpenDART 20,000/일 · ECOS 3분당 300회 · KOSIS 분당 200회. 잡 분할 크기를 정하는 입력이다. [Source: 이슈 #230]
- **실시간 구독 상한**: 조사 기준 동시 구독 40건, 실질 20종목. 그래서 "보고 있는 한 종목만 구독"이 규약이 아니라 자료구조가 된다. [Source: 이슈 #227]
- **시세는 워크스페이스 스코프가 아니다**: 캔들을 테넌트마다 복제하면 700만 행 × N 이 된다. NFR-005 의 명시적 예외이며, 호스팅 전환 시 재검토 대상이다. [Source: .docs/4-아키텍처/m2-전환설계.md#M2-AD-10]
- **LLM 대화용 시세 도구는 그대로 둔다**: `market-data-mcp-service` 의 `market_ohlc` 는 최신순 1~120개 계약이며, LLM 컨텍스트 보호가 목적이다. 적재용 기간 지정 계약과 섞지 않는다. [Source: market-data-mcp-service/app/routers/market/market_router.py:56-61]
- **미국 소스는 미확정이다**: CONTEXT 결정 로그의 "미국 Twelve Data" 는 #230 표에서 오픈소스 배포 부적합으로 나온다. 이 오더는 국내 어댑터 하나까지만 다루며, 미국 어댑터는 소스 확정 후 별도 작업이다. [Source: 이슈 #230 · .docs/4-아키텍처/시세적재-구현설계.md#Q9]
- **거래일 캘린더는 `exchange_calendars` 로 해결한다** (#279, MD-AD-21): Apache-2.0, 가입 불요, XKRX(한국) 내장·2050년까지 선계산. 미국은 `XNAS` 가 없어 `XNYS` 하나로 NASDAQ·NYSE·AMEX 를 전부 판정한다. T6 이 `app/core/calendar.py` 로 진입점을 만든다. [Source: .docs/4-아키텍처/시세-데이터-파이프라인.md#1.1]
- **분봉은 1분봉만 저장한다** (#279, MD-AD-26): "5·15·30·60분봉은 1분봉에서 합성 — 별도 적재하지 않는다"는 전역 제약(위 참조)이 스키마 `CHECK (interval_min = 1)` 로 강제된다. `fetch_minute` 의 `interval` 인자를 저장 목적으로 1이 아닌 값으로 호출하면 안 된다.

## 의존·실행 순서

- Phase 1: **T1 → T2** (같은 `models/schema.py`), **T3 는 병렬**. Phase 1 전체가 오더 2 와 병렬 가능하다.
- Phase 2: T4 ← T3 (오더 2·Q6 선행은 2026-08-07 결정으로 해소) · T5 ← T3·T4 · T6 ← T1·T2·T5 · T7 ← T6
- Phase 3: T8 ← T2 · T9 ← T5 — **T8 ∥ T9 병렬 가능**
- Phase 4: T10 ← T8·T9
