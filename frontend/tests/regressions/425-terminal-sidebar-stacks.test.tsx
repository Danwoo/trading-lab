// @vitest-environment jsdom
//
// #425 — 좁은 폭에서 시세 화면의 「종목 사이드바 · 패널 열」 짝이 세로로 쌓인다.
//
// ## 무엇을 지키나
//
// 사이드바는 `w-64`(256px) 고정이고 셸 레일이 46px 다. 그 둘이 가로로 남으면 390 폭에서 패널
// 열에 88px 밖에 안 남는다 — 차트 패널이 가격축과 접힌 버튼만 남고 캔들 영역이 사라진다
// (공용 스택 실측: 패널 열 88px · 차트 패널 72px). 화면 위쪽(적재 콘솔)은 `lg`(1024) 에서
// 이미 한 열로 접히므로 이 짝도 같은 경계를 쓴다.
//
// ## 왜 브라우저를 띄우나
//
// jsdom 에는 레이아웃이 없어 `getBoundingClientRect()` 가 전부 0 이다. 접힘은 **폭이 만드는
// 결과**라 클래스 문자열을 세는 정적 검사로는 「몇 px 이 남는가」를 못 잰다. 그래서
// `tests/a11y/touchTargets.test.tsx` 와 같은 방식으로 ① 실제 컴포넌트를 jsdom 에 렌더해 HTML 을
// 뽑고 ② 이 레포의 Tailwind 설정으로 CSS 를 실제로 생성해 ③ 헤드리스 크롬에서 잰다.
//
// ## 이 하네스가 제품과 다른 점 (정직하게)
//
// - 셸(`app/(main)/layout.tsx`)은 레일 46px + `overflow-auto` 인 `<main>` 만 본떠 세운다.
// - 적재 콘솔은 대역 상자로 세운다 — 세로 자리만 차지하면 되고, 이 검사의 축은 **가로 배분**이다.
//   높이 520px 은 공용 스택 390 폭 실측(사이드바 y=580)에서 가져왔다.
// - 패널 본문은 대역 컴포넌트다(`load` 만 갈아끼운다) — 패널 칸의 상자는 격자가 정하지 본문이
//   정하지 않는다.
//
// 그래서 이 검사가 증명하는 것은 **셸 골조가 만든 가로 배분**이고, 실제 화면의 확인은 PR 본문의
// 브라우저 실측이 진다.
import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import postcss from "postcss";
import tailwindcss from "tailwindcss";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";

import { theme } from "@/tailwind.config.mjs";
import { TerminalContainer } from "@/components/features/Terminal/TerminalContainer";
import { selectWatchlistList } from "@/services/watchlist/watchlistService";
import { selectHoldingList, selectPortfolioList } from "@/services/portfolio/portfolioService";
import type { WatchlistOut } from "@/schemas/watchlist/watchlist";
import type { PanelDefinition } from "@/types/terminal/panel";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  usePathname: () => "/terminal",
}));

vi.mock("@/hooks/shared/useSessionContext", () => ({
  useSessionContext: () => ({ workspaceId: 1, isLoaded: true }),
}));

// 적재 콘솔은 세로 자리만 차지하면 된다 — 이 검사의 축은 가로 배분이다.
vi.mock("@/components/features/Terminal/IngestConsole", () => ({
  IngestConsole: () => <div data-fixture="ingest-console" style={{ height: 520, flexShrink: 0 }} />,
}));

// 패널 본문은 대역으로 — 칸의 상자는 격자가 정한다. `load` 만 갈아끼우고 나머지(제목·능력·
// 종목 요구)는 진짜 레지스트리 그대로 쓴다.
vi.mock("@/lib/terminal/panelRegistry", async () => {
  const actual = await vi.importActual<typeof import("@/lib/terminal/panelRegistry")>("@/lib/terminal/panelRegistry");
  const stub = async () => ({ default: () => <div data-fixture="panel-body" /> });
  const registry = Object.fromEntries(
    Object.entries(actual.PANEL_REGISTRY).map(([type, definition]) => [
      type,
      { ...definition, load: stub } as PanelDefinition,
    ]),
  );
  return {
    PANEL_REGISTRY: registry,
    getPanelDefinition: (type: string) => registry[type],
    listPanelDefinitions: () => Object.values(registry),
  };
});

vi.mock("@/services/watchlist/watchlistService", () => ({ selectWatchlistList: vi.fn() }));
vi.mock("@/services/portfolio/portfolioService", () => ({
  selectPortfolioList: vi.fn(),
  selectHoldingList: vi.fn(),
}));

const REPO_FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

/** 재는 폭 — 모바일(390)과 넓은 화면(1440). */
const NARROW_WIDTH = 390;
const WIDE_WIDTH = 1440;

/**
 * **크롬은 창을 500px 아래로 안 줄인다** — `--window-size=390` 을 줘도 뷰포트가 500 으로 나온다
 * (이 기계의 번들 크로미움 실측: `clientWidth` 500). 그래서 요청한 폭을 그대로 믿지 않고
 * **브라우저가 실제로 준 폭**에 상대적으로 판정한다. 접힘의 경계는 `lg`(1024) 이므로 500 이든
 * 390 이든 「좁은 구간」이라는 사실은 같다 — 다만 그 폭이 정말 좁은 구간인지는 아래에서 다시
 * 확인한다(안 그러면 넓은 폭에서 재고도 초록이 된다).
 */
const LG_BREAKPOINT_PX = 1024;
const XL_BREAKPOINT_PX = 1280;

/** 페이지를 통째로 담을 높이 — 상자가 화면 밖이어도 `getBoundingClientRect()` 는 나오지만,
 *  스크롤 없이 한 번에 보이는 편이 사람이 dump 를 읽기 좋다. */
const WINDOW_HEIGHT = 4000;

/** 셸 레일 폭 — `styles/globals.css` 의 `--shell-rail` 과 같은 46px. */
const RAIL_PX = 46;

/**
 * 접힌 뒤 패널 열이 가져야 하는 최소 폭. 390 - 46 = 344 가 다 오는 것이 정상이고, 여기서는
 * 「캔들을 읽을 수 있는가」의 하한으로 300 을 쓴다 — 88px 과 344px 을 가르는 자리라 값이
 * 경계에 붙어 있지 않다.
 */
const NARROW_PANEL_MIN_PX = 300;

const WATCHLIST_ROWS: WatchlistOut[] = [
  { ticker: "005930", issuer_nm: "삼성전자", market: "KOSPI", use_at: "Y" } as WatchlistOut,
  { ticker: "AAPL", issuer_nm: "Apple Inc.", market: "NASDAQ", use_at: "Y" } as WatchlistOut,
];

interface Boxes {
  viewportWidth: number;
  rowFlexDirection: string;
  aside: { x: number; y: number; w: number; h: number };
  panelColumn: { x: number; y: number; w: number; h: number };
  panels: Array<{ x: number; y: number; w: number; h: number }>;
}

afterEach(cleanup);

/** 실제 `TerminalContainer` 를 jsdom 에 렌더해 HTML 을 뽑는다. */
async function renderTerminalHtml(): Promise<string> {
  vi.mocked(selectWatchlistList).mockResolvedValue({ items: WATCHLIST_ROWS, total_count: WATCHLIST_ROWS.length });
  vi.mocked(selectPortfolioList).mockResolvedValue({ items: [], total_count: 0 });
  vi.mocked(selectHoldingList).mockResolvedValue({ items: [], total_count: 0 });

  const { container } = render(<TerminalContainer />);
  await waitFor(() => expect(container.querySelector("aside")).not.toBeNull());
  await waitFor(() => expect(container.textContent).toContain("005930"));
  return container.innerHTML;
}

/** 셸 골조(레일 46px + `overflow-auto` 인 `<main>`)를 본떠 씌운다. */
function wrapInShell(inner: string): string {
  return `<div class="flex h-screen bg-bg-base text-ink"><div style="width:${RAIL_PX}px;flex-shrink:0"></div><div class="relative flex min-w-0 flex-1"><main class="min-w-0 flex-1 overflow-auto"><div class="h-full">${inner}</div></main></div></div>`;
}

/** 이 레포의 Tailwind 설정으로 픽스처 HTML 에 필요한 CSS 를 실제로 생성한다. */
async function buildCss(html: string): Promise<string> {
  const globalsPath = path.join(REPO_FRONTEND, "styles/globals.css");
  // @import 는 뺀다 — 웹폰트·KaTeX 는 가로 배분과 무관하고, postcss-import 가 없어 그대로 두면
  // 규칙 뒤에 남아 브라우저가 무시한다.
  const source = readFileSync(globalsPath, "utf8")
    .split("\n")
    .filter((line) => !line.trimStart().startsWith("@import"))
    .join("\n");
  const result = await postcss([tailwindcss({ content: [{ raw: html, extension: "html" }], theme } as never)]).process(
    source,
    { from: globalsPath },
  );
  return result.css;
}

function findChrome(): string {
  const candidates = [
    process.env.CHROME_PATH,
    process.env.CHROME_BIN,
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/snap/bin/chromium",
  ].filter((c): c is string => !!c);
  for (const candidate of candidates) if (existsSync(candidate)) return candidate;

  const cache = path.join(process.env.HOME ?? "", ".cache/ms-playwright");
  if (existsSync(cache)) {
    for (const dir of readdirSync(cache)) {
      const exe = path.join(cache, dir, "chrome-linux64/chrome");
      if (existsSync(exe)) return exe;
      const shell = path.join(cache, dir, "chrome-linux/headless_shell");
      if (existsSync(shell)) return shell;
    }
  }
  throw new Error(
    `레이아웃을 잴 크롬을 못 찾았다 — 이 검사는 건너뛰지 않는다. 찾아본 곳: ${candidates.join(", ")}, ${cache}`,
  );
}

const MEASURE_SCRIPT = `
  const box = (el) => { const r = el.getBoundingClientRect();
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }; };
  const aside = document.querySelector('main aside');
  if (!aside) throw new Error('사이드바(aside)를 못 찾았다 — 픽스처가 안 그려졌다');
  const panelColumn = aside.nextElementSibling;
  if (!panelColumn) throw new Error('패널 열(사이드바의 다음 형제)을 못 찾았다');
  const grid = panelColumn.querySelector('[class*="auto-rows"]');
  if (!grid) throw new Error('패널 격자를 못 찾았다');
  const out = {
    viewportWidth: document.documentElement.clientWidth,
    rowFlexDirection: getComputedStyle(aside.parentElement).flexDirection,
    aside: box(aside),
    panelColumn: box(panelColumn),
    panels: [...grid.children].map(box),
  };
  const pre = document.createElement('pre');
  pre.id = 'measured';
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
`;

function measureInChrome(page: string, width: number): Boxes {
  const dir = mkdtempSync(path.join(tmpdir(), "terminal-stack-"));
  const file = path.join(dir, "harness.html");
  writeFileSync(file, page, "utf8");
  let dom: string;
  try {
    dom = execFileSync(
      findChrome(),
      [
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        `--window-size=${width},${WINDOW_HEIGHT}`,
        "--virtual-time-budget=2000",
        "--dump-dom",
        `file://${file}`,
      ],
      { encoding: "utf8", maxBuffer: 64 * 1024 * 1024, stdio: ["ignore", "pipe", "ignore"] },
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
  const marker = /<pre id="measured">([\s\S]*?)<\/pre>/.exec(dom);
  if (!marker) throw new Error(`크롬이 측정 결과를 안 냈다 — dump 앞부분: ${dom.slice(0, 400)}`);
  const decoded = marker[1]
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
  return JSON.parse(decoded) as Boxes;
}

async function measure(width: number): Promise<Boxes> {
  const inner = await renderTerminalHtml();
  const html = wrapInShell(inner);
  const css = await buildCss(html);
  const page = `<!doctype html><html><head><meta charset="utf-8"><style>${css}</style></head><body>${html}<script>${MEASURE_SCRIPT}</script></body></html>`;
  return measureInChrome(page, width);
}

describe("시세 화면 — 좁은 폭에서 사이드바와 패널 열이 세로로 쌓인다 (#425)", () => {
  it(`좁은 폭(${NARROW_WIDTH} 요청): 패널 열이 레일을 뺀 폭을 다 받는다`, async () => {
    const boxes = await measure(NARROW_WIDTH);

    // 픽스처가 통째로 안 그려져도 「위반 없음」으로 초록이 되지 않게 — 잰 것이 있어야 한다.
    expect(boxes.panels.length, "패널 칸을 하나도 못 쟀다 — 픽스처가 안 그려졌다").toBeGreaterThanOrEqual(4);

    // 브라우저가 정말 좁은 구간을 줬는지 먼저 본다 — 안 그러면 넓은 폭에서 재고 초록이 된다.
    expect(
      boxes.viewportWidth,
      `브라우저가 준 폭이 ${boxes.viewportWidth}px 다 — 접힘 경계(${LG_BREAKPOINT_PX}) 아래에서 재야 의미가 있다`,
    ).toBeLessThan(LG_BREAKPOINT_PX);

    expect(
      boxes.panelColumn.w,
      `패널 열이 ${boxes.panelColumn.w}px 다 (뷰포트 ${boxes.viewportWidth}px, 사이드바 ${boxes.aside.w}px) — 차트가 캔들을 못 그린다`,
    ).toBeGreaterThanOrEqual(NARROW_PANEL_MIN_PX);

    // 접혔다면 패널 열이 레일을 뺀 폭을 **다 받는다** — 사이드바와 나눠 갖지 않는다.
    expect(
      boxes.panelColumn.w,
      `패널 열 ${boxes.panelColumn.w}px 가 레일을 뺀 폭(${boxes.viewportWidth - RAIL_PX}px)에 못 미친다 — 아직 사이드바와 가로로 나눠 갖고 있다`,
    ).toBe(boxes.viewportWidth - RAIL_PX);

    // 사이드바도 화면 폭을 다 쓴다 — 누웠는데 폭이 그대로면 목록이 좁은 기둥으로 남는다.
    expect(
      boxes.aside.w,
      `사이드바가 ${boxes.aside.w}px 다 (레일을 뺀 폭 ${boxes.viewportWidth - RAIL_PX}px) — 누운 뒤에도 세로 폭을 그대로 들고 있다`,
    ).toBe(boxes.viewportWidth - RAIL_PX);

    // 쌓였다면 사이드바가 패널 열보다 **위**에 있다.
    expect(
      boxes.aside.y,
      `사이드바 y=${boxes.aside.y}, 패널 열 y=${boxes.panelColumn.y} — 세로로 안 쌓였다`,
    ).toBeLessThan(boxes.panelColumn.y);
  });

  it(`넓은 폭(${WIDE_WIDTH}): 가로 분할 그대로다 (회귀 없음)`, async () => {
    const boxes = await measure(WIDE_WIDTH);

    expect(boxes.panels.length, "패널 칸을 하나도 못 쟀다 — 픽스처가 안 그려졌다").toBeGreaterThanOrEqual(4);
    expect(
      boxes.viewportWidth,
      `브라우저가 준 폭이 ${boxes.viewportWidth}px 다 — 넓은 구간(${XL_BREAKPOINT_PX} 이상)에서 재야 의미가 있다`,
    ).toBeGreaterThanOrEqual(XL_BREAKPOINT_PX);

    expect(boxes.rowFlexDirection, "넓은 폭에서는 가로 분할이어야 한다").toBe("row");
    expect(boxes.aside.y, "넓은 폭에서 사이드바와 패널 열은 같은 줄에 선다").toBe(boxes.panelColumn.y);
    expect(boxes.aside.w, "사이드바는 넓은 폭에서 256px(w-64) 고정이다").toBe(256);
    expect(boxes.panelColumn.x, "패널 열은 사이드바 오른쪽에서 시작한다").toBe(boxes.aside.x + boxes.aside.w);
  });
});
