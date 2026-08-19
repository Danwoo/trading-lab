"use client";

import { useEffect, useMemo, useState } from "react";
import { ProvenanceBadge } from "@/components/features/Terminal/ProvenanceBadge";
import { cn } from "@/components/shared/ui/primitives/cn";
import { useBarGaps } from "@/hooks/terminal/useBarGaps";
import { useIngestRuns } from "@/hooks/terminal/useIngestRuns";
import { useMarketCapabilities } from "@/hooks/terminal/useMarketCapabilities";
import { useTerminalSymbol } from "@/hooks/terminal/useTerminalContext";
import { insertIngestRun } from "@/services/terminal/ingestService";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";
import type { DataKind, IngestRunOut } from "@/schemas/terminal/ingest";
import type { MarketCapability } from "@/services/terminal/marketService";
import { CREDENTIAL_MISSING_CODE } from "@/lib/terminal/marketDataError";

/**
 * 시세 화면의 **적재 콘솔** — 마일스톤 2 가 이 화면에서 요구하는 두 줄이 여기서 보인다:
 *
 * - *"적재를 실행하면 **어디까지 받았고 무엇이 실패했는지** 화면에서 보인다"*
 * - *"키가 없어도 기동되고, **어떤 패널이 왜 비어 있는지** 안내된다"*
 *
 * 패널이 아니라 **화면의 도구**로 둔다. 패널은 종목 문맥에 매인 자리인데 적재는 워크스페이스
 * 단위 작업이라, 패널 격자에 넣으면 종목을 고르기 전에는 열 수 없는 것처럼 읽힌다.
 */

/** 상태별 표시 — 색은 토큰만 쓴다. `rate_limited` 는 실패가 아니라 이어받을 지점이 있는 상태다. */
/** 돌고 있는 잡이 있을 때만 다시 묻는 주기. */
const POLL_MS = 4000;

const STATUS_TONE: Record<string, string> = {
  succeeded: "text-ink",
  running: "text-ink",
  queued: "text-ink-muted",
  // 실패가 아니라 이어받을 지점이 있는 상태다 — 실패색을 쓰면 거짓말이 된다.
  // 뜻은 아래 라벨(「한도에 걸려 멈춤」)이 진다. 색이 유일한 전달자면 색을 못 보는 사람에게는
  // 아무 정보도 아니다.
  rate_limited: "text-ink",
  failed: "text-danger",
};

const STATUS_LABEL: Record<string, string> = {
  succeeded: "받음",
  running: "받는 중",
  queued: "대기",
  rate_limited: "한도에 걸려 멈춤",
  failed: "실패",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="flex min-w-0 flex-col gap-1.5">
      <h3 className="break-keep text-2xs font-ui uppercase tracking-wide text-ink-muted">{title}</h3>
      {children}
    </section>
  );
}

/**
 * 막힌 조합을 **사유로 묶는다.**
 *
 * 조합은 소스 × 시장 × 데이터종류라 같은 사유가 수십 번 되풀이된다 — 실측으로 46건이 9종이었다.
 * 되풀이된 벽은 읽히지 않고, 첫 화면이 통째로 회색으로 보이게 만든다.
 *
 * 키가 없어 막힌 것(`credential_missing`)을 앞에 세운다 — 그것만이 사용자가 오늘 풀 수 있는
 * 것이고, 나머지는 그 소스가 원래 안 주는 것이라 읽고 넘어갈 자리다.
 */
export function groupBlockedByReason(rows: MarketCapability[]) {
  const groups = new Map<string, { reason: string; fixable: boolean; targets: string[] }>();

  for (const row of rows) {
    const reason = row.reason ?? "사유가 기록되지 않았습니다";
    const group = groups.get(reason) ?? {
      reason,
      fixable: row.code === CREDENTIAL_MISSING_CODE,
      targets: [],
    };
    group.targets.push(`${row.source} · ${row.market} · ${row.dataKind}`);
    groups.set(reason, group);
  }

  return [...groups.values()].sort(
    (a, b) => Number(b.fixable) - Number(a.fixable) || b.targets.length - a.targets.length,
  );
}

/** 데이터 종류의 사람 말. 값 자체는 백엔드 어휘(`DATA_KINDS`)라 화면에서 옮긴다. */
const KIND_LABEL: Record<string, string> = {
  instrument_master: "종목목록",
  daily_bar: "일봉",
  minute_bar: "분봉",
  quote: "시세",
  orderbook: "호가",
};

/**
 * **지금 받을 수 있는 것**을 시장별로 묶는다.
 *
 * 이 섹션이 막힌 것만 나열하던 동안, 잘 도는 소스는 화면에 한 줄도 안 나왔다. 부분적으로
 * 막힌 소스는 **막힌 쪽만 보여 「그 소스는 안 된다」로 읽혔다** — 토스가 국내를 열어 두고
 * 미국 마스터만 SEC 에 양보하는데, 화면에는 미국 3행만 떠서 정반대로 읽혔다(#252).
 */
export function groupAvailableByMarket(rows: MarketCapability[]) {
  // **종류마다 소스를 붙인다.** 시장별로 종류와 소스를 따로 합집합하면 곱집합으로 읽혀
  // 「토스가 미국 종목 마스터를 준다」가 된다 — 그 반대가 이 화면이 바로잡으려던 사실이다.
  const groups = new Map<string, Map<string, Set<string>>>();
  for (const row of rows) {
    const byKind = groups.get(row.market) ?? new Map<string, Set<string>>();
    const label = KIND_LABEL[row.dataKind] ?? row.dataKind;
    const sources = byKind.get(label) ?? new Set<string>();
    sources.add(row.source);
    byKind.set(label, sources);
    groups.set(row.market, byKind);
  }
  return [...groups.entries()]
    .map(([market, byKind]) => ({
      market,
      offers: [...byKind.entries()].map(([kind, sources]) => `${kind}(${[...sources].sort().join(", ")})`),
    }))
    .sort((a, b) => a.market.localeCompare(b.market));
}

/** 소스 가용성 — 무엇이 지금 되고, 안 되는 것은 왜 안 되는지. */
function Capabilities({ rows, loading }: { rows: MarketCapability[] | null; loading: boolean }) {
  if (rows === null) {
    // 「못 읽었다」와 「비어 있다」는 다르다 — 앞의 것은 고쳐야 할 일이라 색으로 갈라 둔다.
    return loading ? (
      <p className="break-keep text-2xs text-ink-muted">소스를 확인하고 있습니다…</p>
    ) : (
      <p className="break-keep text-2xs text-danger">소스 목록을 읽지 못했습니다.</p>
    );
  }
  if (rows.length === 0) {
    return <p className="break-keep text-2xs text-ink-muted">등록된 소스가 없습니다.</p>;
  }

  const blocked = rows.filter((row) => !row.available);
  const open = groupAvailableByMarket(rows.filter((row) => row.available));
  const groups = groupBlockedByReason(blocked);
  const fixableCount = groups.filter((group) => group.fixable).reduce((sum, group) => sum + group.targets.length, 0);

  return (
    <div className="flex min-w-0 flex-col gap-1">
      <p className="break-keep text-2xs text-ink-muted">
        {rows.length}건 중 <span className="text-ink">{rows.length - blocked.length}건</span> 사용 가능
        {blocked.length > 0 && (
          <>
            {" "}
            · {blocked.length}건은 아래 {groups.length}가지 이유로 막혀 있습니다
            {fixableCount > 0 && <> (그중 {fixableCount}건은 키를 넣으면 열립니다)</>}
          </>
        )}
      </p>
      {open.length > 0 && (
        <>
          <p className="break-keep text-2xs text-ink">지금 받을 수 있는 것</p>
          <ul aria-label="지금 받을 수 있는 것" className="flex min-w-0 flex-col gap-0.5">
            {open.map((row) => (
              <li key={row.market} className="flex min-w-0 flex-wrap items-baseline gap-x-1.5 text-2xs">
                <span className="font-mono text-ink">{row.market}</span>
                <span className="min-w-0 break-keep text-ink-muted">{row.offers.join(" · ")}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {groups.length > 0 && (
        <>
          <p className="break-keep text-2xs text-ink-muted">막혀 있는 것</p>
          <ul aria-label="막힌 이유" className="flex min-w-0 flex-col gap-1.5">
            {/* 사유는 **서버가 정본**이다 — env 항목명과 발급 경로까지 완전한 문장으로 온다.
              프론트가 같은 안내를 다시 만들면 서버가 아는 항목명과 갈린다. */}
            {groups.map((group) => (
              <li key={group.reason} className="flex min-w-0 flex-col gap-0.5 text-2xs">
                <p className={cn("min-w-0 break-keep", group.fixable ? "text-danger" : "text-ink-muted")}>
                  {group.reason} <span className="text-ink-muted">({group.targets.length}건)</span>
                </p>
                <p className="min-w-0 break-words font-mono text-2xs text-ink-muted">{group.targets.join(", ")}</p>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

/**
 * 「받음 0행」이 성공처럼 보이지 않게 한다.
 *
 * 잡은 성공했는데 한 행도 안 들어온 경우가 실제로 있다 — 종목 마스터에 없는 심볼을 캔들 적재에
 * 넣으면 서버가 그 심볼을 건너뛰고 `succeeded` 로 끝낸다. 화면이 「받음 · 0행」만 보여 주면
 * 사용자는 성공했다고 읽고 차트가 왜 비어 있는지 알 길이 없다 (FR-021 — 없는 값을 0 으로 뭉개지 않는다).
 */
function emptyReason(run: IngestRunOut): string | null {
  if (run.status !== "succeeded" || run.written_rows !== 0) return null;
  if (run.job_kind === "instrument_master") return "받은 종목이 없습니다 — 소스 응답이 비었습니다.";
  if ((run.skipped_rows ?? 0) > 0) return "종목 마스터에 없는 종목이라 건너뛰었습니다 — 「종목 목록」을 먼저 받으세요.";
  return "그 구간에 받을 캔들이 없었습니다 (휴장이거나 이미 받은 구간입니다).";
}

/** 적재 이력 — 어디까지 받았고 무엇이 실패했는지. */
function Runs({ rows, loading }: { rows: IngestRunOut[] | null; loading: boolean }) {
  if (rows === null) {
    return loading ? (
      <p className="break-keep text-2xs text-ink-muted">이력을 불러오고 있습니다…</p>
    ) : (
      <p className="break-keep text-2xs text-danger">이력을 읽지 못했습니다.</p>
    );
  }
  if (rows.length === 0) {
    return <p className="break-keep text-2xs text-ink-muted">아직 한 번도 적재하지 않았습니다.</p>;
  }

  return (
    <ul className="flex min-w-0 flex-col gap-0.5">
      {rows.slice(0, 8).map((run) => (
        <li key={run.run_id} className="flex min-w-0 flex-wrap items-baseline gap-x-2 text-2xs">
          <span className={cn("font-mono", STATUS_TONE[run.status] ?? "text-ink-muted")}>
            {STATUS_LABEL[run.status] ?? run.status}
          </span>
          <span className="font-mono text-ink-muted">
            {run.source} · {run.job_kind}
            {run.scope ? ` · ${run.scope}` : ""}
          </span>
          {run.period_to && <span className="font-mono text-ink">~{run.period_to} 까지</span>}
          {run.written_rows !== null && <span className="text-ink-muted">{run.written_rows}행</span>}
          {run.skipped_rows !== null && run.skipped_rows > 0 && (
            <span className="text-ink-muted">건너뜀 {run.skipped_rows}</span>
          )}
          {emptyReason(run) && <span className="min-w-0 break-keep text-danger">{emptyReason(run)}</span>}
          {run.failed_reason && <span className="min-w-0 break-keep text-danger">{run.failed_reason}</span>}
        </li>
      ))}
    </ul>
  );
}

/**
 * 이 종목을 적재할 소스 — **캐패빌리티에서 고른다.** 소스 이름을 화면이 손으로 적으면
 * 백엔드 레지스트리와 갈린다: 등록되지 않은 이름은 큐잉이 성공하고 **워커에서 실패한다**.
 * 시장→소스 매핑을 프론트가 복제하는 것도 두 벌이 되는 길이다.
 *
 * 규칙: 그 시장의 캔들을 다루면서 **지금 사용 가능한** 소스 중 첫째. 없으면 `null` —
 * 그때는 버튼이 무엇이 없어서 못 하는지를 말한다.
 */
function pickSource(rows: MarketCapability[] | null, market: string, dataKind: DataKind): string | null {
  if (rows === null) return null;
  return rows.find((row) => row.market === market && row.dataKind === dataKind && row.available)?.source ?? null;
}

/**
 * 종목 목록을 받을 수 있는 (시장, 소스) — 마스터를 주는 소스가 실제로 열려 있는 곳만.
 *
 * **소스를 함께 보인다.** 같은 「종목 목록」이라도 합성 샘플과 실소스는 전혀 다른 것이고,
 * 시장 이름만 보이면 무엇을 받는지 모른 채 누르게 된다.
 */
function mastersAvailable(rows: MarketCapability[] | null): Array<{ market: string; source: string }> {
  if (rows === null) return [];
  const seen = new Set<string>();
  const out: Array<{ market: string; source: string }> = [];
  for (const row of rows) {
    if (row.dataKind !== "instrument_master" || !row.available || seen.has(row.market)) continue;
    seen.add(row.market);
    out.push({ market: row.market, source: row.source });
  }
  return out.sort((a, b) => a.market.localeCompare(b.market));
}

export function IngestConsole() {
  const symbol = useTerminalSymbol();
  const [reloadToken, setReloadToken] = useState(0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; failed: boolean } | null>(null);
  const [masterMarket, setMasterMarket] = useState("");
  const [barKind, setBarKind] = useState<DataKind>("daily_bar");

  const capabilities = useMarketCapabilities(true);
  const runs = useIngestRuns(reloadToken, true);
  const gaps = useBarGaps(true);

  const source = symbol === null ? null : pickSource(capabilities.data, symbol.market, "daily_bar");
  const masters = useMemo(() => mastersAvailable(capabilities.data), [capabilities.data]);
  // 기본값은 **지금 보고 있는 시장** 이다 — 알파벳 첫 시장을 기본으로 두면 관심 없는 시장을 받게 된다.
  const defaultMarket = masters.find((row) => row.market === symbol?.market)?.market ?? masters[0]?.market ?? "";
  const chosenMarket = masterMarket || defaultMarket;
  const masterSource = masters.find((row) => row.market === chosenMarket)?.source ?? null;

  /**
   * 적재 버튼이 무엇을 말할까 — **모르는 것을 「없다」고 하지 않는다.**
   *
   * `pickSource` 는 「아직 못 읽음」과 「읽었는데 없음」을 둘 다 `null` 로 준다. 그 둘을 뭉치면
   * 로딩 중에는 매번 잠깐 거짓말을 하고, 조회가 실패하면 **서버 장애를 키 문제로 오인시킨다** —
   * 사용자가 키를 발급받으러 간다. 「소스」 섹션은 이미 셋을 가르고 있는데 버튼만 안 갈랐다.
   */
  const buttonState = (() => {
    if (busy) return { label: "요청 중…", disabled: true };
    if (symbol === null) return { label: "종목을 고르면 적재합니다", disabled: true };
    if (capabilities.data === null) {
      return capabilities.isLoading
        ? { label: "소스를 확인하는 중입니다", disabled: true }
        : { label: "소스 목록을 읽지 못해 적재할 수 없습니다", disabled: true };
    }
    if (source === null) return { label: `${symbol.market} 를 받을 소스가 없습니다`, disabled: true };
    return {
      label: `${symbol.ticker} ${barKind === "minute_bar" ? "분봉" : "일봉"} 받기 (${source})`,
      disabled: false,
    };
  })();
  const missing = gaps.data?.missingDates ?? [];
  const runningNow = useMemo(
    () => (runs.data ?? []).some((run) => run.status === "running" || run.status === "queued"),
    [runs.data],
  );

  // 돌고 있는 잡이 있으면 스스로 다시 본다 — 「queued → running → succeeded」를 보려면
  // 화면이 물어봐야 한다. 멈춰 있으면 안 묻는다(조용한 폴링으로 서버를 계속 두드리지 않게).
  useEffect(() => {
    if (!runningNow) return;
    const timer = setInterval(() => setReloadToken((n) => n + 1), POLL_MS);
    return () => clearInterval(timer);
  }, [runningNow]);

  /**
   * 종목 목록(마스터) 받기 — **종목 선택에 매이지 않는 유일한 경로**다.
   *
   * 이 자리가 없으면 첫 진입이 순환에 갇힌다: 캔들을 받으려면 종목을 골라야 하고, 종목을
   * 고르려면 마스터가 있어야 하고, 마스터는 이 잡으로만 채워진다.
   */
  const startMaster = async () => {
    if (!chosenMarket || masterSource === null) {
      setMessage({ text: "종목 목록을 줄 소스가 없습니다 — 위 「소스」의 사유를 보세요.", failed: true });
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const created = await insertIngestRun({
        source: masterSource,
        job_kind: "instrument_master",
        scope: chosenMarket,
      });
      if (created === null) {
        setMessage({ text: "종목 목록 요청이 받아들여지지 않았습니다.", failed: true });
        return;
      }
      setMessage({
        text: `${chosenMarket} 종목 목록을 큐에 넣었습니다. 아래 이력에서 진행을 볼 수 있습니다.`,
        failed: false,
      });
      setReloadToken((n) => n + 1);
    } catch (error) {
      setMessage({ text: getApiErrorMessage(error), failed: true });
    } finally {
      setBusy(false);
    }
  };

  const start = async (kind: DataKind = "daily_bar") => {
    if (symbol === null) {
      setMessage({ text: "종목을 먼저 고르시면 그 종목을 적재합니다.", failed: true });
      return;
    }
    if (source === null) {
      setMessage({
        text: `${symbol.market} 시장의 캔들을 지금 받을 수 있는 소스가 없습니다 — 위 「소스」의 사유를 보세요.`,
        failed: true,
      });
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const created = await insertIngestRun({
        source,
        job_kind: kind,
        scope: `${symbol.market}:${symbol.ticker}`,
      });
      if (created === null) {
        setMessage({ text: "적재 요청이 받아들여지지 않았습니다.", failed: true });
        return;
      }
      setMessage({ text: "적재를 큐에 넣었습니다. 아래 이력에서 진행을 볼 수 있습니다.", failed: false });
      setReloadToken((n) => n + 1);
    } catch (error) {
      setMessage({ text: getApiErrorMessage(error), failed: true });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-label="적재" className="flex min-w-0 flex-col gap-3 border-b border-line bg-bg-raised px-3 py-2.5">
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-x-3 gap-y-1.5">
        <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
          <h2 className="break-keep text-sm font-ui text-ink">적재</h2>
          <span className="text-2xs">
            <ProvenanceBadge provenance={runs.provenance} />
          </span>
          {runningNow && <span className="break-keep text-2xs text-ink-muted">지금 돌고 있습니다.</span>}
        </div>
        {/* 주기는 고르는 것이고 실행은 하나다 — 버튼을 늘리면 무엇이 주 동작인지 흐려진다. */}
        <div role="group" aria-label="이 종목 받기" className="flex min-w-0 flex-wrap items-center gap-1.5">
          <select
            aria-label="받을 주기"
            value={barKind}
            onChange={(event) => setBarKind(event.target.value as DataKind)}
            className="min-h-touch-min rounded-control border border-line bg-bg-base px-2 py-1 text-2xs text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
          >
            <option value="daily_bar">일봉</option>
            <option value="minute_bar">분봉</option>
          </select>
          <button
            type="button"
            onClick={() => start(barKind)}
            disabled={buttonState.disabled}
            className="rounded-control border border-line px-2.5 py-1 text-2xs text-ink hover:border-line-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted disabled:opacity-50"
          >
            {buttonState.label}
          </button>
        </div>
      </div>

      {/* 종목 목록 — 종목을 고르기 **전에** 필요한 것이라 종목 선택과 나란히 두지 않는다. */}
      <div
        role="group"
        aria-label="종목 목록 받기"
        className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-2xs"
      >
        <span className="text-ink-muted">종목 목록</span>
        {masters.length === 0 ? (
          <span className="break-keep text-ink-muted">
            {capabilities.isLoading
              ? "소스를 확인하는 중입니다"
              : "지금 종목 목록을 줄 소스가 없습니다 — 아래 「소스」의 사유를 보세요."}
          </span>
        ) : (
          <>
            <select
              aria-label="종목 목록을 받을 시장"
              value={chosenMarket}
              onChange={(event) => setMasterMarket(event.target.value)}
              className="min-h-touch-min rounded-control border border-line bg-bg-base px-2 py-1 text-2xs text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
            >
              {masters.map((row) => (
                <option key={row.market} value={row.market}>
                  {row.market} · {row.source}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={startMaster}
              disabled={busy}
              className="rounded-control border border-line px-2.5 py-1 text-2xs text-ink hover:border-line-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted disabled:opacity-50"
            >
              {busy ? "요청 중…" : `${chosenMarket} 종목 목록 받기`}
            </button>
            <span className="break-keep text-ink-muted">종목을 고르기 전에 이것부터 받습니다.</span>
          </>
        )}
      </div>

      {message && (
        <p role="status" className={cn("break-keep text-2xs", message.failed ? "text-danger" : "text-ink-muted")}>
          {message.text}
        </p>
      )}

      <div className="grid min-w-0 gap-3 lg:grid-cols-3">
        <Section title="소스">
          <Capabilities rows={capabilities.data} loading={capabilities.isLoading} />
        </Section>

        <Section title="이력">
          <Runs rows={runs.data} loading={runs.isLoading} />
        </Section>

        <Section title="빠진 거래일">
          {symbol === null ? (
            <p className="break-keep text-2xs text-ink-muted">종목을 고르면 그 구간의 결측을 셉니다.</p>
          ) : gaps.data === null ? (
            gaps.isLoading ? (
              <p className="break-keep text-2xs text-ink-muted">결측을 세고 있습니다…</p>
            ) : (
              <p className="break-keep text-2xs text-danger">결측을 읽지 못했습니다.</p>
            )
          ) : missing.length === 0 ? (
            <p className="break-keep text-2xs text-ink-muted">
              {gaps.data.dateFrom} ~ {gaps.data.dateTo} 구간에 빠진 거래일이 없습니다.
            </p>
          ) : (
            <p className="break-keep text-2xs">
              <span className="text-danger">{missing.length}일</span>
              <span className="text-ink-muted">
                {" "}
                빠져 있습니다 ({gaps.data.dateFrom} ~ {gaps.data.dateTo}) — 가장 이른 결측 {missing[0]}
              </span>
            </p>
          )}
        </Section>
      </div>
    </section>
  );
}
