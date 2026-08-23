// #350 — **적재가 끝나면 그 적재본을 읽는 자리가 스스로 다시 받는다.**
//
// 이슈가 잡은 것: 242행이 들어간 뒤에도 차트는 60초 넘게 「아직 적재되지 않았습니다」였고,
// 바로 옆 이력 패널은 「받음 · 242행」이었다. 화면이 한 자리에서 두 말을 했다.
//
// 손으로 훑는 것으로는 이 클래스가 안 닫힌다 — 「적재가 바꾸는 데이터를 읽는 자리」는 서비스
// 계층에 흩어져 있고, 새 패널이 하나 붙을 때마다 같은 구멍이 다시 열린다. 그래서 세 축을 잡는다:
//
//   ① **신호의 의미** — `ingestSignalStore` 가 언제 세대를 올리고 언제 안 올리나 (단위).
//   ② **전수** — 적재가 채우는 백엔드 경로를 읽는 함수를 서비스 계층에서 **찾아내고**,
//      그 함수를 부르는 화면·훅이 **전부** 신호를 구독하는지. 목록을 손으로 적지 않는다 —
//      새 조회 함수가 생기면 자동으로 검사 대상이 된다.
//   ③ **쓰는 쪽** — 적재 완료를 아는 자리(이력 폴러)가 실제로 신호를 낸다.
//
// **fail-closed**: 훑은 파일·찾은 조회 함수·그 호출자가 하나라도 0건이면 실패한다. 검사 건수를
// 출력에 남겨, 초록이 "위반 없음"인지 "아무것도 안 봤음"인지 읽는 사람이 가릴 수 있게 한다.
//
// **검증 경계** — ②③ 은 정적 검사다. 화면이 실제로 다시 그려지는지는 브라우저로 확인한다.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { beforeEach, describe, expect, it } from "vitest";

import {
  INSTRUMENT_MASTER_SIGNAL_KEY,
  barSignalKey,
  observeIngestRuns,
  useIngestSignalStore,
} from "@/stores/terminal/ingestSignalStore";
import type { IngestRunOut } from "@/schemas/terminal/ingest";

const FRONTEND_ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));

/* ------------------------------------------------------------------ 공용 ---- */

function walk(dir: string): string[] {
  const entries = fs.existsSync(dir) ? fs.readdirSync(dir, { withFileTypes: true }) : [];
  return entries.flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return walk(full);
    return /\.tsx?$/.test(entry.name) ? [full] : [];
  });
}

function rel(file: string): string {
  return path.relative(FRONTEND_ROOT, file);
}

/* ------------------------------------------------------- ① 신호의 의미 ---- */

function run(overrides: Partial<IngestRunOut> & { run_id: number }): IngestRunOut {
  return {
    source: "toss",
    job_kind: "daily_bar",
    scope: "KOSPI:012330",
    period_from: null,
    period_to: null,
    status: "succeeded",
    cursor: null,
    written_rows: 242,
    skipped_rows: null,
    failed_reason: null,
    started_dt: null,
    finished_dt: null,
    reg_dt: null,
    ...overrides,
  } as IngestRunOut;
}

function revisionOf(key: string): number {
  return useIngestSignalStore.getState().revisionByKey[key] ?? 0;
}

describe("#350 ① 적재 신호 — 무엇이 세대를 올리나", () => {
  beforeEach(() => {
    useIngestSignalStore.setState({ revisionByKey: {}, seenRuns: null });
  });

  const KEY = barSignalKey("KOSPI", "012330");

  it("첫 판은 기준선일 뿐 신호가 아니다 — 화면을 열 때마다 헛 재조회가 되면 안 된다", () => {
    observeIngestRuns([run({ run_id: 1 })]);
    expect(revisionOf(KEY)).toBe(0);
  });

  it("돌던 잡이 끝나면 그 종목의 세대가 오른다", () => {
    observeIngestRuns([run({ run_id: 1, status: "running", written_rows: 0 })]);
    observeIngestRuns([run({ run_id: 1, status: "succeeded", written_rows: 242 })]);
    expect(revisionOf(KEY)).toBe(1);
  });

  it("기준선을 잡은 뒤 처음 보는 잡이 이미 끝나 있어도 세대가 오른다", () => {
    observeIngestRuns([]);
    observeIngestRuns([run({ run_id: 7 })]);
    expect(revisionOf(KEY)).toBe(1);
  });

  it("도는 중에 행 수가 늘어도 세대가 오른다 — 긴 잡을 끝까지 옛 화면으로 기다리지 않는다", () => {
    observeIngestRuns([run({ run_id: 1, status: "running", written_rows: 10 })]);
    observeIngestRuns([run({ run_id: 1, status: "running", written_rows: 90 })]);
    expect(revisionOf(KEY)).toBe(1);
  });

  it("아무것도 안 바뀐 판은 세대를 올리지 않는다 — 폴링마다 재조회가 되면 안 된다", () => {
    observeIngestRuns([run({ run_id: 1 })]);
    observeIngestRuns([run({ run_id: 1 })]);
    observeIngestRuns([run({ run_id: 1 })]);
    expect(revisionOf(KEY)).toBe(0);
  });

  it("받은 종목만 흔든다 — 남의 종목 세대는 그대로다", () => {
    observeIngestRuns([]);
    observeIngestRuns([run({ run_id: 1 })]);
    expect(revisionOf(KEY)).toBe(1);
    expect(revisionOf(barSignalKey("KOSPI", "005930"))).toBe(0);
  });

  it("한 잡이 여러 종목을 담으면 그 전부의 세대가 오른다", () => {
    observeIngestRuns([]);
    observeIngestRuns([run({ run_id: 1, scope: "NASDAQ:AAPL,MSFT" })]);
    expect(revisionOf(barSignalKey("NASDAQ", "AAPL"))).toBe(1);
    expect(revisionOf(barSignalKey("NASDAQ", "MSFT"))).toBe(1);
  });

  it("분봉 적재도 같은 키를 흔든다 — 조회 시점에 분봉이 일봉을 갈아 끼우기 때문이다", () => {
    observeIngestRuns([]);
    observeIngestRuns([run({ run_id: 1, job_kind: "minute_bar" })]);
    expect(revisionOf(KEY)).toBe(1);
  });

  it("종목 마스터 잡은 마스터 키를 흔든다", () => {
    observeIngestRuns([]);
    observeIngestRuns([run({ run_id: 1, job_kind: "instrument_master", scope: "KOSPI" })]);
    expect(revisionOf(INSTRUMENT_MASTER_SIGNAL_KEY)).toBe(1);
    expect(revisionOf(KEY)).toBe(0);
  });

  it("실패한 잡도 신호다 — 사유가 화면에 닿아야 하고, 받다 만 행이 남아 있을 수 있다", () => {
    observeIngestRuns([run({ run_id: 1, status: "running", written_rows: 0 })]);
    observeIngestRuns([run({ run_id: 1, status: "failed", written_rows: 0 })]);
    expect(revisionOf(KEY)).toBe(1);
  });

  it("모르는 job_kind 는 아무 자리도 흔들지 않는다 — 짐작해서 남의 자리를 다시 그리지 않는다", () => {
    observeIngestRuns([]);
    observeIngestRuns([run({ run_id: 1, job_kind: "something_new", scope: "KOSPI:012330" })]);
    expect(useIngestSignalStore.getState().revisionByKey).toEqual({});
  });
});

/* ---------------------------------------------------------- ② 전수 ---- */

/**
 * 적재가 채우는 백엔드 경로 — 이 경로를 읽는 프론트 조회 함수가 곧 「적재 완료에 반응해야 하는
 * 자리」다. `job_kind` 셋(`daily_bar`·`minute_bar` → `tn_daily_bar`·`tn_minute_bar`,
 * `instrument_master` → `tn_instrument`)이 채우는 표를 내는 경로가 정확히 이 둘이다.
 *
 * 시세(`/quote`)·소스표(`/market-capability`)는 적재본이 아니라 실시간·설정이라 대상이 아니다.
 */
const INGEST_FED_PATH_PREFIXES = ["/api/external/backend/bar", "/api/external/backend/instrument"];

/** 신호를 구독하는 통로. 이 훅을 부르지 않으면 세대가 올라도 그 자리는 모른다. */
const SUBSCRIBE_HOOK = "useIngestRevision";

interface Reader {
  name: string;
  file: string;
}

/** 서비스 계층에서 적재본을 읽는 exported 함수를 **찾아낸다** (목록을 손으로 적지 않는다). */
function discoverIngestFedReaders(): Reader[] {
  const files = walk(path.join(FRONTEND_ROOT, "services"));
  const readers: Reader[] = [];

  for (const file of files) {
    const source = fs.readFileSync(file, "utf8");

    // 이 파일이 들고 있는 URL 상수 중 적재본 경로를 가리키는 것.
    const ingestFedConsts = new Set<string>();
    for (const match of source.matchAll(/const\s+(\w+)\s*=\s*"([^"]+)"/g)) {
      if (INGEST_FED_PATH_PREFIXES.some((prefix) => match[2].startsWith(prefix))) ingestFedConsts.add(match[1]);
    }
    if (ingestFedConsts.size === 0) continue;

    // exported 함수 블록으로 잘라, 그 상수를 쓰는 함수만 고른다.
    const blocks = [...source.matchAll(/export\s+(?:async\s+)?function\s+(\w+)/g)];
    for (let i = 0; i < blocks.length; i += 1) {
      const start = blocks[i].index ?? 0;
      const end = i + 1 < blocks.length ? (blocks[i + 1].index ?? source.length) : source.length;
      const body = source.slice(start, end);
      if ([...ingestFedConsts].some((name) => new RegExp(`\\b${name}\\b`).test(body))) {
        readers.push({ name: blocks[i][1], file });
      }
    }
  }
  return readers;
}

/** 화면·훅 계층에서 그 조회 함수를 부르는 파일. 서비스·테스트 자신은 제외한다. */
function callSitesOf(reader: Reader, consumerFiles: string[]): string[] {
  return consumerFiles.filter((file) => new RegExp(`\\b${reader.name}\\s*\\(`).test(fs.readFileSync(file, "utf8")));
}

describe("#350 ② 전수 — 적재본을 읽는 자리가 전부 신호를 구독한다", () => {
  const consumerFiles = ["components", "hooks", "app"].flatMap((dir) => walk(path.join(FRONTEND_ROOT, dir)));
  const readers = discoverIngestFedReaders();

  it("훑을 파일과 찾을 조회 함수가 실제로 있다 (fail-closed)", () => {
    // 경로가 사라지거나 파싱이 빗나가면 "대상 없음 = 위반 없음"으로 조용히 초록이 된다.
    expect(consumerFiles.length).toBeGreaterThan(50);
    expect(readers.length).toBeGreaterThan(0);
    console.log(
      `[#350 전수] 소비자 후보 ${consumerFiles.length}개 파일 · 적재본 조회 함수 ${readers.length}개: ` +
        readers.map((r) => `${r.name}(${rel(r.file)})`).join(", "),
    );
  });

  it("찾아낸 조회 함수마다 호출자가 있고, 그 호출자가 전부 적재 신호를 구독한다", () => {
    const census: string[] = [];
    const violations: string[] = [];
    let checkedCallSites = 0;

    for (const reader of readers) {
      const sites = callSitesOf(reader, consumerFiles);
      // 호출자가 0이면 그물이 아무것도 안 본 것이다 — 죽은 조회 함수든 파싱 실패든 시끄럽게 낸다.
      if (sites.length === 0) {
        violations.push(`${reader.name}: 호출자를 하나도 못 찾았다 (죽은 조회 함수이거나 검사가 빗나갔다)`);
        continue;
      }
      for (const site of sites) {
        checkedCallSites += 1;
        const source = fs.readFileSync(site, "utf8");
        const bound = source.match(new RegExp(`const\\s+(\\w+)\\s*=\\s*${SUBSCRIBE_HOOK}\\(`));
        if (bound === null) {
          violations.push(`${rel(site)}: ${reader.name} 을 부르면서 ${SUBSCRIBE_HOOK} 을 구독하지 않는다`);
          continue;
        }
        // 구독만 하고 안 쓰면 세대가 올라도 다시 받지 않는다 — 이름이 다시 등장해야 한다
        // (의존성 배열이든 `useOnDemand` 의 세대 키든).
        const uses = source.match(new RegExp(`\\b${bound[1]}\\b`, "g")) ?? [];
        if (uses.length < 2) {
          violations.push(`${rel(site)}: ${SUBSCRIBE_HOOK} 결과(${bound[1]})를 받아만 두고 쓰지 않는다`);
          continue;
        }
        census.push(`${reader.name} @ ${rel(site)} → ${bound[1]} (${uses.length}회 등장)`);
      }
    }

    console.log(`[#350 전수] 호출 지점 ${checkedCallSites}개 검사 · 구독 확인 ${census.length}개`);
    for (const line of census) console.log(`  · ${line}`);

    expect(checkedCallSites).toBeGreaterThan(0);
    expect(violations).toEqual([]);
    expect(census.length).toBe(checkedCallSites);
  });
});

/* ------------------------------------------------------- ③ 쓰는 쪽 ---- */

describe("#350 ③ 적재 완료를 아는 자리가 신호를 낸다", () => {
  it("이력을 폴링하는 화면이 판마다 observeIngestRuns 를 부른다", () => {
    const files = ["components", "hooks", "app"].flatMap((dir) => walk(path.join(FRONTEND_ROOT, dir)));
    const emitters = files.filter((file) => /\bobserveIngestRuns\s*\(/.test(fs.readFileSync(file, "utf8")));
    console.log(`[#350 쓰는 쪽] ${files.length}개 파일 중 신호를 내는 자리 ${emitters.length}개: ${emitters.map(rel).join(", ")}`);
    // 0건이면 훅들이 영영 세대 0에 머문다 — 고친 것이 통째로 사라진 상태다.
    expect(emitters.length).toBeGreaterThan(0);
  });
});
