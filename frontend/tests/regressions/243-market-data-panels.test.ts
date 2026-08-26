// #2 — 시세 계층이 프론트까지 오는 길의 그물 세 겹.
//
// 이 파일이 막는 것은 셋 다 "조용한" 실패다 — 화면은 멀쩡해 보이는데 내용이 틀린 부류:
//
//   ① **프록시 경로 lockstep** (anti-patterns 룰 13) — backend `APIRouter(prefix=)` 와
//      `app/api/external/backend/**` 의 `BACKEND_URL` 이 어긋나면 404 가 난다. 런타임에만
//      드러나고, 그마저도 그 패널을 열어 봐야 안다.
//   ② **빈 응답의 사유 전달** — 200 + 빈 배열 + `unavailable_reason` 이 왔는데 서비스 계층이
//      사유를 떨어뜨리면, 화면은 "데이터 없음"만 남는다. 그 순간 FR-021("왜 비었는지 말한다")이
//      사라진다.
//   ③ **샘플 데이터 규율** (룰 17) — `SAMPLE_CANDLES` 가 `placeholder` 분기 밖에서 쓰이면
//      키가 없어 빈 차트에 그럴싸한 가짜 캔들이 그려진다. 그건 "데이터가 들어왔다"로 읽힌다.
//
// **fail-closed**: ①·③은 검사 대상을 파일시스템에서 매번 다시 찾고, 0건이면 실패한다.
// 경로가 옮겨졌는데 조용히 초록이 되는 것이 이 레포가 반복해서 데인 부류다.
//
// **트리거 한계(적어 둔다)**: 이 파일은 `ci.yml` 의 `on.paths: frontend/**` 아래 돈다 —
// backend 만 바뀐 PR 에서는 ①이 돌지 않는다. backend prefix 를 바꾸면 프론트 프록시도 같이
// 고쳐야 하므로(byte-identical 규약) 실무상 두 축이 함께 바뀌지만, 한쪽만 바뀌는 PR 에서 이
// 그물이 침묵한다는 사실 자체는 숨기지 않는다.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { beforeEach, describe, expect, it, vi } from "vitest";

const FRONTEND_ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));
const REPO_ROOT = path.dirname(FRONTEND_ROOT);
const EXTERNAL_BACKEND_ROOT = path.join(FRONTEND_ROOT, "app/api/external/backend");
const BACKEND_ROUTERS_ROOT = path.join(REPO_ROOT, "backend-service/app/routers");

vi.mock("@/utils/common/api/client", () => ({ apiCall: vi.fn() }));

function listFiles(dir: string, suffix: string): string[] {
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...listFiles(full, suffix));
    else if (entry.name.endsWith(suffix)) out.push(full);
  }
  return out;
}

/** backend 라우터가 선언한 prefix 집합 — SoT 다. */
function backendPrefixes(): Set<string> {
  const prefixes = new Set<string>();
  for (const file of listFiles(BACKEND_ROUTERS_ROOT, "_router.py")) {
    const match = fs.readFileSync(file, "utf8").match(/APIRouter\(\s*prefix\s*=\s*"([^"]+)"/);
    if (match) prefixes.add(match[1]);
  }
  return prefixes;
}

/** 프록시 route.ts 가 조립하는 backend 경로 (`env.BACKEND_SERVICE_URL + "..."`). */
function proxyBackendPaths(): Array<{ file: string; backendPath: string }> {
  return listFiles(EXTERNAL_BACKEND_ROOT, "route.ts").flatMap((file) => {
    const match = fs.readFileSync(file, "utf8").match(/BACKEND_SERVICE_URL\s*\+\s*"([^"]+)"/);
    return match ? [{ file: path.relative(FRONTEND_ROOT, file), backendPath: match[1] }] : [];
  });
}

describe("#2 ① 프록시 경로가 backend prefix 와 lockstep", () => {
  it("모든 external/backend 프록시의 경로 선두가 실재하는 backend prefix 다", () => {
    const prefixes = backendPrefixes();
    const proxies = proxyBackendPaths();

    // fail-closed — 어느 쪽이든 0건이면 "위반 없음"이 아니라 "아무것도 안 봤음"이다.
    expect(prefixes.size, "backend 라우터 prefix 를 0건 수집했다").toBeGreaterThan(0);
    expect(proxies.length, "프록시 route.ts 를 0건 수집했다").toBeGreaterThan(0);

    const mismatched = proxies.filter(({ backendPath }) => {
      const head = `/${backendPath.split("/").filter(Boolean)[0] ?? ""}`;
      return !prefixes.has(head);
    });
    expect(mismatched, `backend prefix 에 없는 프록시 경로: ${JSON.stringify(mismatched)}`).toEqual([]);
  });

  it("이번에 추가한 시세 경로 넷이 실제로 배선돼 있다", () => {
    const paths = proxyBackendPaths().map(({ backendPath }) => backendPath);
    for (const expected of ["/bar/daily", "/bar/minute", "/quote/batch", "/market-capability"]) {
      expect(paths, `${expected} 프록시가 없다`).toContain(expected);
    }
  });
});

describe("#2 ② 빈 응답이 사유를 들고 온다", () => {
  beforeEach(() => vi.resetModules());

  it("unavailable_reason 이 있으면 그대로 올린다 — 빈 배열로 뭉개지 않는다", async () => {
    const { apiCall } = await import("@/utils/common/api/client");
    vi.mocked(apiCall).mockResolvedValue({
      items: [],
      total_count: 0,
      market: "KOSPI",
      symbol: "005930",
      interval: "1d",
      source: null,
      adj_policy: null,
      asof: null,
      unavailable_reason: "data_go_kr 인증키가 등록되지 않았습니다",
    } as never);

    const { selectCandles } = await import("@/services/terminal/marketService");
    const result = await selectCandles({
      ticker: "005930",
      market: "KOSPI",
      interval: "1d",
      from: "2026-01-02",
      to: "2026-01-31",
    });

    expect(result.items).toEqual([]);
    expect(result.unavailableReason).toBe("data_go_kr 인증키가 등록되지 않았습니다");
  });

  it("값이 있으면 사유가 null 이고 출처에 수정주가 정책이 실린다 (FR-019)", async () => {
    const { apiCall } = await import("@/utils/common/api/client");
    vi.mocked(apiCall).mockResolvedValue({
      items: [{ time: "2026-01-02", open: 1, high: 2, low: 0.5, close: 1.5, volume: 10, trade_value: null }],
      total_count: 1,
      market: "NASDAQ",
      symbol: "AAPL",
      interval: "1d",
      source: "alpaca",
      adj_policy: "raw",
      asof: "2026-01-03T00:00:00",
      unavailable_reason: null,
    } as never);

    const { selectCandles } = await import("@/services/terminal/marketService");
    const result = await selectCandles({
      ticker: "AAPL",
      market: "NASDAQ",
      interval: "1d",
      from: "2026-01-02",
      to: "2026-01-31",
    });

    expect(result.unavailableReason).toBeNull();
    expect(result.source).toBe("alpaca · raw");
    expect(result.items).toHaveLength(1);
  });

  it("월봉은 조용한 빈 배열이 아니라 '아직 없다'는 사유다", async () => {
    const { selectCandles } = await import("@/services/terminal/marketService");
    const result = await selectCandles({
      ticker: "AAPL",
      market: "NASDAQ",
      interval: "1M",
      from: "2026-01-02",
      to: "2026-01-31",
    });
    expect(result.items).toEqual([]);
    expect(result.unavailableReason).toMatch(/월봉/);
  });
});

describe("#2 ③ 샘플 캔들은 placeholder 분기에서만 쓰인다 (룰 17)", () => {
  it("ChartPanel 이 unavailable 사유를 임시 캔들로 덮지 않는다", () => {
    const source = fs.readFileSync(path.join(FRONTEND_ROOT, "components/features/ChartPanel/ChartPanel.tsx"), "utf8");
    expect(source, "SAMPLE_CANDLES 를 쓰지 않게 바뀌었다면 이 그물의 전제가 사라진 것이다").toContain("SAMPLE_CANDLES");
    // 사유가 있는 unavailable 을 분리해 뽑아내고, 임시 캔들은 placeholder 쪽에만 붙는다.
    expect(source).toContain("unavailableReason");
    expect(source).toContain("PanelUnavailable");
    expect(source, "isPlaceholder 가 unavailable 전체를 삼키면 사유가 사라진다").toContain("isNoContextYet");
  });
});

describe("#2 ④ 「키가 아직 없다」만 임시 데이터로 덮는다", () => {
  it("credential_missing 은 임시 데이터가 되고 사유가 note 로 살아남는다", async () => {
    const { provenanceForUnavailable, CREDENTIAL_MISSING_CODE } = await import("@/lib/terminal/marketDataError");
    const reason = "data_go_kr: .env 에 데이터 소스 키를 채우세요";
    expect(provenanceForUnavailable(reason, CREDENTIAL_MISSING_CODE)).toEqual({
      kind: "placeholder",
      source: "임시 데이터",
      hint: reason,
    });
  });

  it("코드 없는 사유는 덮이지 않는다 — 진짜 결손이 숨으면 안 된다", async () => {
    const { provenanceForUnavailable } = await import("@/lib/terminal/marketDataError");
    for (const code of [null, "upstream_error", "not_supported"]) {
      expect(provenanceForUnavailable("상류가 응답하지 않습니다", code)).toEqual({
        kind: "unavailable",
        reason: "상류가 응답하지 않습니다",
        because: "no-source",
      });
    }
  });

  it("코드 문자열이 백엔드 상수와 같다 — 한쪽만 바뀌면 조용히 갈린다", async () => {
    const { CREDENTIAL_MISSING_CODE } = await import("@/lib/terminal/marketDataError");
    const backend = fs.readFileSync(path.join(REPO_ROOT, "backend-service/app/providers/base.py"), "utf8");
    const declared = /^CREDENTIAL_MISSING_CODE = "([^"]+)"$/m.exec(backend);
    expect(declared, "백엔드 상수를 못 찾았다 — 이름이 바뀌었으면 이 그물부터 고쳐라").not.toBeNull();
    expect(CREDENTIAL_MISSING_CODE).toBe(declared![1]);
  });

  it("사유가 화면까지 간다 — 패널이 hint 를 넘기고 틀이 그것을 낸다", () => {
    for (const file of [
      "components/features/ChartPanel/ChartPanel.tsx",
      "components/features/SymbolInfoPanel/SymbolInfoPanel.tsx",
    ]) {
      const source = fs.readFileSync(path.join(FRONTEND_ROOT, file), "utf8");
      expect(source, `${file} 가 hint 를 안 넘기면 사유가 그 자리에서 죽는다`).toMatch(
        /hint:\s*\w+\.provenance\.kind === "placeholder"/,
      );
    }
    const frame = fs.readFileSync(path.join(FRONTEND_ROOT, "components/features/Terminal/PanelFrame.tsx"), "utf8");
    expect(frame, "틀이 hint 를 렌더하지 않으면 넘겨도 안 보인다").toContain("provenance.hint");
  });

  it("훅과 서비스가 실제로 그 판정을 쓴다 — 순수 함수만 통과하고 화면은 옛길일 수 있다", () => {
    const hook = fs.readFileSync(path.join(FRONTEND_ROOT, "hooks/terminal/useLoadedSeries.ts"), "utf8");
    expect(hook).toContain("provenanceForUnavailable(result.unavailableReason, result.unavailableCode)");
    const service = fs.readFileSync(path.join(FRONTEND_ROOT, "services/terminal/marketService.ts"), "utf8");
    expect(service, "코드를 안 실어 보내면 판정이 늘 unavailable 로 떨어진다").toContain("unavailable_code");
  });
});
