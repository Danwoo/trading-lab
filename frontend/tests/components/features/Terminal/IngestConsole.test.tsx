// @vitest-environment jsdom
//
// 마일스톤 2 가 시세 화면에 요구하는 두 줄을 지킨다:
//   "적재를 실행하면 **어디까지 받았고 무엇이 실패했는지** 화면에서 보인다"
//   "키가 없어도 기동되고, **어떤 패널이 왜 비어 있는지** 안내된다"
//
// 그래서 여기서 단언하는 것은 「무엇이 렌더되나」가 아니라 **「사실이 아닌 것을 말하지 않는가」**다 —
// 아직 확인 중인 것을 「없다」고 하지 않고, 막힌 소스는 이유와 함께, 실패한 적재는 사유와 함께.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { IngestConsole } from "@/components/features/Terminal/IngestConsole";
import type { PanelData } from "@/types/terminal/provenance";

const SYMBOL = { market: "KOSPI", ticker: "005930", name: "삼성전자" };

vi.mock("@/hooks/terminal/useTerminalContext", () => ({ useTerminalSymbol: vi.fn() }));
vi.mock("@/hooks/terminal/useMarketCapabilities", () => ({ useMarketCapabilities: vi.fn() }));
vi.mock("@/hooks/terminal/useIngestRuns", () => ({ useIngestRuns: vi.fn() }));
vi.mock("@/hooks/terminal/useBarGaps", () => ({ useBarGaps: vi.fn() }));
vi.mock("@/services/terminal/ingestService", () => ({ insertIngestRun: vi.fn() }));

const { useTerminalSymbol } = await import("@/hooks/terminal/useTerminalContext");
const { useMarketCapabilities } = await import("@/hooks/terminal/useMarketCapabilities");
const { useIngestRuns } = await import("@/hooks/terminal/useIngestRuns");
const { useBarGaps } = await import("@/hooks/terminal/useBarGaps");
const { insertIngestRun } = await import("@/services/terminal/ingestService");

function panel<T>(over: Partial<PanelData<T>>): PanelData<T> {
  return {
    data: null,
    isLoading: false,
    error: null,
    provenance: { kind: "loaded", source: "적재 이력", asOf: null },
    ...over,
  } as PanelData<T>;
}

/** 기본은 「아무것도 없음」 — 각 테스트가 필요한 것만 채운다. */
function given({
  symbol = SYMBOL as typeof SYMBOL | null,
  capabilities = panel<unknown[]>({ data: [] }),
  runs = panel<unknown[]>({ data: [] }),
  gaps = panel<unknown>({ data: null }),
} = {}) {
  vi.mocked(useTerminalSymbol).mockReturnValue(symbol as never);
  vi.mocked(useMarketCapabilities).mockReturnValue(capabilities as never);
  vi.mocked(useIngestRuns).mockReturnValue(runs as never);
  vi.mocked(useBarGaps).mockReturnValue(gaps as never);
}

/** 이 종목(KRX)의 캔들을 지금 받을 수 있는 상태. */
function usableKrx() {
  return panel<unknown[]>({
    data: [{ source: "data_go_kr", market: "KOSPI", dataKind: "daily_bar", available: true, reason: null }],
  });
}

function section(name: string): HTMLElement {
  return screen.getByRole("region", { name });
}

describe("적재 콘솔 — 사실이 아닌 것을 말하지 않는다", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("소스를 아직 확인하는 중이면 「없다」고 하지 않는다", () => {
    given({ capabilities: panel<unknown[]>({ data: null, isLoading: true }) });
    render(<IngestConsole />);

    const text = section("소스").textContent ?? "";
    expect(text).toContain("확인하고 있습니다");
    expect(text).not.toContain("등록된 소스가 없습니다");
  });

  it("막힌 소스는 서버가 준 사유를 **그대로** 보여준다 — 프론트가 안내를 다시 만들지 않는다", () => {
    // 서버(`DataKeyService.unavailable_reason`)가 env 항목명과 발급 경로까지 완전한 문장으로 준다.
    // 프론트가 같은 안내를 따로 만들면 서버가 아는 항목명과 갈린다 — 그 중복을 여기서 막는다.
    // 키 이름을 여기 적지 않는다 — 「키 이름을 아는 자리는 services/data_key/ 하나」가
    // 이 레포의 경계다(2026-08-07 리드 결정, verify_data_key_env_boundary 가 지킨다).
    // 이 테스트가 지키는 것은 **서버 문장을 그대로 보여준다**는 것이라, 내용이 무엇이든 상관없다.
    const serverReason = "서버가 조립한 사유 문장 — 항목명과 발급 경로까지";
    given({
      capabilities: panel<unknown[]>({
        data: [
          { source: "sec", market: "NASDAQ", dataKind: "quote", available: true, reason: null },
          { source: "alpaca", market: "NASDAQ", dataKind: "daily_bar", available: false, reason: serverReason },
        ],
      }),
    });
    render(<IngestConsole />);

    const text = section("소스").textContent ?? "";
    expect(text).toContain(serverReason);
    // 「2건 중 1건 사용 가능」 — 몇 건이 되는지 세어 말한다.
    expect(text).toContain("1건");
    // 프론트가 만든 축약 안내가 덧붙지 않는다.
    expect(text).not.toContain("키:");
  });

  it("적재 소스를 캐패빌리티에서 고른다 — 이름을 손으로 적지 않는다", async () => {
    // 등록되지 않은 소스 이름을 보내면 큐잉은 성공하고 **워커에서 실패한다**.
    // 그래서 「지금 이 시장의 캔들을 받을 수 있는 소스」를 데이터에서 골라 보낸다.
    given({
      capabilities: panel<unknown[]>({
        data: [
          { source: "alpaca", market: "NASDAQ", dataKind: "daily_bar", available: true, reason: null },
          { source: "data_go_kr", market: "KOSPI", dataKind: "daily_bar", available: true, reason: null },
        ],
      }),
    });
    vi.mocked(insertIngestRun).mockResolvedValue({ data: { run_id: 9 } } as never);
    render(<IngestConsole />);

    await userEvent.setup().click(within(section("적재")).getByRole("button"));

    await waitFor(() => expect(vi.mocked(insertIngestRun)).toHaveBeenCalled());
    expect(vi.mocked(insertIngestRun).mock.calls[0][0]).toMatchObject({ source: "data_go_kr" });
  });

  it("소스를 아직 확인하는 중이면 버튼도 「없다」고 하지 않는다", () => {
    // 「소스」 섹션은 이미 셋을 가르는데 버튼만 뭉치면, 매 초기 로드마다 잠깐 거짓말을 한다.
    given({ capabilities: panel<unknown[]>({ data: null, isLoading: true }) });
    render(<IngestConsole />);

    const button = within(section("적재")).getByRole("button") as HTMLButtonElement;
    expect(button.textContent).toContain("확인하는 중");
    expect(button.textContent).not.toContain("소스가 없습니다");
    expect(button.disabled).toBe(true);
  });

  it("소스 목록 조회가 실패하면 원인을 소스 부재로 오인시키지 않는다", () => {
    // 서버 장애인데 「소스가 없다」고 하면 사용자는 키를 발급받으러 간다.
    given({ capabilities: panel<unknown[]>({ data: null, isLoading: false }) });
    render(<IngestConsole />);

    const button = within(section("적재")).getByRole("button") as HTMLButtonElement;
    expect(button.textContent).toContain("읽지 못해");
    expect(button.textContent).not.toContain("소스가 없습니다");
    expect(button.disabled).toBe(true);
  });

  it("그 시장을 받을 소스가 없으면 누를 수 없고, 왜인지 말한다", () => {
    given({
      capabilities: panel<unknown[]>({
        data: [
          { source: "data_go_kr", market: "KOSPI", dataKind: "daily_bar", available: false, reason: "키가 없습니다" },
        ],
      }),
    });
    render(<IngestConsole />);

    const button = within(section("적재")).getByRole("button") as HTMLButtonElement;
    expect(button.textContent).toContain("소스가 없습니다");
    expect(button.disabled).toBe(true);
  });

  it("적재 이력이 어디까지 받았고 무엇이 실패했는지 보인다", () => {
    given({
      runs: panel<unknown[]>({
        data: [
          {
            run_id: 2,
            source: "alpaca",
            job_kind: "daily_bar",
            scope: "US:AAPL",
            period_from: "2026-01-01",
            period_to: "2026-08-14",
            status: "succeeded",
            cursor: null,
            written_rows: 152,
            skipped_rows: 0,
            failed_reason: null,
            started_dt: null,
            finished_dt: null,
            reg_dt: null,
          },
          {
            run_id: 1,
            source: "data_go_kr",
            job_kind: "daily_bar",
            scope: "KOSPI:005930",
            period_from: null,
            period_to: null,
            status: "failed",
            cursor: null,
            written_rows: null,
            skipped_rows: null,
            failed_reason: "일일 호출 한도를 넘었습니다",
            started_dt: null,
            finished_dt: null,
            reg_dt: null,
          },
        ],
      }),
    });
    render(<IngestConsole />);

    const text = section("이력").textContent ?? "";
    expect(text).toContain("~2026-08-14 까지"); // 어디까지 받았나
    expect(text).toContain("152행");
    expect(text).toContain("일일 호출 한도를 넘었습니다"); // 무엇이 실패했나
  });

  it("결측은 구간과 함께 세어 말하고, 종목이 없으면 세지 않는다", () => {
    given({ symbol: null });
    const { unmount } = render(<IngestConsole />);
    expect(section("빠진 거래일").textContent).toContain("종목을 고르면");
    unmount();

    given({
      gaps: panel<unknown>({
        data: { missingDates: ["2026-08-03", "2026-08-04"], dateFrom: "2026-08-01", dateTo: "2026-08-15" },
      }),
    });
    render(<IngestConsole />);
    const text = section("빠진 거래일").textContent ?? "";
    expect(text).toContain("2일");
    expect(text).toContain("2026-08-01");
    expect(text).toContain("2026-08-03");
  });

  it("종목이 없으면 적재 버튼이 그 사실을 말한다", () => {
    given({ symbol: null });
    render(<IngestConsole />);

    expect(within(section("적재")).getByRole("button").textContent).toContain("종목을 고르면");
  });

  it("적재 요청이 거절되면 조용히 성공한 척하지 않는다", async () => {
    given({ capabilities: usableKrx() });
    vi.mocked(insertIngestRun).mockResolvedValue(null);
    render(<IngestConsole />);

    await userEvent.setup().click(within(section("적재")).getByRole("button"));

    await waitFor(() => {
      expect(screen.getByRole("status").textContent).toContain("받아들여지지 않았습니다");
    });
  });

  it("적재 요청이 받아들여지면 그 사실과 다음 자리를 말한다", async () => {
    given({ capabilities: usableKrx() });
    vi.mocked(insertIngestRun).mockResolvedValue({ data: { run_id: 9 } } as never);
    render(<IngestConsole />);

    await userEvent.setup().click(within(section("적재")).getByRole("button"));

    await waitFor(() => {
      expect(screen.getByRole("status").textContent).toContain("큐에 넣었습니다");
    });
    expect(vi.mocked(insertIngestRun).mock.calls[0][0]).toMatchObject({
      job_kind: "daily_bar",
      scope: "KOSPI:005930",
    });
  });

  it("종목 목록은 종목을 고르지 않아도 받을 수 있다 — 첫 진입의 순환을 끊는 자리", async () => {
    given({
      capabilities: panel<unknown[]>({
        data: [
          { source: "toss", market: "KOSPI", dataKind: "instrument_master", available: true, reason: null },
          { source: "toss", market: "KOSPI", dataKind: "daily_bar", available: true, reason: null },
        ],
      }),
      symbol: null,
    });
    vi.mocked(insertIngestRun).mockResolvedValue({ data: { run_id: 11 } } as never);
    render(<IngestConsole />);

    const group = screen.getByRole("group", { name: "종목 목록 받기" });
    expect((within(group).getByRole("button") as HTMLButtonElement).disabled).toBe(false);
    await userEvent.setup().click(within(group).getByRole("button"));

    await waitFor(() => {
      expect(screen.getByRole("status").textContent).toContain("큐에 넣었습니다");
    });
    expect(vi.mocked(insertIngestRun).mock.calls[0][0]).toMatchObject({
      job_kind: "instrument_master",
      scope: "KOSPI",
    });
  });

  it("종목 목록을 줄 소스가 없으면 버튼 대신 사유가 선다", () => {
    given({
      capabilities: panel<unknown[]>({
        data: [{ source: "toss", market: "KOSPI", dataKind: "daily_bar", available: true, reason: null }],
      }),
      symbol: null,
    });
    render(<IngestConsole />);
    const group = screen.getByRole("group", { name: "종목 목록 받기" });
    expect(within(group).queryByRole("button")).toBeNull();
    expect(group.textContent).toContain("종목 목록을 줄 소스가 없습니다");
  });

  it("되는 것을 먼저 보인다 — 부분적으로 막힌 소스가 「안 되는 소스」로 읽히지 않게", () => {
    given({
      capabilities: panel<unknown[]>({
        data: [
          // 토스는 국내를 열고 미국 마스터만 SEC 에 양보한다 — 화면이 그 사실을 거꾸로 전하면 안 된다
          { source: "toss", market: "KOSPI", dataKind: "instrument_master", available: true, reason: null },
          { source: "toss", market: "KOSPI", dataKind: "daily_bar", available: true, reason: null },
          { source: "toss", market: "KOSPI", dataKind: "minute_bar", available: true, reason: null },
          {
            source: "toss",
            market: "NASDAQ",
            dataKind: "instrument_master",
            available: false,
            reason: "미국 종목 마스터의 정본 소스는 SEC 입니다",
            code: null,
          },
        ],
      }),
      symbol: null,
    });
    render(<IngestConsole />);

    const open = screen.getByRole("list", { name: "지금 받을 수 있는 것" });
    expect(open.textContent).toContain("KOSPI");
    // **종류마다 소스를 붙인다** — 종류와 소스를 따로 합집합하면 곱집합으로 읽혀,
    // 「그 소스가 이 종류도 준다」는 사실이 아닌 말이 된다.
    expect(open.textContent).toContain("종목목록(toss)");
    expect(open.textContent).toContain("일봉(toss)");
    expect(open.textContent).toContain("분봉(toss)");
    // 막힌 목록에만 있고 되는 목록엔 없는 상태가 이 이슈의 증상이었다
    expect(screen.getByRole("list", { name: "막힌 이유" }).textContent).toContain("정본 소스는 SEC");
  });

  it("한 시장을 여러 소스가 나눠 줄 때 어느 종류를 누가 주는지 뭉개지 않는다", () => {
    given({
      capabilities: panel<unknown[]>({
        data: [
          // 실제 배선이다: SEC 은 미국 마스터만, 토스는 미국 캔들만 준다 (MD-AD-17)
          { source: "sec", market: "NASDAQ", dataKind: "instrument_master", available: true, reason: null },
          { source: "toss", market: "NASDAQ", dataKind: "daily_bar", available: true, reason: null },
          { source: "toss", market: "NASDAQ", dataKind: "minute_bar", available: true, reason: null },
        ],
      }),
      symbol: null,
    });
    render(<IngestConsole />);

    const text = screen.getByRole("list", { name: "지금 받을 수 있는 것" }).textContent ?? "";
    expect(text).toContain("종목목록(sec)");
    expect(text).toContain("일봉(toss)");
    // 곱집합으로 읽히면 「토스가 미국 마스터를 준다」가 된다 — 이 이슈가 바로잡으려던 사실의 반대다
    expect(text).not.toContain("종목목록(sec, toss)");
    expect(text).not.toContain("종목목록(toss)");
  });

  it("되는 것이 하나도 없으면 그 목록을 아예 세우지 않는다", () => {
    given({
      capabilities: panel<unknown[]>({
        data: [
          {
            source: "toss",
            market: "KOSPI",
            dataKind: "daily_bar",
            available: false,
            reason: "키가 없습니다",
            code: null,
          },
        ],
      }),
      symbol: null,
    });
    render(<IngestConsole />);
    expect(screen.queryByRole("list", { name: "지금 받을 수 있는 것" })).toBeNull();
  });

  it("성공했는데 0행이면 왜인지 말한다 — 「받음」만 보이면 성공으로 읽힌다", () => {
    given({
      capabilities: usableKrx(),
      runs: panel<unknown[]>({
        data: [
          {
            run_id: 3,
            source: "toss",
            job_kind: "daily_bar",
            scope: "KOSPI:005930",
            period_from: null,
            period_to: "2026-08-19",
            status: "succeeded",
            cursor: null,
            written_rows: 0,
            skipped_rows: 1,
            failed_reason: null,
            started_dt: null,
            finished_dt: null,
            reg_dt: null,
          },
        ],
      }),
    });
    render(<IngestConsole />);
    const history = section("적재").textContent ?? "";
    expect(history).toContain("종목 마스터에 없는 종목이라 건너뛰었습니다");
    expect(history).toContain("건너뜀 1");
  });
});
