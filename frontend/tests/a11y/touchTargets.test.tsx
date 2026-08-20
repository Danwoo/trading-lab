// @vitest-environment jsdom
//
// 조작부 표적 크기 회귀 그물 — WCAG 2.5.8 (AA, 24×24 CSS px). #289.
//
// ## 왜 브라우저를 띄우나
//
// jsdom 에는 레이아웃이 없다 — `getBoundingClientRect()` 가 전부 0 을 낸다. 그래서 기존
// 컴포넌트 테스트는 "트리에 있다"까지만 증명한다(PortfolioHoldingGrid.test.tsx 의 「검증 경계」).
// 표적 크기는 **패딩·글리프 크기·줄 높이가 CSS 로 합성된 결과**라 클래스 문자열을 세는 정적
// 검사로는 못 잡는다: `p-1` 이 24 를 만드는지 22 를 만드는지는 안쪽 아이콘 크기에 달렸다.
//
// 그래서 이 파일은 ① 실제 컴포넌트를 jsdom 에 렌더해 HTML 을 뽑고 ② 그 HTML 에 대해 이 레포의
// Tailwind 설정으로 CSS 를 실제로 생성해 ③ 헤드리스 크롬에 얹어 `getBoundingClientRect()` 로
// 잰다. 재는 축이 진짜 픽셀이라 클래스 이름이 바뀌어도(리팩터) 판정은 그대로 유효하다.
//
// ## fail-closed
//
// - 크롬을 못 찾으면 실패한다(조용히 건너뛰지 않는다).
// - 잰 조작부가 `MIN_MEASURED` 미만이면 실패한다 — 픽스처가 통째로 안 그려져도 "위반 0건"
//   으로 초록이 되는 것을 막는다.
// - 빠진 것들의 목록을 **그대로 단언**한다 — 2.5.8 예외(본문 문장 속 인라인 링크)와
//   `sr-only`(화면에 없고 접근명만 내주는 상자) 둘 다. 규칙이 느슨해져 진짜 조작부를
//   삼키면 그 자리에서 빨간불이 난다.
//
// ## 이 그물이 증명하지 않는 것
//
// 픽스처에 없는 화면·상태의 조작부. 아이콘 조작부를 새로 만들면 여기에 픽스처를 더해야 한다
// (`ICON_HIT_AREA` 를 쓰면 24 는 자동으로 따라오지만, 그 사실을 재는 것은 이 파일뿐이다).
// 그 「픽스처를 안 더했다」는 `scripts/verify_icon_hit_area.py` 가 짝으로 잡는다 — 소스를 전수로
// 훑어 아이콘 조작부인데 `ICON_HIT_AREA` 를 안 쓰는 자리를 센다(크기는 안 잰다).
// 웹폰트도 안 싣는다 — 글리프 폭이 폰트에 따라 몇 px 달라질 수 있어 경계값(24)에 딱 붙는
// 자리는 실제 화면에서 다시 확인해야 한다.

import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import postcss from "postcss";
import tailwindcss from "tailwindcss";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/react";

import { theme } from "@/tailwind.config.mjs";
import { ProductStages } from "@/components/features/Bench/ProductStages";
import { SessionListPanel } from "@/components/features/ResearchChat/SessionListPanel";
import { PanelFrame } from "@/components/features/Terminal/PanelFrame";
import { DataTablePager } from "@/components/shared/DataTable/DataTablePager";
import { ToastNotification } from "@/components/shared/Feedback/ToastNotification";
import { showToast } from "@/components/shared/Feedback/toastQueue";
import { GlobalTabs } from "@/components/shared/Layout/GlobalTabs";
import { ProductPanel } from "@/components/shared/Layout/ProductPanel";
import { FileUploader } from "@/components/shared/ui/FileUploader";
import { TextBox } from "@/components/shared/ui/TextBox";
import { SelectMenu } from "@/components/shared/ui/primitives/SelectMenu";
import { useTabStore } from "@/stores/shared/tabStore";

// FileUploader 는 `services/common/fileService` → `env.ts` 를 끌고 온다. jsdom 에는 window 가
// 있어 클라이언트 변수만 검증되므로 이 한 줄이면 실제 컴포넌트를 그대로 렌더할 수 있다.
// `vi.hoisted` 인 이유 — 정적 import 가 모듈 본문보다 먼저 평가돼 아래에 적으면 늦는다.
vi.hoisted(() => {
  process.env.NEXT_PUBLIC_FILE_SERVICE_URL ??= "http://localhost:8000";
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  usePathname: () => "/bench",
}));

const REPO_FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

/** 재는 폭 — 모바일(390)과 xl 구간(1440). 구간에 따라 있는 조작부가 다르다. */
const WIDTHS = [390, 1440];

/** 잰 조작부가 이보다 적으면 픽스처가 안 그려진 것이다 — 위반 0건과 구분한다. */
const MIN_MEASURED = 40;

/** 2.5.8 "Inline" 예외로 빠져도 되는 것 — 문장 속 링크뿐이다(폭마다 한 번씩). */
const EXPECTED_EXEMPT = ["ROADMAP.md", "ROADMAP.md"];

/** 화면에서 안 보이고 접근명만 내주는 것(`sr-only`) — 누르는 자리는 그것을 감싼 라벨이다.
 *  빠지는 자리를 **그대로 단언**한다: 이 규칙이 넓어져 진짜 조작부를 삼키면 목록이 달라진다. */
const EXPECTED_SR_ONLY = ["FileUploader(선택 해제) @390", "FileUploader(선택 해제) @1440"];

interface Measured {
  fixture: string;
  tag: string;
  label: string;
  w: number;
  h: number;
  exempt: boolean;
  srOnly: boolean;
}

afterEach(cleanup);

/** 각 픽스처를 jsdom 에 렌더해 실제 HTML 을 뽑는다(포털로 나간 것까지 포함해 body 를 통째로). */
function renderFixtures(): Array<{ name: string; html: string }> {
  const fixtures: Array<{ name: string; node: React.ReactElement }> = [
    {
      name: "SelectMenu(지우기)",
      node: (
        <SelectMenu
          items={[{ id: "KOSPI", label: "KOSPI" }]}
          displayExpr="label"
          valueExpr="id"
          value="KOSPI"
          showClearButton
          onChange={() => {}}
        />
      ),
    },
    {
      // 다중선택은 지금 소비자가 0이지만 태그마다 제거 `×` 가 붙는다 — 「소비자가 없다」와
      // 「표적이 작아도 된다」는 다른 말이라, 그려지는 자리를 여기서 잡아 둔다.
      // 경계: 이 태그 버튼은 트리거 `<button>` **안에** 있다(중첩 버튼). React 는 경고만 하고
      // 그대로 그리지만 브라우저 HTML 파서는 바깥 버튼을 닫아 버리므로, 하네스에서는 트리거
      // 밖으로 밀려난 상태로 잰다. 상자 크기(min-w-6/min-h-6)는 그대로지만 자리는 실제와 다르다.
      name: "SelectMenu(태그 제거)",
      node: (
        <SelectMenu
          items={[
            { id: "KOSPI", label: "KOSPI" },
            { id: "KOSDAQ", label: "KOSDAQ" },
          ]}
          displayExpr="label"
          valueExpr="id"
          multiple
          value={["KOSPI", "KOSDAQ"]}
          onChange={() => {}}
        />
      ),
    },
    {
      // 파일을 고른 직후의 목록 — 줄마다 「선택 해제」 `×` 가 붙는다. 고르기 전에는 목록이
      // 없으므로 렌더 뒤에 실제로 파일을 하나 물린다(아래 `pickFile`).
      name: "FileUploader(선택 해제)",
      node: <FileUploader />,
    },
    {
      name: "TextBox(지우기·비밀번호)",
      node: (
        <div>
          <TextBox value="삼성전자" showClearButton onValueChanged={() => {}} />
          <TextBox mode="password" value="secret" showPasswordToggle onValueChanged={() => {}} />
        </div>
      ),
    },
    {
      // 헤더 줄 안에서 재야 의미가 있다 — 줄 높이·글꼴이 상자 크기에 섞인다. 그래서 `PanelMenu`
      // 를 홀로 두지 않고 실제 자리인 `PanelFrame` 헤더째로 그린다.
      name: "PanelFrame(패널 메뉴 ⋮)",
      node: (
        <PanelFrame
          instance={{ instanceId: "p1", type: "quote", collapsed: false, settings: {} }}
          definition={{
            type: "quote",
            title: "시세",
            capability: "quote" as never,
            needsSymbol: false,
            load: async () => ({ default: () => null }) as never,
          }}
          provenance={null}
          onToggleCollapse={() => {}}
          onClose={() => {}}
        >
          <div />
        </PanelFrame>
      ),
    },
    {
      name: "ProductPanel(머리 버튼)",
      node: (
        <ProductPanel
          item={{ id: "bot", label: "봇", icon: "box", kind: "panel", expandable: true }}
          expanded={false}
          onToggleExpanded={() => {}}
          onClose={() => {}}
          id="panel-fixture"
        />
      ),
    },
    { name: "GlobalTabs(탭 닫기)", node: <GlobalTabs /> },
    { name: "ToastNotification(알림 닫기)", node: <ToastNotification /> },
    {
      name: "SessionListPanel(대화 삭제)",
      node: (
        <SessionListPanel
          sessions={[{ gid: 1, title: "지난 대화", reg_dt: "2026-01-01" } as never]}
          activeGid={1}
          onSelect={() => {}}
          onNew={() => {}}
          onDelete={() => {}}
        />
      ),
    },
    { name: "ProductStages(펼침·인라인 링크)", node: <ProductStages /> },
    {
      name: "DataTablePager(쪽 이동)",
      node: (
        <DataTablePager
          pageIndex={1}
          pageSize={10}
          totalCount={100}
          onPageChange={() => {}}
          onPageSizeChange={() => {}}
        />
      ),
    },
  ];

  return fixtures.map(({ name, node }) => {
    if (name === "GlobalTabs(탭 닫기)") {
      useTabStore.setState({ tabs: [{ id: "t1", title: "메뉴 관리", path: "/admin/menu" }], activeId: "t1" });
    }
    if (name === "ToastNotification(알림 닫기)") showToast("저장했습니다", "success");
    render(node);
    // PanelMenu 의 항목은 열어야 그려진다.
    const trigger = document.querySelector('[aria-label="패널 메뉴"]');
    if (trigger) fireEvent.click(trigger);
    if (name === "FileUploader(선택 해제)") pickFile();
    const html = document.body.innerHTML;
    cleanup();
    return { name, html };
  });
}

/** 파일 목록은 고른 뒤에만 그려진다 — 숨은 `input[type=file]` 에 파일 하나를 물린다. */
function pickFile(): void {
  const input = document.querySelector('input[type="file"]');
  if (!input) throw new Error("FileUploader 픽스처에 파일 입력이 없다");
  fireEvent.change(input, { target: { files: [new File(["x"], "분기보고서.pdf")] } });
  if (!document.querySelector('[aria-label="분기보고서.pdf 선택 해제"]')) {
    throw new Error("파일을 물렸는데 목록이 안 그려졌다 — 픽스처가 죽었다");
  }
}

/** 이 레포의 Tailwind 설정으로 픽스처 HTML 에 필요한 CSS 를 실제로 생성한다. */
async function buildCss(html: string): Promise<string> {
  const globalsPath = path.join(REPO_FRONTEND, "styles/globals.css");
  // @import 는 빼고 넣는다 — 웹폰트·KaTeX 는 표적 크기와 무관하고, postcss-import 가 없어
  // 그대로 두면 규칙 뒤에 남아 브라우저가 무시한다.
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

  // 개발 기계에는 playwright 가 받아 둔 크롬이 있을 수 있다.
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
    `표적 크기를 잴 크롬을 못 찾았다 — 이 검사는 건너뛰지 않는다. 찾아본 곳: ${candidates.join(", ")}, ${cache}`,
  );
}

/** 헤드리스 크롬에 픽스처를 얹고 조작부 상자를 잰다. */
function measureInChrome(page: string, width: number): Measured[] {
  const dir = mkdtempSync(path.join(tmpdir(), "touch-targets-"));
  const file = path.join(dir, "harness.html");
  writeFileSync(file, page, "utf8");
  let dom: string;
  try {
    dom = runChrome(file, width);
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
  return JSON.parse(decoded) as Measured[];
}

function runChrome(file: string, width: number): string {
  return execFileSync(
    findChrome(),
    [
      "--headless",
      "--disable-gpu",
      "--no-sandbox",
      "--hide-scrollbars",
      `--window-size=${width},900`,
      "--virtual-time-budget=2000",
      "--dump-dom",
      `file://${file}`,
    ],
    { encoding: "utf8", maxBuffer: 64 * 1024 * 1024, stdio: ["ignore", "pipe", "ignore"] },
  );
}

const MEASURE_SCRIPT = `
  const SELECTOR = 'button, [role="button"], [role="menuitem"], [role="tab"], a[href], summary,' +
    ' input:not([type=hidden]), select, textarea';
  // WCAG 2.5.8 "Inline" 예외 — 문장(텍스트 흐름) 안에 놓인 표적. 인라인 상자이면서 형제로
  // 글자를 두고 있으면 그 자리다. 줄 높이를 벌리면 문단이 깨지므로 24 를 요구하지 않는다.
  function isInlineException(el) {
    if (getComputedStyle(el).display !== 'inline') return false;
    const parent = el.parentElement;
    if (!parent) return false;
    const own = (el.textContent || '').trim();
    const around = (parent.textContent || '').trim().replace(own, '').trim();
    return around.length > 0;
  }
  // sr-only — 화면에는 없고 접근명만 내주는 상자(파일 입력이 대표적이다). 1×1 로 잘려
  // 있으므로 크기를 요구할 대상이 아니다. 실제로 누르는 자리는 이것을 감싼 라벨이다.
  function isScreenReaderOnly(el) {
    const style = getComputedStyle(el);
    const clip = (style.clip || '').split(' ').join('');
    return style.clipPath === 'inset(50%)' || clip === 'rect(0px,0px,0px,0px)';
  }
  const out = [];
  for (const section of document.querySelectorAll('[data-fixture]')) {
    for (const el of section.querySelectorAll(SELECTOR)) {
      const style = getComputedStyle(el);
      if (style.display === 'none' || style.visibility === 'hidden') continue;
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) continue;
      out.push({
        fixture: section.getAttribute('data-fixture'),
        tag: el.tagName,
        label: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 30),
        w: Math.round(rect.width * 10) / 10,
        h: Math.round(rect.height * 10) / 10,
        exempt: isInlineException(el),
        srOnly: isScreenReaderOnly(el),
      });
    }
  }
  const pre = document.createElement('pre');
  pre.id = 'measured';
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
`;

it("아이콘 조작부의 표적이 24×24 이상이다 (WCAG 2.5.8)", async () => {
  const fixtures = renderFixtures();
  const body = fixtures
    .map(({ name, html }) => `<section data-fixture="${name}" style="margin:8px">${html}</section>`)
    .join("\n");
  const css = await buildCss(body);
  const page = `<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>${css}</style></head>
<body>${body}<script>${MEASURE_SCRIPT}</script></body></html>`;

  // 두 폭에서 잰다 — 손가락으로 누르는 폭(390)과, 거기서는 `display:none` 이라 아예 없는
  // 조작부(ProductPanel 의 620 토글은 xl 이상에만 있다)가 사는 폭(1440).
  const measured = WIDTHS.flatMap((width) =>
    measureInChrome(page, width).map((m) => ({ ...m, fixture: `${m.fixture} @${width}` })),
  );

  // 통과가 "위반 없음"인지 "아무것도 안 봤음"인지 읽는 사람이 구분할 수 있게 남긴다.
  console.log(
    `[2.5.8] 픽스처 ${fixtures.length}개 × 폭 ${WIDTHS.join("·")} 에서 조작부 ${measured.length}개를 쟀다 ` +
      `(인라인 예외 ${measured.filter((m) => m.exempt).length}개 · sr-only ${
        measured.filter((m) => m.srOnly).length
      }개). 가장 작은 다섯:\n` +
      [...measured]
        .filter((m) => !m.exempt && !m.srOnly)
        .sort((a, b) => Math.min(a.w, a.h) - Math.min(b.w, b.h))
        .slice(0, 5)
        .map((m) => `  ${m.w}x${m.h} «${m.label}» — ${m.fixture}`)
        .join("\n"),
  );

  // 픽스처가 안 그려졌는데 "위반 0건"으로 초록이 되는 것을 막는다.
  expect(measured.length, `잰 조작부가 ${measured.length}개뿐이다 — 픽스처가 안 그려졌다`).toBeGreaterThanOrEqual(
    MIN_MEASURED,
  );
  for (const { name } of fixtures) {
    for (const width of WIDTHS) {
      expect(
        measured.some((m) => m.fixture === `${name} @${width}`),
        `픽스처 「${name}」(폭 ${width})에서 잰 조작부가 0개다`,
      ).toBe(true);
    }
  }

  // 예외로 빠지는 것은 문장 속 인라인 링크뿐이어야 한다.
  expect(measured.filter((m) => m.exempt).map((m) => m.label)).toEqual(EXPECTED_EXEMPT);
  expect(measured.filter((m) => m.srOnly).map((m) => m.fixture)).toEqual(EXPECTED_SR_ONLY);

  const violations = measured
    .filter((m) => !m.exempt && !m.srOnly && (m.w < 24 || m.h < 24))
    .map((m) => `${m.w}x${m.h} «${m.label}» ${m.tag} — ${m.fixture}`);
  expect(violations, `24×24 미만인 조작부:\n${violations.join("\n")}`).toEqual([]);
  // Tailwind 컴파일 + 크롬 두 번 기동이라 기본 5초 안에 안 끝난다(전체 스위트 병렬 실행에서 실측).
}, 120_000);
