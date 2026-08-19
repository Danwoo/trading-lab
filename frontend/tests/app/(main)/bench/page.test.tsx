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
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import BenchPage from "@/app/(main)/bench/page";
import { useBenchSelectionStore } from "@/stores/shell/benchSelectionStore";
import { useProductPanelStore } from "@/stores/shell/productPanelStore";
import { RAIL_ITEMS } from "@/constants/shell";

/** 보드가 내놓는 두 갈래의 목적지 (`BenchPaths` 의 PATHS 와 같은 순서). */
const BENCH_PATH_RAIL_IDS = ["bot", "agent"] as const;
import { selectBotList } from "@/services/bot/botService";
import { selectIngestRunList } from "@/services/terminal/ingestService";
import type { IngestRunOut } from "@/schemas/terminal/ingest";

vi.mock("@/services/bot/botService", () => ({ selectBotList: vi.fn(), selectBot: vi.fn() }));
vi.mock("@/services/terminal/ingestService", () => ({ selectIngestRunList: vi.fn() }));

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
