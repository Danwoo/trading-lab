// @vitest-environment jsdom — 실제 DataGrid(devextreme-react/data-grid)를 렌더해 셀 텍스트를
// 읽으므로 DOM 이 필요하다. `tests/setup.ts` 가 devextreme 테마 초기화 인터벌을 안전하게
// 정리해 두므로(#342) 이 파일이 그 위험을 새로 만들지 않는다 — 오히려 이 파일이 바로 그
// setup.ts 가 계속 필요한 이유 중 하나다(setup.ts 상단 주석의 2026-08-04 재확인 참고).
//
// #303 — 관리 화면 타임스탬프: 쓰기(+9h 시프트)와 읽기(UTC 벽시계 잘림) 버그 두 개가 서로
// 상쇄돼 있던 상태를 재현하고, 수정된 파이프라인(쓰기=new Date, 읽기=인스턴트 그대로)이
// 이슈 본문의 실측 표와 같은 결과를 내는지 검증한다.
//
// 이 파일은 단일 소스 파일이 아니라 **저장 → 전선(API JSON) → 그리드 표시** 파이프라인 전체를
// 검증하는 회귀 테스트라 tests/ 의 1:1 소스 미러링 규약 밖에 둔다(tests/regressions/, 신설).
//
// 표시 단계는 실제 DevExtreme `DataGrid`+`Column`(`devextreme-react/data-grid`, 관리 화면
// 그리드가 그대로 쓰는 공개 패키지)을 렌더해 검증한다 — 예전엔 devextreme 의 비공개 내부 모듈을
// 딥임포트해 흉내 냈으나(`devextreme/cjs/core/utils/date_serialization.js`·
// `devextreme/cjs/localization/date.js`), #341 O8(devextreme 걷어내기)이 테스트 코드의 devextreme
// 딥임포트도 대상으로 잡아(⑥, `tests/regressions/devextreme-internal.d.ts` 도 함께 삭제) 공개
// 컴포넌트 렌더로 바꿨다. `format="yyyy-MM-dd HH:mm:ss"` 를 명시하는 것은 예전과 동일 —
// 실제 관리 화면 컬럼(`AdminUserContainer.tsx` 등)은 이 포맷을 지정하지 않고 DevExtreme 로케일
// 기본값을 쓰지만, 이 테스트의 관심사는 "그 포맷일 때 지역/서머타임 변환이 맞는가"이지 앱의
// 기본 로케일 포맷 자체가 아니다 — 아래 "그리드 ↔ 상세 화면" 절이 같은 포맷 문자열로 두 경로
// (그리드 렌더링 · `formatDate()`)를 대조하는 것도 이 때문이다.
//
// 부정 통제(쓰기만 고침·읽기만 고침)가 이 테스트의 핵심이다 — 한쪽만 고치면 정확히 어디서,
// 얼마나 틀어지는지 이 파일이 숫자로 잡아야 한다.
//
// #372 — 이 파일이 예전엔 쓰기·읽기를 파일 안의 지역 람다(`writeFixed = (d) => new Date(d)` 등)로
// **모사**해, 실제 라우트가 `getKSTTime()` 을 다시 쓰기 시작해도 이 테스트는 그대로 초록이었다.
// "버그" 쪽 쓰기는 이제 실제 프로덕션 함수 `getKSTTime()`(`@/utils/common/timeUtils`, 저장에
// 오용되면 정확히 이 버그를 재현하는 그 함수)을 직접 import 해서 쓴다 — 손으로 다시 구현한
// `addHours(d, 9)` 가 아니라, `getKSTTime()` 의 실제 동작이 바뀌면 이 테스트도 함께 움직인다.
// "고침" 쪽 쓰기(`new Date(d)`)·읽기(`d.toISOString()`)는 그 자체가 이미 프로덕션 코드다 —
// #303 이 한 일이 정확히 "래퍼 함수를 걷어내고 빌트인을 직접 쓴다"였으므로 감쌀 함수가 없다
// (`app/api/common/system/adminuser/[email]/route.ts:109` 의 `mod_dt: new Date()` 참고). "버그"
// 쪽 읽기(`formatDateTime()`)는 #303 이 코드베이스에서 완전히 지운 함수라 더는 import 할 대상이
// 없다 — 옛 버그 모양을 문서화하는 용도로만 인라인에 남긴다(아래 주석).
//
// 라우트가 `getKSTTime()` 을 다시 쓰기 시작하는 재유입 자체를 막는 것은 이 파일의 역할이
// 아니다 — 그건 `scripts/check-no-kst-time-in-routes.js`(#372, `app/api/**` 렉시컬 스캔)의
// 몫이다. 이 파일은 "쓰면 실제로 얼마나 틀어지는가"를 숫자로 증명한다.

import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";
// 배럴(@/components/shared/DataGrid)이 아니라 직접 경로 — 배럴은 DualSelectGrid 를 거쳐
// 이 테스트와 무관한 모듈까지 끌고 온다(#341 ② 배럴 fan-out).
import { MasterGrid } from "@/components/shared/DataGrid/MasterGrid";
import type { LegacyGridSource } from "@/hooks/shared/legacyGridSource";
import { getKSTTime } from "@/utils/common/timeUtils";
// 상세 화면 TableCell 이 쓰는 것과 같은 공용 포맷터 — 그리드와 상세가 같은 값을 쓰는지
// 대조하는 절(아래 "그리드 ↔ 상세 화면" describe)에서만 쓴다.
import { formatDate } from "@/utils/common/formatters/date";

// 실제 인스턴트 — 서울 10:00 / 뉴욕(전날) 21:00 / UTC 01:00 (이슈 #303 실측 표와 동일 시각).
const REAL_INSTANT = new Date("2026-07-30T01:00:00.000Z");

// 쓰기 경로
const writeBuggy = (d: Date) => getKSTTime(d); // #303 이전: 저장 직전에 이 호출이 있었다 (+9h 시프트)
const writeFixed = (d: Date) => new Date(d); // #303 이후: 인스턴트 그대로 저장 — 프로덕션 코드 그 자체.

// 읽기 경로 — API 가 클라이언트에 보내는 "전선 위 값"(JSON 문자열)
// #303 이전: formatDateTime()(이제 코드베이스에서 삭제됨) 이 하던 일 — UTC 벽시계로 잘라 보냄.
const readBuggy = (d: Date) => d.toISOString().replace("T", " ").substring(0, 19);
const readFixed = (d: Date) => d.toISOString(); // #303 이후: 인스턴트 그대로 — 프로덕션 코드 그 자체.

// jsdom 에는 ResizeObserver 도 레이아웃 엔진도 없다 — 가상 스크롤(`@tanstack/react-virtual`,
// DataTable 내부)이 둘 다 필요하다. 없으면 렌더가 막히거나(생성자 부재) 스크롤 컨테이너 높이를
// 0 으로 읽어 본문을 통째로 비운다. `WatchlistContainer.test.tsx` 가 쓰는 것과 같은 흉내다.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeAll(() => {
  vi.stubGlobal("ResizeObserver", ResizeObserverStub);
  Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, value: 600 });
  Object.defineProperty(HTMLElement.prototype, "offsetHeight", { configurable: true, value: 600 });
});

/**
 * 그리드가 받는 데이터 원천 스텁 — `useMasterGridData()` 가 돌려주는 모양 그대로 손으로 만든다.
 * 이 테스트가 보는 것은 **표시 변환**이지 데이터 적재가 아니라, 훅을 돌리지 않고 행을 직접 꽂는다.
 */
function stubSource(rows: Array<{ dt: string }>): LegacyGridSource<{ dt: string }> {
  return {
    rows,
    totalCount: rows.length,
    isLoading: false,
    // 이 스텁은 "정상 응답 0건 이상" 상태다 — 실패를 싣지 않는다(실으면 그리드가 행 대신
    // 「목록을 읽지 못했습니다」를 그려 이 파일이 보려는 표시 변환 자체가 사라진다).
    error: null,
    query: { skip: 0, take: 20 },
    pageIndex: 0,
    pageSize: 20,
    setPage: () => {},
    setPageSize: () => {},
    setSort: () => {},
    setFilter: () => {},
    reload: () => {},
    fetchAll: async () => rows,
    keyField: "dt",
  };
}

/**
 * wire 값을 관리 화면이 실제로 쓰는 그리드(`MasterGrid` → `DataTable` 커널)로 렌더해 셀
 * 텍스트를 읽는다. #341 이전에는 `devextreme-react/data-grid` 를 마운트했다 — 그 라이브러리가
 * 사라졌으므로 같은 자리를 지금의 그리드가 대신한다.
 *
 * **이 이관으로 아래 「그리드 ↔ 상세 일치」 절의 성격이 바뀐다**: 두 경로가 이제 같은 공용
 * 포맷터(`formatDate`)를 쓰므로, 그 절은 "서로 다른 두 구현이 우연히 같은 값을 내는가"가 아니라
 * "그리드가 그 공용 포맷터를 계속 거치는가"를 잠근다. 누가 그리드 셀에 자체 변환을 다시
 * 들이면(예: `String(value)`) 그 절이 빨간불을 낸다 — 그게 이 절이 지키려는 회귀다.
 */
async function renderGridCell(wire: string): Promise<string> {
  const { container, unmount } = render(
    <MasterGrid
      dataSource={stubSource([{ dt: wire }])}
      columns={[{ dataField: "dt", caption: "일시", dataType: "datetime" }]}
    />,
  );
  try {
    let text = "";
    await waitFor(() => {
      text = container.querySelector("tbody tr[aria-rowindex] td")?.textContent ?? "";
      expect(text).not.toBe("");
    });
    return text;
  } finally {
    unmount();
    cleanup();
  }
}

const ORIGINAL_TZ = process.env.TZ;
afterEach(() => {
  process.env.TZ = ORIGINAL_TZ;
});

/** wire 값을 주어진 타임존을 쓰는 뷰어(브라우저) 앞에서 렌더링한 결과. */
async function renderAsViewerIn(tz: string, wire: string): Promise<string> {
  process.env.TZ = tz;
  return renderGridCell(wire);
}

const VIEWER_TZS = ["UTC", "America/New_York", "Asia/Seoul"] as const;

/** VIEWER_TZS 각각에 대해 renderAsViewerIn 을 순차 실행해 { tz: 렌더결과 } 맵을 만든다. */
async function renderAcrossViewers(wire: string): Promise<Record<string, string>> {
  const rendered: Record<string, string> = {};
  for (const tz of VIEWER_TZS) {
    rendered[tz] = await renderAsViewerIn(tz, wire);
  }
  return rendered;
}

describe("#303 — 관리 화면 타임스탬프 (쓰기 +9h 시프트 · 읽기 UTC 벽시계 잘림 상쇄)", () => {
  it("현행(수정 전): 쓰기·읽기 둘 다 버그 — 모든 타임존에서 KST 자릿수로 보인다 (이슈 표 그대로)", async () => {
    const wire = readBuggy(writeBuggy(REAL_INSTANT));
    const rendered = await renderAcrossViewers(wire);

    expect(rendered).toEqual({
      UTC: "2026-07-30 10:00:00",
      "America/New_York": "2026-07-30 10:00:00",
      "Asia/Seoul": "2026-07-30 10:00:00",
    });
  });

  it("부정 통제 — 읽기만 고침: 쓰기가 여전히 버그면 서울 뷰어에게 9시간 미래가 보인다", async () => {
    const wire = readFixed(writeBuggy(REAL_INSTANT));
    const rendered = await renderAcrossViewers(wire);

    expect(rendered).toEqual({
      UTC: "2026-07-30 10:00:00",
      "America/New_York": "2026-07-30 06:00:00",
      // 실제 서울 시각은 10:00 인데 19:00 로 보인다 — 9시간 미래 회귀 (이슈가 경고한 바로 그 증상).
      "Asia/Seoul": "2026-07-30 19:00:00",
    });
    expect(rendered["Asia/Seoul"]).not.toBe("2026-07-30 10:00:00");
  });

  it("부정 통제 — 쓰기만 고침: 저장은 맞아도 표시가 뷰어 타임존에 반응하지 않아 뉴욕·서울 모두 틀린다", async () => {
    const wire = readBuggy(writeFixed(REAL_INSTANT));
    const rendered = await renderAcrossViewers(wire);

    // 세 타임존 모두 같은 문자열이 그대로 인쇄된다 — 타임존 표기가 없는 문자열은 "로컬로 파싱 →
    // 같은 로컬로 포맷"이라 파싱·표시가 항상 같은 오프셋을 쓰고 그대로 상쇄된다. 즉 표시가
    // 뷰어 타임존에 전혀 반응하지 않는다는 뜻이고, 이는 UTC 뷰어에게만 우연히 맞는 값이다.
    expect(rendered.UTC).toBe(rendered["America/New_York"]);
    expect(rendered.UTC).toBe(rendered["Asia/Seoul"]);
    expect(rendered.UTC).toBe("2026-07-30 01:00:00");
    // 뉴욕 실제 시각은 07/29 21:00, 서울 실제 시각은 07/30 10:00 인데 둘 다 01:00 으로 보인다 (오답).
    expect(rendered["America/New_York"]).not.toBe("2026-07-29 21:00:00");
    expect(rendered["Asia/Seoul"]).not.toBe("2026-07-30 10:00:00");
  });

  it("둘 다 고침(수정 후): 실제 인스턴트가 각 뷰어 타임존으로 정확히 변환돼 보인다", async () => {
    const wire = readFixed(writeFixed(REAL_INSTANT));
    const rendered = await renderAcrossViewers(wire);

    expect(rendered).toEqual({
      UTC: "2026-07-30 01:00:00",
      "America/New_York": "2026-07-29 21:00:00",
      "Asia/Seoul": "2026-07-30 10:00:00",
    });
  });
});

// 리뷰 지적(2026-08-03) — 그리드(DevExtreme dataType:"datetime")는 고쳤는데 관리 상세 화면
// 5곳(TableCell, dataType 미지정 → 기본값 "string")이 인스턴트를 그대로 출력해 같은 행이
// 그리드·상세에서 다른 시각으로 보였다. TableCell 의 "datetime" 분기를 공용 포맷터
// `formatDate()` 로 옮기고 5곳에 `dataType="datetime"` 을 넘겨 고쳤다 — 이 절은 "같은 wire
// 값이 그리드 경로·상세 경로에서 같은 문자열을 내는가"를 세 타임존에서 대조한다.
describe("#303 — 그리드 ↔ 상세 화면 표시 일치 (TableCell 이 공용 포맷터를 쓰는가)", () => {
  it.each(VIEWER_TZS)("%s — 둘 다 고친 wire 값에서 그리드와 상세가 같은 문자열을 낸다", async (tz) => {
    const wire = readFixed(writeFixed(REAL_INSTANT));

    const gridDisplay = await renderAsViewerIn(tz, wire); // 실제 DataGrid dataType:"datetime" 경로
    const detailDisplay = formatDate(wire, "datetime", { timeZone: tz })!; // TableCell → formatDate() 경로

    expect(detailDisplay).toBe(gridDisplay);
  });

  it("부정 통제 — TableCell 이 dataType 을 못 받으면(기본값 string) 그리드와 어긋난다", async () => {
    // dataType 이 없으면 TableCell 은 값을 그대로 String() 한다 — 즉 상세 화면에 wire(ISO 원문)가
    // 그대로 노출된다. 이게 정확히 리뷰가 잡은 회귀다: 그리드는 사용자 타임존으로 보이는데
    // 상세는 UTC 원문 그대로라 같은 행이 화면마다 다른 시각으로 보인다.
    const wire = readFixed(writeFixed(REAL_INSTANT));
    const gridDisplay = await renderAsViewerIn("Asia/Seoul", wire);
    const detailDisplayWithoutDataType = wire; // TableCell 기본값(string) 경로 — String(value) 그대로

    expect(detailDisplayWithoutDataType).not.toBe(gridDisplay);
    expect(gridDisplay).toBe("2026-07-30 10:00:00");
    expect(detailDisplayWithoutDataType).toBe("2026-07-30T01:00:00.000Z");
  });
});
