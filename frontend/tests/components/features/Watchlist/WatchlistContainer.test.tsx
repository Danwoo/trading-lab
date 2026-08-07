// @vitest-environment jsdom
//
// 이슈 #242 O5 — 관심종목 화면이 그리드 커널(O1)로 이주한 뒤에도 컬럼 집합·서버 필터·정렬
// 요청 형태·공통코드 룩업 표시가 이주 전과 같은지 이 파일이 검증한다. `WatchlistDetailView`/
// `WatchlistDetailForm`(O8 범위, DevExtreme 그대로)은 이 테스트의 관심사가 아니므로 목으로
// 대체해 왼쪽 그리드만 격리한다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
// 실제 다운로드 경로가 쓰는 것과 같은 라이브러리로 결과 파일을 다시 읽어 셀 값을 대조한다
// (지휘자 실측 회귀: 화면 셀은 이름인데 엑셀엔 코드가 그대로 샜다 — #242 O5).
import { Workbook } from "devextreme-exceljs-fork";

import WatchlistContainer from "@/components/features/Watchlist/WatchlistContainer";
import { selectWatchlistList } from "@/services/watchlist/watchlistService";
import { useCodeStore } from "@/stores/shared/codeStore";
import type { WatchlistOut } from "@/schemas/watchlist/watchlist";

// `DetailPanel`(공용, O5 범위 밖)이 `Feedback` 배럴 → `MessagePopup` → `@/components/shared/ui`
// 배럴 → `FileListDisplay` 를 물고 있어, 이 컴포넌트 트리를 렌더하면 `env.ts`(t3-oss 검증)까지
// 평가된다 — `.env.test` 가 없는 vitest 환경이라 필수 서버 환경변수가 비어 그대로 두면
// 이 화면과 무관한 이유로 테스트가 죽는다. 실제 값이 필요 없는 목이므로 통째로 비운다.
vi.mock("@/env", () => ({ env: new Proxy({}, { get: () => "" }) }));

vi.mock("@/services/watchlist/watchlistService", () => ({
  selectWatchlistList: vi.fn(),
  selectWatchlist: vi.fn(),
  createWatchlist: vi.fn(),
  updateWatchlist: vi.fn(),
  deleteWatchlist: vi.fn(),
}));

vi.mock("@/stores/shared/codeStore", () => ({
  useCodeStore: vi.fn(),
}));

vi.mock("@/components/features/Watchlist/WatchlistDetailView", () => ({
  default: () => <div data-testid="detail-view" />,
}));

vi.mock("@/components/features/Watchlist/WatchlistDetailForm", () => ({
  default: () => <div data-testid="detail-form" />,
}));

// `saveAs`(브라우저 다운로드 API)만 가로챈다 — 워크북 생성(`useTableExport`/`tableExport.ts`)
// 은 실제 프로덕션 코드를 그대로 태운다.
let savedBlob: Blob | null = null;
vi.mock("file-saver", () => ({
  saveAs: vi.fn((blob: Blob) => {
    savedBlob = blob;
  }),
}));

// 실제 DB 값(운영 확인, operator@example.com/workspace 1) — market 은 code==code_nm 이지만
// currency/priority/use_at 는 다르다. 룩업 렌더가 진짜로 이름을 쓰는지 이 비대칭으로 검증한다.
const CODE_LISTS: Record<string, { code: string; code_nm: string }[]> = {
  "5000": [
    { code: "KOSPI", code_nm: "KOSPI" },
    { code: "NASDAQ", code_nm: "NASDAQ" },
  ],
  "5001": [{ code: "IT/반도체", code_nm: "IT/반도체" }],
  "5002": [
    { code: "KRW", code_nm: "원화(KRW)" },
    { code: "USD", code_nm: "미국 달러(USD)" },
  ],
  "5003": [{ code: "1", code_nm: "높음" }],
  "1000": [
    { code: "Y", code_nm: "사용" },
    { code: "N", code_nm: "미사용" },
  ],
};

const ROWS: WatchlistOut[] = [
  {
    rn: 1,
    ticker: "005930",
    issuer_nm: "삼성전자",
    market: "KOSPI",
    sector: "IT/반도체",
    currency: "KRW",
    target_price: 90000,
    alert_price: 70000,
    priority: "1",
    use_at: "Y",
    reg_dt: "2026-07-27 06:49:50",
    mod_dt: "2026-07-27 06:49:50",
  } as WatchlistOut,
  {
    rn: 2,
    ticker: "AAPL",
    issuer_nm: "Apple Inc.",
    market: "NASDAQ",
    sector: "IT/반도체",
    currency: "USD",
    target_price: 240,
    alert_price: 180,
    priority: "1",
    use_at: "N",
    reg_dt: "2026-07-27 06:49:50",
    mod_dt: "2026-07-27 06:49:50",
  } as WatchlistOut,
];

// jsdom 은 ResizeObserver 를 구현하지 않는다 — `SplitPane`(react-resizable-panels)과 가상
// 스크롤(`@tanstack/react-virtual`, DataTable 내부)이 둘 다 이를 필요로 한다. 실측: 없으면
// `new ResizeObserver(...)` 가 "TypeError: n is not a constructor" 로 렌더 자체를 막는다.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

function setup() {
  vi.stubGlobal("ResizeObserver", ResizeObserverStub);

  // jsdom 은 레이아웃 엔진이 없어 모든 요소의 높이가 0 이다 — `@tanstack/react-virtual`(DataTable
  // 내부 가상 스크롤)이 스크롤 컨테이너 높이를 0 으로 읽으면 뷰포트 안에 아무 행도 없다고
  // 판단해 바디를 통째로 비운다. 실측 높이를 흉내내 최소 몇 행이 뷰포트 안에 들어오게 한다.
  Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, value: 600 });
  Object.defineProperty(HTMLElement.prototype, "offsetHeight", { configurable: true, value: 600 });

  vi.mocked(useCodeStore).mockReturnValue({
    codes: {},
    getGroupCodes: vi.fn(),
    getCode: (groupCode: string) => CODE_LISTS[groupCode] ?? [],
  } as unknown as ReturnType<typeof useCodeStore>);

  vi.mocked(selectWatchlistList).mockResolvedValue({ items: ROWS, total_count: ROWS.length });

  render(<WatchlistContainer />);
}

afterEach(() => {
  cleanup();
  vi.mocked(selectWatchlistList).mockReset();
  vi.mocked(useCodeStore).mockReset();
});

describe("WatchlistContainer — 컬럼 계약(시안 「바뀌면 안 되는 것」)", () => {
  it("컬럼 12개를 정해진 순서·캡션으로 그린다(체크박스 열 없음)", async () => {
    setup();
    await waitFor(() => expect(screen.getByText("005930")).toBeTruthy());

    const headerRow = screen.getAllByRole("columnheader");
    const captions = headerRow.map((cell) => cell.textContent?.replace(/[▲▼]/g, "").trim());

    expect(captions).toEqual([
      "#",
      "티커",
      "종목명",
      "시장",
      "섹터",
      "통화",
      "목표가",
      "알림가",
      "우선순위",
      "사용여부",
      "생성일시",
      "수정일시",
    ]);
  });

  it("시장·통화·우선순위·사용여부를 코드가 아니라 이름으로 보여준다", async () => {
    setup();
    await waitFor(() => expect(screen.getByText("005930")).toBeTruthy());

    const row = screen.getByText("005930").closest("tr") as HTMLElement;
    const cells = within(row)
      .getAllByRole("cell")
      .map((cell) => cell.textContent);

    expect(cells).toContain("KOSPI"); // 시장 — 코드와 이름이 같은 값(운영 데이터)
    expect(cells).toContain("원화(KRW)"); // 통화 — 코드(KRW)가 아니라 이름
    expect(cells).toContain("높음"); // 우선순위 — 코드(1)가 아니라 이름
    expect(cells).toContain("사용"); // 사용여부 — 코드(Y)가 아니라 이름
    expect(cells).not.toContain("Y");
  });
});

describe("WatchlistContainer — 서버 필터·정렬 요청(부정 통제 포함)", () => {
  it("종목명 필터에 값을 넣으면 디바운스 뒤 O1 필터 문법으로 재조회한다", async () => {
    setup();
    await waitFor(() => expect(screen.getByText("005930")).toBeTruthy());

    const filterInput = screen.getByLabelText("종목명 필터");
    fireEvent.change(filterInput, { target: { value: "삼성" } });

    await waitFor(
      () => {
        const lastCall = vi.mocked(selectWatchlistList).mock.calls.at(-1)?.[0] as any;
        expect(lastCall?.filter).toEqual(["issuer_nm", "contains", "삼성"]);
      },
      { timeout: 1000 },
    );
  });

  it("티커 컬럼 헤더를 클릭하면 sort 로 재조회하고, 걸지 않은 필터는 파라미터에서 사라진다", async () => {
    const user = userEvent.setup();
    setup();
    await waitFor(() => expect(screen.getByText("005930")).toBeTruthy());

    const sortButton = screen.getByRole("button", { name: /^티커/ });
    await user.click(sortButton);

    await waitFor(() => {
      const lastCall = vi.mocked(selectWatchlistList).mock.calls.at(-1)?.[0] as any;
      expect(lastCall?.sort).toEqual([{ selector: "ticker", desc: false }]);
      // 필터를 건 적이 없으므로 filter 키는 undefined 여야 한다 — 걸었을 때만 줄어드는지는
      // 위 필터 테스트가 별도로 확인한다(부정 통제: 조건 없음 ≠ 조건 있음과 같은 요청).
      expect(lastCall?.filter).toBeUndefined();
    });
  });
});

describe("WatchlistContainer — 엑셀 다운로드는 화면과 같은 값을 낸다(코드가 아니라 이름)", () => {
  it("엑셀다운로드 버튼을 누르면 화면 셀과 같은 룩업 이름으로 워크북을 만든다", async () => {
    savedBlob = null;
    setup();
    await waitFor(() => expect(screen.getByText("005930")).toBeTruthy());

    const excelButton = document.querySelector('[title="엑셀다운로드"]') as HTMLElement;
    expect(excelButton).toBeTruthy();
    fireEvent.click(excelButton);

    await waitFor(() => expect(savedBlob).not.toBeNull());
    if (!savedBlob) throw new Error("saveAs 가 호출되지 않았다");

    const arrayBuffer = await (savedBlob as Blob).arrayBuffer();
    const workbook = new Workbook();
    // devextreme-exceljs-fork 의 타입 선언(`declare interface Buffer extends ArrayBuffer {}`)이
    // 전역 Buffer 를 ArrayBuffer 로도 만족하도록 재선언해, 이 레포의 @types/node 기준 실제
    // Buffer 타입과 구조적으로 어긋난다 — 런타임에는 같은 Buffer 인스턴스라 안전하다.
    await workbook.xlsx.load(Buffer.from(arrayBuffer) as any);
    const worksheet = workbook.getWorksheet("Data");

    const header = (worksheet!.getRow(1).values as unknown[]).filter((v) => v !== undefined && v !== null);
    expect(header).toEqual([
      "#",
      "티커",
      "종목명",
      "시장",
      "섹터",
      "통화",
      "목표가",
      "알림가",
      "우선순위",
      "사용여부",
      "생성일시",
      "수정일시",
    ]);
    expect(worksheet!.rowCount - 1).toBe(ROWS.length); // 헤더 제외 데이터 행 수

    // 005930 행(rn=1) — 화면 셀과 같은 이름이어야 한다. 코드(KRW/1/Y)로 되돌아가면 회귀.
    //
    // 날짜 두 칸은 **문자열이 아니라 진짜 날짜 셀**이다(#417) — 텍스트로 나가면 `numFmt` 이
    // 무력해져 엑셀 안에서 정렬·필터가 깨진다. 그 두 칸은 아래에서 따로 단정한다.
    const row1 = (worksheet!.getRow(2).values as unknown[]).filter((v) => v !== undefined && v !== null);
    expect(row1.slice(0, 10)).toEqual([
      1,
      "005930",
      "삼성전자",
      "KOSPI", // 시장 — 코드와 이름이 같은 값(운영 데이터)
      "IT/반도체",
      "원화(KRW)", // 통화 — 코드(KRW)가 아니라 이름
      90000,
      70000,
      "높음", // 우선순위 — 코드(1)가 아니라 이름
      "사용", // 사용여부 — 코드(Y)가 아니라 이름
    ]);

    // 생성일시·수정일시 — 셀 타입은 Date 이고, 파일에 찍히는 벽시계는 화면과 같아야 한다.
    // 엑셀은 타임존 없는 일련번호로 저장하므로 "UTC 필드 = 지역 벽시계"가 그 계약이다
    // (`tableExport.ts` 의 `toExcelWallClockDate`). 인스턴트를 그대로 넣으면 KST 사용자
    // 파일에 9시간 이른 시각이 찍힌다.
    const [regCell, modCell] = row1.slice(10) as [Date, Date];
    for (const cell of [regCell, modCell]) {
      expect(cell).toBeInstanceOf(Date);
      expect(cell.toISOString()).toBe("2026-07-27T06:49:50.000Z");
    }
  });
});
