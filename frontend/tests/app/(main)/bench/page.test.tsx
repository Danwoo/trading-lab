// @vitest-environment jsdom
//
// 실험대 보드 — 화면 결정 §21.4(빈 상태) · §21.5(실패는 영향 범위 먼저) · §21.6(폭 구간) ·
// §20.2(패널에서 고르면 보드가 표시).
//
// 데이터는 **서비스 층에서** 갈아 끼운다 — 훅을 통째로 모킹하면 「0건」과 「못 읽음」을 가르는
// 판정부(훅 안에 있다)가 테스트를 안 지나간다.
//
// 폭 구간은 이제 CSS 가 가른다(Tailwind `xl`). jsdom 은 CSS 를 적용하지 않으므로 두 배치가
// 둘 다 DOM 에 있다 — 그래서 「무엇이 보이나」가 아니라 **「어느 배치에 무엇이 들어 있나」**와
// 그 배치를 여닫는 클래스를 단언한다.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import BenchPage from "@/app/(main)/bench/page";
import { useBenchSelectionStore } from "@/stores/shell/benchSelectionStore";
import { useProductPanelStore } from "@/stores/shell/productPanelStore";
import { RAIL_ITEMS } from "@/constants/shell";

/** 보드가 내놓는 두 갈래의 목적지 (`BenchPaths` 의 PATHS 와 같은 순서). */
const BENCH_PATH_RAIL_IDS = ["bot", "agent"] as const;
import { selectBot, selectBotList } from "@/services/bot/botService";
import { runBacktestGrid } from "@/services/backtest/backtestService";
import { selectIngestRunList } from "@/services/terminal/ingestService";
import type { IngestRunOut } from "@/schemas/terminal/ingest";
import { FRESHNESS_TONE } from "@/components/features/Bench/QuoteFreshnessBanner";
import type { QuoteFreshnessKind } from "@/hooks/bench/useQuoteFreshness";

vi.mock("@/services/bot/botService", () => ({ selectBotList: vi.fn(), selectBot: vi.fn() }));
vi.mock("@/services/terminal/ingestService", () => ({ selectIngestRunList: vi.fn() }));
vi.mock("@/services/backtest/backtestService", () => ({
  runBacktestGrid: vi.fn(),
  selectBacktestReport: vi.fn(),
}));

const TODAY = "2026-08-15";

/** 성공한 일봉 적재 하나 — `period_to` 가 「어디까지 받았나」다 */
function succeededRun(periodTo: string): IngestRunOut {
  return {
    run_id: 1,
    source: "yfinance",
    job_kind: "daily_bar",
    scope: "NASDAQ:AAPL",
    period_from: "2026-01-01",
    period_to: periodTo,
    status: "succeeded",
    cursor: null,
    written_rows: 120,
    skipped_rows: 0,
    failed_reason: null,
    started_dt: `${periodTo}T18:00:00`,
    finished_dt: `${periodTo}T18:02:00`,
    reg_dt: `${periodTo}T18:00:00`,
  };
}

/** 적재 이력·봇 목록을 이 상태로 세운다 */
function givenBackend(options: { runs?: IngestRunOut[] | null; bots?: unknown[] | null }) {
  vi.mocked(selectIngestRunList).mockResolvedValue(
    options.runs === null ? null : { items: options.runs ?? [], total_count: (options.runs ?? []).length },
  );
  vi.mocked(selectBotList).mockResolvedValue(
    options.bots === null ? null : ({ items: options.bots ?? [], total_count: (options.bots ?? []).length } as any),
  );
}

/** 화면에 두 벌로 있는 자리 중 하나를 집는다 (넓은 배치가 먼저 온다) */
const firstRegion = (name: string) => screen.getAllByRole("region", { name })[0];

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date(`${TODAY}T12:00:00`));
  useBenchSelectionStore.setState({ selection: null });
  useProductPanelStore.setState({ openPanelId: null, expanded: false, focusRailItemId: null });
  givenBackend({});
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.clearAllMocks();
  // `matchMedia` 를 undefined 로 세우는 테스트가 있다 — 해제하지 않으면 뒤 테스트가
  // 그 상태로 돈다 (vitest 설정에 `unstubGlobals` 가 없어 자동 해제도 없다).
  vi.unstubAllGlobals();
});

describe("첫 진입 — 봇 0개 · 거래 0건 · 적재 미실행 (§21.4)", () => {
  it("빈 화면이 아니라 자리마다 무엇이 올 것인지가 적혀 있다", async () => {
    render(<BenchPage />);

    expect(firstRegion("격자").textContent).toContain("파라미터 조합이 칸으로 깔립니다");
    expect(firstRegion("곡선").textContent).toContain("자산 추이·낙폭과 판정 지표");
    expect(firstRegion("내 봇").textContent).toContain("만든 봇과 지금 상태");
    expect(firstRegion("오늘 할 일").textContent).toContain("어젯밤에 리서치가 올린 것");
  });

  it("비어 있는 이유가 자리마다 적힌다 — 봇이 없어서인지 엔진이 없어서인지 갈린다", async () => {
    render(<BenchPage />);

    await waitFor(() => expect(firstRegion("내 봇").textContent).toContain("아직 만든 봇이 없습니다"));
    expect(firstRegion("격자").textContent).toContain("돌릴 봇이 없습니다");
    // 봇이 0개면 「거래가 0건」이 아니다 — 돌린 적이 없다. 안 일어난 실행의 결과를 말하지 않는다.
    expect(firstRegion("곡선").textContent).toContain("돌릴 봇이 없습니다");
    expect(firstRegion("오늘 할 일").textContent).toContain("리서치 저녁 배치가 아직 없어");
  });

  // 엔진(#200~#202)이 붙었다 — 「엔진이 없다」는 사유는 더 이상 참이 아니고, 봇이 있으면
  // 이 자리가 실행으로 가는 길(격자 실행 폼)을 연다.
  it("봇이 생기면 격자·곡선의 사유가 「아직 돌리지 않았다」로 바뀌고 실행 폼이 열린다", async () => {
    givenBackend({ bots: [{ bot_id: 1, bot_nm: "봇 알파", bot_role: "READONLY", use_at: "Y" }] });
    render(<BenchPage />);

    await waitFor(() => expect(firstRegion("내 봇").textContent).toContain("봇 알파"));
    expect(firstRegion("격자").textContent).toContain("아직 돌리지 않았습니다");
    expect(firstRegion("격자").textContent).not.toContain("돌릴 봇이 없습니다");
    expect(firstRegion("곡선").textContent).toContain("아직 돌리지 않았습니다");
    expect(within(firstRegion("격자")).getByRole("form", { name: "격자 실행" })).toBeTruthy();
  });

  it("봇의 역할을 사람 말로 적는다 — READONLY 를 그대로 내보내지 않는다", async () => {
    givenBackend({ bots: [{ bot_id: 1, bot_nm: "봇 알파", bot_role: "READONLY", use_at: "Y" }] });
    render(<BenchPage />);

    const zone = firstRegion("내 봇");
    await waitFor(() => expect(zone.textContent).toContain("봇 알파"));
    expect(zone.textContent).toContain("보기만 한다");
    expect(zone.textContent).not.toContain("READONLY");
  });

  it("제품이 없다고 말하는 것은 실제로 없는 것뿐이다 — 백테스트는 왔다", async () => {
    render(<BenchPage />);

    const text = document.body.textContent ?? "";
    expect(text).not.toContain("검증(백테스트)과 굴리기(주문)는 아직 없습니다");
    expect(text).toContain("과거 데이터로 검증하는 자리입니다");
  });

  it("길을 둘 준다 — 「봇 만들기」와 「에이전트에게 맡기기」 (§21.4)", () => {
    render(<BenchPage />);

    expect(screen.getByRole("button", { name: /봇 만들기/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /에이전트에게 맡기기/ })).toBeTruthy();
  });

  it("그 길은 죽은 링크가 아니다 — 누르면 해당 패널이 열린다", async () => {
    const user = userEvent.setup();
    render(<BenchPage />);

    await user.click(screen.getByRole("button", { name: /봇 만들기/ }));
    expect(useProductPanelStore.getState().openPanelId).toBe("bot");

    await user.click(screen.getByRole("button", { name: /에이전트에게 맡기기/ }));
    expect(useProductPanelStore.getState().openPanelId).toBe("agent");
  });

  // 이 성질은 「봇이 준비 중이다」가 아니라 **「준비 중인 것만 준비 중이라 말한다」**이다.
  // 봇 패널이 배선되면서 봇은 준비 중이 아니게 됐다 — 그래서 대상을 레일 표식으로 잡는다.
  it("목적지가 아직 준비 중이면 그 사실이 버튼에 보인다", () => {
    render(<BenchPage />);

    const pendingPaths = BENCH_PATH_RAIL_IDS.filter(
      (railId) => RAIL_ITEMS.find((item) => item.id === railId)?.pending !== undefined,
    );
    expect(pendingPaths.length).toBeGreaterThan(0);

    for (const railId of pendingPaths) {
      const label = railId === "bot" ? /봇 만들기/ : /에이전트에게 맡기기/;
      expect(screen.getByRole("button", { name: label }).textContent).toContain("준비 중");
    }
  });

  it("배선된 목적지는 「준비 중」이라 말하지 않는다", () => {
    render(<BenchPage />);

    const readyPaths = BENCH_PATH_RAIL_IDS.filter(
      (railId) => RAIL_ITEMS.find((item) => item.id === railId)?.pending === undefined,
    );
    expect(readyPaths).toContain("bot");

    for (const railId of readyPaths) {
      const label = railId === "bot" ? /봇 만들기/ : /에이전트에게 맡기기/;
      expect(screen.getByRole("button", { name: label }).textContent).not.toContain("준비 중");
    }
  });
});

describe("낡은 적재본 — 조용히 굴리지 않는다 (§21.5)", () => {
  it("하루 낡으면 상단 배지에 「하루 낡음」이 뜬다", async () => {
    givenBackend({ runs: [succeededRun("2026-08-14")] });
    render(<BenchPage />);

    const banner = screen.getByRole("region", { name: "시세 신선도" });
    await waitFor(() => expect(banner.textContent).toContain("하루 낡음"));
    expect(banner.textContent).toContain("08-14");
  });

  it("영향 범위가 오류 문구보다 **먼저** 온다", async () => {
    givenBackend({ runs: [succeededRun("2026-08-06")] });
    render(<BenchPage />);

    const banner = screen.getByRole("region", { name: "시세 신선도" });
    await waitFor(() => expect(banner.textContent).toContain("9일 낡음"));

    const text = banner.textContent ?? "";
    expect(text).toContain("멈추는 것");
    expect(text).toContain("오늘 신호 판정");
    expect(text).toContain("계속 도는 것");
    expect(text.indexOf("멈추는 것")).toBeLessThan(text.indexOf("계속 도는 것"));
  });

  it("오늘 적재본이면 낡음 문구가 없다 — 경고를 남발하지 않는다", async () => {
    givenBackend({ runs: [succeededRun(TODAY)] });
    render(<BenchPage />);

    const banner = screen.getByRole("region", { name: "시세 신선도" });
    await waitFor(() => expect(banner.textContent).toContain("오늘 적재본입니다"));
    expect(banner.textContent).not.toContain("낡음");
  });

  it("종목 마스터만 돌린 것은 시세 신선도가 아니다 — 여전히 「한 번도 안 돌렸다」", async () => {
    givenBackend({ runs: [{ ...succeededRun(TODAY), job_kind: "instrument_master" }] });
    render(<BenchPage />);

    const banner = screen.getByRole("region", { name: "시세 신선도" });
    await waitFor(() => expect(banner.textContent).toContain("한 번도 돌리지 않았습니다"));
  });

  it("적재 이력을 못 읽으면 최신인 척하지 않는다", async () => {
    givenBackend({ runs: null });
    render(<BenchPage />);

    const banner = screen.getByRole("region", { name: "시세 신선도" });
    await waitFor(() => expect(banner.textContent).toContain("확인하지 못했습니다"));
    expect(banner.textContent).toContain("멈추는 것");
  });

  it("적재를 아직 안 돌렸으면 갈 곳을 준다 — 안내만 하고 끝내지 않는다", async () => {
    render(<BenchPage />);

    const banner = screen.getByRole("region", { name: "시세 신선도" });
    await waitFor(() => expect(banner.textContent).toContain("한 번도 돌리지 않았습니다"));
    expect(
      within(banner)
        .getByRole("link", { name: /적재하기/ })
        .getAttribute("href"),
    ).toBe("/terminal");
  });
});

describe("봇 목록 실패 — 「0개」로 뭉개지 않는다", () => {
  it("못 읽었을 때 「아직 만든 봇이 없습니다」라고 말하지 않는다", async () => {
    givenBackend({ bots: null });
    render(<BenchPage />);

    const zone = firstRegion("내 봇");
    await waitFor(() => expect(zone.textContent).toContain("읽지 못했습니다"));
    expect(zone.textContent).not.toContain("아직 만든 봇이 없습니다");
    expect(zone.textContent).toContain("멈추는 것");
  });

  it("못 읽었을 때 격자·곡선·시작하는 길도 「없다」고 말하지 않는다", async () => {
    givenBackend({ bots: null });
    render(<BenchPage />);

    await waitFor(() => expect(firstRegion("내 봇").textContent).toContain("읽지 못했습니다"));
    for (const zone of ["격자", "곡선"]) {
      expect(firstRegion(zone).textContent).toContain("봇이 있는지 아직 모릅니다");
      expect(firstRegion(zone).textContent).not.toContain("돌릴 봇이 없습니다");
    }
    // 「시작하는 길」은 보드 밖이라 자리 이름이 없다 — 문서 전체에서 본다.
    expect(document.body.textContent).not.toContain("아직 봇이 없습니다.");
    expect(document.body.textContent).toContain("몇 개인지 모릅니다");
  });

  it("아직 불러오는 중일 때도 「없다」로 앞질러 말하지 않는다", async () => {
    // 응답을 붙잡아 둔다 — 느린 연결에서 첫 페인트가 무엇을 말하는가.
    let release: (value: unknown) => void = () => {};
    vi.mocked(selectBotList).mockReturnValue(new Promise((resolve) => (release = resolve)) as never);
    render(<BenchPage />);

    expect(document.body.textContent).not.toContain("아직 봇이 없습니다.");
    expect(document.body.textContent).toContain("봇 목록을 확인하고 있습니다");

    release({ items: [{ bot_id: 1, bot_nm: "봇 알파", bot_role: "READONLY", use_at: "Y" }], total_count: 1 });
    await waitFor(() => expect(document.body.textContent).toContain("봇 1개가 있습니다"));
  });

  it("원인 문구가 영향 범위보다 앞에 서지 않는다 (§21.5)", async () => {
    givenBackend({ bots: null });
    render(<BenchPage />);

    const zone = firstRegion("내 봇");
    await waitFor(() => expect(zone.textContent).toContain("멈추는 것"));

    const text = zone.textContent ?? "";
    // 훅이 내는 일반 실패 문구(`useOnDemand` 의 `unavailable` 사유). 자리의 사유 줄로 한 번 더
    // 나오면 영향 범위 위에 서게 된다.
    expect(text).not.toContain("요청을 처리하지 못했습니다");
    // 원인(`detail`)은 맨 뒤 — 영향 범위 다음이다.
    expect(text.indexOf("멈추는 것")).toBeLessThan(text.indexOf("봇 목록을 불러오지 못했습니다"));
  });
});

// #291 — 실행이 500 으로 실패했는데 자리 머리가 「아직 돌리지 않았습니다 — 골라 실행하면…」
// 이었다. 이미 한 일을 다시 하라고 안내한 것이다. 판정 자체는 `lib/bench/boardProvenance`
// 단위 테스트가 전수로 잡고, 여기서는 **그 판정이 실제 실행 경로를 타고 자리 머리까지 가는지**를 본다.
describe("격자 실행 실패 — 자리 머리가 「아직 안 돌렸다」로 되돌아가지 않는다", () => {
  /** 훑을 축이 하나 있는 봇 하나 — 폼이 실행 가능한 최소 상태 */
  function givenRunnableBot() {
    givenBackend({ bots: [{ bot_id: 1, bot_nm: "봇 알파", bot_role: "READONLY", use_at: "Y" }] });
    vi.mocked(selectBot).mockResolvedValue({
      bot_id: 1,
      bot_nm: "봇 알파",
      bot_role: "READONLY",
      use_at: "Y",
      strategies: [
        {
          bot_strategy_id: 1,
          strategy_key: "pullback",
          params: {},
          param_sources: {},
          weight: null,
          sort_order: 0,
          missing_reason: null,
          form: {
            key: "pullback",
            name: "눌림목",
            fields: [{ name: "window", label: "기간", control: "number", default: 20, min: 5, max: 60 }],
          },
        },
      ],
    } as never);
    // 폼이 `/bench?bot=<id>` 를 읽어 봇을 집는다 — 드롭다운을 열지 않고 실행까지 간다.
    window.history.replaceState({}, "", "/bench?bot=1");
  }

  afterEach(() => window.history.replaceState({}, "", "/bench"));

  it("실패하면 머리가 사유를 말한다 — 「골라 실행하세요」가 아니다", async () => {
    givenRunnableBot();
    vi.mocked(runBacktestGrid).mockRejectedValue({ response: { status: 500, data: {} } });
    render(<BenchPage />);

    await waitFor(() => expect(firstRegion("격자").textContent).toContain("아직 돌리지 않았습니다"));
    const symbol = screen.getAllByPlaceholderText("005930 또는 AAPL")[0];
    fireEvent.change(symbol, { target: { value: "005930" } });
    fireEvent.submit(screen.getAllByRole("form", { name: "격자 실행" })[0]);

    await waitFor(() => expect(firstRegion("격자").textContent).toContain("격자 실행이 실패했습니다"));
    expect(firstRegion("격자").textContent).not.toContain("아직 돌리지 않았습니다");
    // 곡선도 같은 실패를 안다 — 「격자를 실행하면 곡선이 그려집니다」는 이미 한 일이다.
    expect(firstRegion("곡선").textContent).toContain("격자 실행이 실패해 고를 칸이 없습니다");
  });

  it("같은 사유를 한 자리에서 두 번 말하지 않는다", async () => {
    givenRunnableBot();
    vi.mocked(runBacktestGrid).mockRejectedValue({ response: { status: 500, data: {} } });
    render(<BenchPage />);

    await waitFor(() => expect(firstRegion("격자").textContent).toContain("아직 돌리지 않았습니다"));
    fireEvent.change(screen.getAllByPlaceholderText("005930 또는 AAPL")[0], { target: { value: "005930" } });
    fireEvent.submit(screen.getAllByRole("form", { name: "격자 실행" })[0]);

    await waitFor(() => expect(firstRegion("격자").textContent).toContain("서버에서 오류가 발생했습니다"));
    const text = firstRegion("격자").textContent ?? "";
    expect(text.split("서버에서 오류가 발생했습니다")).toHaveLength(2);
  });
});

describe("폭 구간은 CSS 가 가른다 (§21.6 · 반응형 규칙)", () => {
  it("1280 이상 배치와 그 미만 배치가 둘 다 DOM 에 있고 브레이크포인트로만 갈린다", () => {
    const { container } = render(<BenchPage />);

    const wide = container.querySelector(".xl\\:grid-cols-2");
    expect(wide).toBeTruthy();
    expect(wide!.className).toContain("hidden");
    expect(wide!.className).toContain("xl:grid");

    const narrow = screen.getByRole("tablist", { name: "보드 보기" }).parentElement!;
    expect(narrow.className).toContain("xl:hidden");
  });

  it("`matchMedia` 가 없어도 보드가 그려진다 — 폭 판단이 JS 로 돌아오면 여기서 깨진다", () => {
    vi.stubGlobal("matchMedia", undefined);

    const { container } = render(<BenchPage />);

    expect(container.querySelector(".xl\\:grid-cols-2")).toBeTruthy();
    expect(screen.getByRole("tablist", { name: "보드 보기" })).toBeTruthy();
  });

  it("보드가 뷰포트 비례 바닥을 갖는다 — 아래 줄 내용이 늘어도 보드가 밀리지 않는다", () => {
    const { container } = render(<BenchPage />);

    // 이 자리는 클래스만 본다. **비가 실제로 성립하는지는 jsdom 이 CSS 를 적용하지 않아
    // 여기서 못 잰다** — 브라우저 실측이 정본이고, 여기서는 바닥이 사라지는 것만 막는다.
    const wide = container.querySelector(".xl\\:grid-cols-2")!;
    expect(wide.className).toContain("xl:min-h-[50svh]");

    const narrow = screen.getByRole("tablist", { name: "보드 보기" }).parentElement!;
    expect(narrow.className).toContain("min-h-[50svh]");

    // 바닥은 뷰포트 비례여야 한다 — 고정 px/rem 으로 박으면 화면 크기를 안 따라간다.
    for (const el of [wide, narrow]) {
      expect(el.className).toMatch(/min-h-\[\d+s?vh\]/);
      expect(el.className).not.toMatch(/(^|\s)h-\d/);
    }
  });

  it("좁은 배치는 격자·곡선을 하나씩만 담는다", () => {
    render(<BenchPage />);

    const narrow = screen.getByRole("tablist", { name: "보드 보기" }).parentElement!;
    expect(within(narrow).getByRole("region", { name: "격자" })).toBeTruthy();
    expect(within(narrow).queryByRole("region", { name: "곡선" })).toBeNull();
  });

  it("탭은 화살표 키로 옮겨진다", async () => {
    const user = userEvent.setup();
    render(<BenchPage />);

    screen.getByRole("tab", { name: "격자" }).focus();
    await user.keyboard("{ArrowRight}");

    const narrow = screen.getByRole("tablist", { name: "보드 보기" }).parentElement!;
    expect(screen.getByRole("tab", { name: "곡선" }).getAttribute("aria-selected")).toBe("true");
    expect(within(narrow).getByRole("region", { name: "곡선" })).toBeTruthy();
    expect(within(narrow).queryByRole("region", { name: "격자" })).toBeNull();
  });

  it("내 봇·오늘 할 일은 한 벌만 있고 접지 않는다", () => {
    render(<BenchPage />);

    expect(screen.getAllByRole("region", { name: "내 봇" })).toHaveLength(1);
    expect(screen.getAllByRole("region", { name: "오늘 할 일" })).toHaveLength(1);
  });

  it("고정 px 폭을 새로 만들지 않는다 — 보드 안에 `w-[…px]` 가 없다", () => {
    const { container } = render(<BenchPage />);

    expect(container.innerHTML).not.toMatch(/\bw-\[\d+px\]/);
    expect(container.innerHTML).not.toMatch(/\bmin-w-\[\d+px\]/);
  });
});

describe("패널에서 고르면 보드가 그 지점을 표시한다 (§20.2 셋째 줄)", () => {
  it("선택이 없으면 어느 자리도 표시되지 않는다", () => {
    render(<BenchPage />);

    expect(screen.queryByText(/여기 표시합니다/)).toBeNull();
  });

  it("격자 지점은 「격자」 자리가 받는다", () => {
    useBenchSelectionStore.setState({
      selection: { kind: "grid-point", id: "g-42", label: "칸 42", origin: "panel" },
    });
    render(<BenchPage />);

    const grid = firstRegion("격자");
    expect(grid.textContent).toContain("칸 42");
    expect(grid.textContent).toContain("패널에서 고른 지점을 여기 표시합니다");
  });

  it("종류가 다르면 다른 자리가 받는다 — 봇 선택은 「내 봇」이 받고 「격자」는 조용하다", () => {
    useBenchSelectionStore.setState({
      selection: { kind: "bot", id: "bot-1", label: "봇 알파", origin: "panel" },
    });
    render(<BenchPage />);

    expect(firstRegion("내 봇").textContent).toContain("봇 알파");
    expect(firstRegion("격자").textContent).not.toContain("봇 알파");
  });
});

// ---------------------------------------------------------------------------
// #285 — 오류가 아닌 것을 오류색으로 그리지 않는다.
//
// 색은 클래스가 아니라 **뜻**을 나른다. 「아직 안 온 것」(준비 중·첫 적재 전)과 「그대로 두면
// 안 되는 것」(낡음)과 「지금 잘못된 것」(적재 실패·못 읽음)이 같은 빨강으로 나오면 둘이 동시에
// 망가진다 — 처음 온 사람은 제품을 고장으로 읽고, 진짜 오류가 났을 때 그 빨강이 안 두드러진다.
//
// jsdom 은 CSS 를 적용하지 않으므로 여기서 재는 것은 **어느 토큰 클래스가 붙었나**다. 그
// 클래스가 실제로 무슨 색으로 그려지는지는 브라우저 실측과 `verify_token_contrast.py` 가 맡고,
// 원시 색(`text-red-500` 등)이 새로 들어오는 것은 `verify_color_token_usage.py` 가 막는다.
// ---------------------------------------------------------------------------

/** 실패로 끝난 캔들 적재 하나 — 성공분이 하나도 없으면 「한 번도 성공 못 했다」다 */
function failedRun(day: string): IngestRunOut {
  return {
    ...succeededRun(day),
    run_id: 9,
    status: "failed",
    written_rows: 0,
    failed_reason: "소스가 응답하지 않았습니다",
  };
}

/** 신선도 갈래를 각각 만드는 법 + 그 갈래가 받아야 할 색 토큰(`null` 이면 상태색이 없어야 한다). */
const FRESHNESS_COLOR_CASES: {
  kind: QuoteFreshnessKind;
  arrange: () => void;
  expected: string | null;
  settle: string;
}[] = [
  {
    kind: "fresh",
    arrange: () => givenBackend({ runs: [succeededRun(TODAY)] }),
    expected: null,
    settle: "오늘 적재본입니다",
  },
  {
    kind: "stale",
    arrange: () => givenBackend({ runs: [succeededRun("2026-08-14")] }),
    expected: "text-caution",
    settle: "하루 낡음",
  },
  {
    kind: "never-run",
    arrange: () => givenBackend({ runs: [] }),
    expected: null,
    settle: "한 번도 돌리지 않았습니다",
  },
  {
    kind: "never-succeeded",
    arrange: () => givenBackend({ runs: [failedRun("2026-08-14")] }),
    expected: "text-danger",
    settle: "한 번도 성공하지 못했습니다",
  },
  {
    kind: "unreadable",
    arrange: () => givenBackend({ runs: null }),
    expected: "text-danger",
    settle: "확인하지 못했습니다",
  },
];

describe("#285 상태 → 색 토큰", () => {
  it("대응표가 신선도 갈래 전수를 덮는다 — 갈래가 늘면 여기서 멈춘다", () => {
    // 표는 `Record<QuoteFreshnessKind, …>` 라 갈래를 늘리면 타입이 먼저 막고, 채워 넣더라도
    // 이 건수가 어긋나 빨개진다. 0건이면 실패다.
    const kinds = Object.keys(FRESHNESS_TONE);
    expect(kinds.length).toBe(6);

    // 사다리는 「얼마나 비었나」가 아니라 **「무엇이 잘못됐나」**로 오른다.
    expect(FRESHNESS_TONE).toEqual({
      checking: "quiet",
      fresh: "quiet",
      "never-run": "quiet",
      stale: "caution",
      "never-succeeded": "alert",
      unreadable: "alert",
    });
  });

  it("색을 실제로 재 보는 갈래가 0건이 아니다", () => {
    expect(FRESHNESS_COLOR_CASES.length).toBe(5);
  });

  it.each(FRESHNESS_COLOR_CASES)("$kind 배너는 $expected 로 그려진다", async ({ arrange, expected, settle }) => {
    arrange();
    render(<BenchPage />);

    const banner = screen.getByRole("region", { name: "시세 신선도" });
    await waitFor(() => expect(banner.textContent).toContain(settle));

    for (const token of ["text-danger", "text-caution"]) {
      const hits = banner.querySelectorAll(`[class*="${token}"]`).length;
      if (token === expected) expect(hits).toBeGreaterThan(0);
      else expect(hits).toBe(0);
    }
  });

  it("적재를 한 번도 안 돌린 첫 화면에는 오류색이 하나도 없다 (#285 완료 조건)", async () => {
    givenBackend({ runs: [], bots: [] });
    const { container } = render(<BenchPage />);

    await waitFor(() =>
      expect(screen.getByRole("region", { name: "시세 신선도" }).textContent).toContain("한 번도 돌리지 않았습니다"),
    );
    await waitFor(() => expect(firstRegion("내 봇").textContent).toContain("아직 만든 봇이 없습니다"));

    expect(container.querySelectorAll('[class*="text-danger"]')).toHaveLength(0);
    expect(container.querySelectorAll('[class*="border-danger"]')).toHaveLength(0);
  });

  it("「준비 중」은 중립 잉크다 — 계획대로인 상태를 고장으로 그리지 않는다", () => {
    render(<BenchPage />);

    const pendingPaths = BENCH_PATH_RAIL_IDS.filter(
      (railId) => RAIL_ITEMS.find((item) => item.id === railId)?.pending !== undefined,
    );
    expect(pendingPaths.length).toBeGreaterThan(0);

    for (const railId of pendingPaths) {
      const label = railId === "bot" ? /봇 만들기/ : /에이전트에게 맡기기/;
      const line = within(screen.getByRole("button", { name: label })).getByText(/^준비 중 —/);
      expect(line.className).toContain("text-ink-muted");
      expect(line.className).not.toContain("text-danger");
    }
  });

  it("배지의 「하루 낡음」도 오류색이 아니다", async () => {
    givenBackend({ runs: [succeededRun("2026-08-14")] });
    render(<BenchPage />);

    const banner = screen.getByRole("region", { name: "시세 신선도" });
    await waitFor(() => expect(banner.textContent).toContain("하루 낡음"));

    const mark = within(banner).getByText(/하루 낡음$/);
    expect(mark.className).toContain("text-caution");
    expect(mark.className).not.toContain("text-danger");
  });
});
