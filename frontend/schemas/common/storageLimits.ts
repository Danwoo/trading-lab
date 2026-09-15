// schemas/common/storageLimits.ts
/**
 * 저장 컬럼이 정하는 천장 — 백엔드 `backend-service/app/schemas/common_schema.py` 와 같은 값이다.
 *
 * 화면이 이 선을 안 그으면 폼은 통과시키고 저장에서 422 가 나 사용자가 두 번 왕복한다.
 * 값을 파일마다 다시 적으면 한쪽만 고쳐져 층이 어긋나므로 여기 한 곳에 둔다.
 */

/** `integer` 컬럼 */
export const INT32_MAX = 2_147_483_647;
/** `bigint` 컬럼 — JS 가 정확히 셀 수 있는 데까지만 쓴다 */
export const BIGINT_MAX = Number.MAX_SAFE_INTEGER;
/** `Numeric(18,2)` 안쪽의 보수적인 상한 */
export const MONEY_MAX = 1e15;
/** `Numeric(6,2)` 컬럼이 담는 최대 */
export const NUMERIC_6_2_MAX = 9999.99;
/** 비중·비율은 전체의 몫이라 100% 를 넘을 수 없다 */
export const PERCENT_MAX = 100;
