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

const SYMBOL = { market: "KRX", ticker: "005930", name: "삼성전자" };

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
    data: [{ source: "data_go_kr", market: "KRX", dataKind: "candles", available: true, reason: null }],
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
          { source: "sec", market: "US", dataKind: "financials", available: true, reason: null },
          { source: "alpaca", market: "US", dataKind: "candles", available: false, reason: serverReason },
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
          { source: "alpaca", market: "US", dataKind: "candles", available: true, reason: null },
          { source: "data_go_kr", market: "KRX", dataKind: "candles", available: true, reason: null },
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
        data: [{ source: "data_go_kr", market: "KRX", dataKind: "candles", available: false, reason: "키가 없습니다" }],
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
            scope: "KRX:005930",
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
      scope: "KRX:005930",
    });
  });
});
