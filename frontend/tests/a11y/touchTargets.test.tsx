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
//   「조작 대상 아님」(sr-only·aria-hidden) 둘 다. 규칙이 느슨해져 진짜 조작부를 삼키면
//   그 자리에서 빨간불이 난다.
//
// ## 네 축을 잰다 — 크기 · **닿음** · **덮음** · **보이지 않는데 눌림**
//
// 크기가 24 여도 그 좌표를 눌러서 안 열리면 「히트 영역을 고쳤다」는 반만 참이다 (#289 리드 결정
// 2026-08-21 ①). 실제로 이 레포에서 조작부가 자기 조상의 클립 상자 밖으로 밀려나 **크기는 그대로
// 인 채 못 눌리는** 결함이 있었다 — 그래서 크기와 함께 `document.elementFromPoint(중심)` 이 그
// 조작부(또는 그 자손)를 내는지도 잰다.
//
// ## 덮음 — 이 표적이 **남의 글자 자리**를 먹는가
//
// 표적이 커지면 자기 상자 밖으로 자라 옆 조작부를 덮는다. 그때 커진 표적이 히트 테스트를 이기므로
// **크기도 닿음도 초록인 채로** 사용자는 엉뚱한 것을 누른다 — 입력 글자 끝을 눌렀는데 값이 지워지고,
// 목록을 여는 `▾` 를 눌렀는데 선택이 지워진다 (#289 리뷰 2026-08-22, 세 자리에서 실측).
// 그래서 아이콘 표적의 상자가 **다른 조작부의 content box**(글자가 사는 상자)와 겹치는지 잰다.
//
// 세로로 새는 것은 글자 상자만 봐서는 안 잡힌다 — 그래서 **겹쳐 놓인(absolute) 표적은 자기가 얹힌
// 조작부의 상자 안에 있어야 한다**는 축을 따로 잰다. 44 짜리 상자를 높이 34 짜리 입력 위에 얹으면
// 위아래로 5px 씩 새고, 그 띠에는 클립이 없어 이웃 줄 위에 얹힌다 (#289 리뷰).
//
// ## 보이지 않는데 눌림 — 호버가 없는 기기
//
// `opacity: 0` 은 포인터 이벤트를 안 막는다. 호버로만 드러나는 chrome 은 손가락 기기에서 영영
// 안 보이는데 히트 테스트는 그대로 받는다 — 확인 없이 지우는 버튼이 거기 있으면 사고가 난다.
// 아래 `revealHoverOnlyChrome` 은 그 상태를 **지우고** 재므로, 이 축만 **지우기 전 HTML** 로 따로
// 잰다(호버가 없는 갈래에서만).
//
// ## 입력 장치 두 갈래를 각각 잰다
//
// 표적 하한이 마우스 24 · 손가락 44 로 갈린다(`--touch-icon-target`). 헤드리스 크롬은 기본이
// `pointer: none` · `hover: none` 이라 어느 쪽도 아니므로, `--blink-settings` 로 갈래를 명시해
// 두 번 잰다 (`primaryPointerType` 4=fine · 2=coarse, `primaryHoverType` 2=hover · 1=none —
// 실측으로 미디어 쿼리가 실제로 적용되는 것을 확인했다). **hover 도 같이 준다**: 기본 헤드리스는
// `hover: none` 이라 「마우스」 회차가 사실은 마우스가 아니었고, 그러면 호버 갈래로 갈리는 규칙
// (`[@media(hover:none)]:…`)이 두 회차에 똑같이 적용돼 그 축이 통째로 빈다.
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
import { DateBox } from "@/components/shared/ui/DateBox";
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

/** 페이지를 통째로 담을 높이 — 조작부 중심이 화면 밖이면 히트 테스트를 못 한다.
 *  모자라면 「화면 밖」으로 실패하므로 조용히 안 재지지 않는다. */
const WINDOW_HEIGHT = 6000;

/** 입력 장치 갈래. Blink 의 비트값이다 — 포인터 2=coarse · 4=fine, 호버 1=none · 2=hover.
 *  `iconFloor` 는 `ICON_HIT_AREA` 자리의 하한 — `--touch-icon-target` 과 같은 숫자여야 한다.
 *  `hoverless` 인 갈래에서만 「보이지 않는데 눌림」 축을 잰다. */
const POINTERS = [
  { name: "fine", blinkPointerType: 4, blinkHoverType: 2, hoverless: false, iconFloor: 24 },
  { name: "coarse", blinkPointerType: 2, blinkHoverType: 1, hoverless: true, iconFloor: 44 },
] as const;

/** 모든 조작부가 어느 갈래에서도 지켜야 하는 하한 (WCAG 2.5.8 AA). */
const WCAG_FLOOR = 24;

/** `ICON_HIT_AREA` 가 붙은 자리를 알아보는 표식 — 그 클래스가 내는 유틸리티다. */
const ICON_HIT_AREA_MARKER = "min-w-touch-icon";

/** 한 회차(폭×포인터)에 잰 조작부가 이보다 적으면 픽스처가 안 그려진 것이다 — 위반 0건과 구분한다. */
const MIN_MEASURED_PER_RUN = 32;

/** 한 회차의 `ICON_HIT_AREA` 자리가 이보다 적으면 표식이 바뀐 것이다 — 44 검사가 통째로 비는 것을 막는다. */
const MIN_ICON_HIT_AREA_PER_RUN = 15;

/** 아이콘 표적 × 다른 조작부 짝이 한 회차에 이보다 적으면 짝짓기가 죽은 것이다 — 「덮음 0건」과 구분한다. */
const MIN_COVER_PAIRS_PER_RUN = 30;

/** 「얹힌 자리」를 찾아낸 절대 배치 표적이 한 회차에 이보다 적으면 삐져나옴 축이 죽은 것이다. */
const MIN_OVERLAID_TARGETS_PER_RUN = 4;

/** 호버가 없는 갈래에서 「안 보이는데 눌리는」 조작부는 하나도 없어야 한다. 예외를 두려면 여기 적고
 *  왜 안전한지(파괴적이지 않다·다른 경로가 있다)를 함께 남긴다 — 목록이 곧 리뷰 대상이다. */
const EXPECTED_INVISIBLE_HITTABLE: string[] = [];

/** 2.5.8 "Inline" 예외로 빠져도 되는 것 — 문장 속 링크뿐이다(잰 회차마다 한 번씩). */
const EXPECTED_EXEMPT_PER_RUN = ["ROADMAP.md"];

/** 사람이 그 자리를 눌러 쓰는 조작부가 아닌 것 — `sr-only`(접근명만 내주는 파일 입력)와
 *  `aria-hidden`(DateBox 달력 팝업의 앵커). 누르는 자리는 각각 그것을 감싼 라벨과 달력 버튼이다.
 *  빠지는 자리를 **그대로 단언**한다: 이 규칙이 넓어져 진짜 조작부를 삼키면 목록이 달라진다. */
const EXPECTED_NOT_OPERABLE_PER_RUN = ["FileUploader(선택 해제)", "DateBox(달력 열기)"];

interface Measured {
  fixture: string;
  tag: string;
  label: string;
  w: number;
  h: number;
  exempt: boolean;
  notOperable: boolean;
  /** `ICON_HIT_AREA` 가 붙은 자리인가 — 손가락 갈래에서 44 를 요구하는 대상이다. */
  iconHitArea: boolean;
  /** 중심 좌표가 화면 안인가. 아니면 히트 테스트 자체를 못 한 것이라 실패로 센다. */
  inViewport: boolean;
  /** 중심 좌표의 최상단이 이 조작부(또는 그 자손)인가. */
  reachable: boolean;
  /** 못 닿았을 때 그 자리에서 실제로 잡힌 것 — 무엇이 가로챘는지 사람이 바로 읽게. */
  blockedBy: string;
  /** 이 표적이 **글자 자리**를 먹은 다른 조작부들 — 비어 있어야 한다. */
  covers: string[];
  /** 짝지어 본 다른 조작부 수 — 0 이면 덮음 축이 아무것도 안 본 것이다. */
  coverPairs: number;
  /** 겹쳐 놓인(absolute) 표적이 자기가 얹힌 조작부 상자 밖으로 삐져나온 양 — 비어 있어야 한다. */
  spills: string[];
  /** 「얹힌 자리」를 실제로 찾아낸 표적인가 — 이 수가 0 이면 삐져나옴 축이 아무것도 안 본 것이다. */
  overlaid: boolean;
  /** 조상까지 곱한 실효 불투명도. 0 이면 화면에 없다. */
  opacity: number;
}

afterEach(cleanup);

/** 각 픽스처를 jsdom 에 렌더해 실제 HTML 을 뽑는다(포털로 나간 것까지 포함해 body 를 통째로).
 *  `raw` 는 호버 전용 chrome 을 **안 세운** 스냅샷이다 — 「보이지 않는데 눌림」 축이 그것을 쓴다. */
function renderFixtures(): Array<{ name: string; html: string; raw: string }> {
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
      // 달력 열기 버튼은 `TextBox` 의 지우기와 **같은 공용 클래스**(FIELD_ICON_BUTTON_CLASS)를
      // 쓴다 — 그 클래스가 통째로 흔들리면 두 자리가 같이 무너지므로 둘 다 잰다.
      name: "DateBox(달력 열기)",
      node: <DateBox fieldName="from" value="2026-08-20" onValueChanged={() => {}} />,
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
        // 격자 한 줄의 높이(`auto-rows-[minmax(20rem,1fr)]`)를 준다 — 높이 없이 그리면 패널
        // 상자가 머리 한 줄로 줄어, `overflow-hidden` 이 열린 메뉴를 잘라 낸다(하네스가 만든
        // 겹침이지 제품의 것이 아니다).
        <div style={{ height: 320 }}>
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
        </div>
      ),
    },
    {
      // **좁은 패널** — 패널이 좁아지면 머리의 조작 묶음이 패널 상자 밖으로 밀려나는데, 패널
      // 뿌리가 `overflow-hidden` 이라 밀려난 `⋮` 는 크기가 24 인 채로 **못 눌린다**(#289).
      // 크기 축만으로는 안 잡히므로 「닿음」 축이 잡게 이 자리를 따로 그린다. 폭은 실측에서
      // 실제로 나온 값(사이드바가 자리를 다 먹는 폭에서 패널이 72px 까지 간다)에서 왔다.
      name: "PanelFrame(좁은 패널 ⋮)",
      node: (
        <div style={{ width: 96, height: 320 }}>
          <PanelFrame
            instance={{ instanceId: "p2", type: "quote", collapsed: false, settings: {} }}
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
        </div>
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

  // jsdom 에는 `showPicker` 가 없어 DateBox 가 달력 버튼을 **아예 안 그린다** — 그러면 그 자리가
  // 조용히 검사 밖으로 빠진다(픽스처를 더해도 소용없다). 실제 브라우저와 같은 조건으로 세운다.
  if (typeof HTMLInputElement.prototype.showPicker !== "function") {
    (HTMLInputElement.prototype as { showPicker?: () => void }).showPicker = () => {};
  }

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
    if (name === "DateBox(달력 열기)") requireControl("달력에서 고르기");
    // 순서가 중요하다 — `raw` 를 먼저 뜨고 그다음에 호버 상태를 세운다.
    const raw = document.body.innerHTML;
    if (trigger) revealHoverOnlyChrome(trigger);
    const html = document.body.innerHTML;
    cleanup();
    return { name, html, raw };
  });
}

/**
 * 호버·포커스에서만 보이는 chrome 을 스냅샷에 세운다.
 *
 * 패널 머리의 조작 묶음은 `opacity-0 group-hover:opacity-100 group-focus-within:opacity-100` 이다.
 * **메뉴가 열려 있다는 것은 그 줄에 포커스(또는 호버)가 있다는 뜻**인데, `innerHTML` 스냅샷에는
 * 그 상태가 안 실려 정적 하네스에서는 opacity 가 0 으로 남는다. 그러면 `opacity < 1` 이 만드는
 * 쌓임 맥락에 열린 메뉴가 갇혀 패널 본문 아래로 내려간다 — 실제 화면에서는 안 일어나는 일이다
 * (실측: 열린 상태의 그 묶음은 `opacity: 1` 이고 「접기」를 마우스로 누르면 패널이 접힌다).
 * 그래서 그 자리에만 최종 상태를 박아 하네스가 거짓 빨간불을 내지 않게 한다.
 */
function revealHoverOnlyChrome(trigger: Element): void {
  for (let el = trigger.parentElement; el; el = el.parentElement) {
    if (el.classList.contains("opacity-0")) {
      el.classList.remove("opacity-0");
      el.classList.add("opacity-100");
    }
  }
}

/** 그 조작부가 실제로 그려졌는지 — 없으면 픽스처가 죽은 것이다(잰 것이 0개여도 통과하지 않게). */
function requireControl(label: string): void {
  if (!document.querySelector(`[aria-label="${label}"]`)) {
    throw new Error(`픽스처에 「${label}」 조작부가 없다 — 그리는 조건이 바뀌었다`);
  }
}

/** 파일 목록은 고른 뒤에만 그려진다 — 숨은 `input[type=file]` 에 파일 하나를 물린다. */
function pickFile(): void {
  const input = document.querySelector('input[type="file"]');
  if (!input) throw new Error("FileUploader 픽스처에 파일 입력이 없다");
  fireEvent.change(input, { target: { files: [new File(["x"], "분기보고서.pdf")] } });
  requireControl("분기보고서.pdf 선택 해제");
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
function measureInChrome(page: string, width: number, blinkPointerType: number, blinkHoverType: number): Measured[] {
  const dir = mkdtempSync(path.join(tmpdir(), "touch-targets-"));
  const file = path.join(dir, "harness.html");
  writeFileSync(file, page, "utf8");
  let dom: string;
  try {
    dom = runChrome(file, width, blinkPointerType, blinkHoverType);
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

function runChrome(file: string, width: number, blinkPointerType: number, blinkHoverType: number): string {
  return execFileSync(
    findChrome(),
    [
      "--headless",
      "--disable-gpu",
      "--no-sandbox",
      "--hide-scrollbars",
      `--window-size=${width},${WINDOW_HEIGHT}`,
      // 기본 헤드리스는 `pointer: none` · `hover: none` 이라 두 갈래 어느 쪽도 아니다 — 둘 다 명시한다.
      `--blink-settings=primaryPointerType=${blinkPointerType},primaryHoverType=${blinkHoverType}`,
      "--virtual-time-budget=2000",
      "--dump-dom",
      `file://${file}`,
    ],
    { encoding: "utf8", maxBuffer: 64 * 1024 * 1024, stdio: ["ignore", "pipe", "ignore"] },
  );
}

const MEASURE_SCRIPT = `
  // 애니메이션은 **끝난 상태**로 잰다. 토스트는 200ms 페이드인이라 첫 프레임의 opacity 가 0 이고,
  // 그 프레임을 재면 「안 보이는데 눌린다」로 잘못 잡힌다 — 진짜 문제는 가라앉은 뒤에도 0 인 자리다.
  if (document.getAnimations) {
    for (const animation of document.getAnimations()) { try { animation.finish(); } catch (e) {} }
  }
  const ICON_HIT_AREA_MARKER = ${JSON.stringify(ICON_HIT_AREA_MARKER)};
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
  // 사람이 그 자리를 눌러 쓰는 조작부가 아닌 것 — 두 갈래다.
  // ㉠ sr-only: 화면에 없고 접근명만 내준다(파일 입력). 누르는 자리는 감싼 라벨이다.
  // ㉡ aria-hidden: 접근성 트리 밖이다(DateBox 달력 팝업의 앵커 입력). 누르는 자리는 버튼이다.
  function isNotOperable(el) {
    if (el.closest('[aria-hidden="true"]')) return true;
    const style = getComputedStyle(el);
    const clip = (style.clip || '').split(' ').join('');
    return style.clipPath === 'inset(50%)' || clip === 'rect(0px,0px,0px,0px)';
  }
  // 「닿음」 — 표적 중심을 실제로 히트 테스트한다. 크기가 24 여도 조상의 클립 상자 밖으로
  // 밀려나면 그 좌표에서 잡히는 것은 뒤엣것이다(#289). 최상단이 그 조작부 또는 그 자손이면
  // 통과다 — 아이콘 svg 가 위에 있어도 누르면 버튼이 받는다.
  function describeHit(el) {
    if (!el) return 'null';
    const label = el.getAttribute('aria-label');
    const cls = String(el.className || '').split(' ').slice(0, 4).join('.');
    return el.tagName + (label ? '«' + label + '»' : cls ? '.' + cls : '');
  }
  // 글자가 사는 상자 — 테두리·패딩을 뺀 안쪽. 표적이 여기를 먹으면 사람이 노린 글자를 덮은 것이다.
  function contentBox(el) {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    const n = function (v) { return parseFloat(v) || 0; };
    return {
      l: r.left + n(s.borderLeftWidth) + n(s.paddingLeft),
      r: r.right - n(s.borderRightWidth) - n(s.paddingRight),
      t: r.top + n(s.borderTopWidth) + n(s.paddingTop),
      b: r.bottom - n(s.borderBottomWidth) - n(s.paddingBottom),
    };
  }
  // 이 표적이 얹힌 자리 — 절대 배치된 표적이 right-*/top-* 로 좌표를 재는 기준 상자,
  // 곧 offsetParent 다. 기하로 「가장 가까운 상자」를 추측하지 않는다: 추측은 옆에 놓인
  // 칩·배지를 얹힌 자리로 잘못 골라 뜻 없는 빨간불을 냈다. offsetParent 는 브라우저가 실제
  // 배치에 쓴 상자라 추측이 아니고, 「표적이 자기 기준 상자를 넘었다」가 곧 결함의 정의다.
  function findAnchor(target) {
    const host = target.el.offsetParent;
    if (!host || host === document.body || host === document.documentElement) return null;
    return host;
  }
  // 조상까지 곱한 실효 불투명도 — opacity 0 은 히트 테스트를 안 막으므로 크기·닿음으로는 안 보인다.
  function effectiveOpacity(el) {
    let value = 1;
    for (let e = el; e && e !== document.documentElement; e = e.parentElement) {
      const own = parseFloat(getComputedStyle(e).opacity);
      if (!isNaN(own)) value *= own;
      if (value === 0) return 0;
    }
    return value;
  }
  const out = [];
  for (const section of document.querySelectorAll('[data-fixture]')) {
    const entries = [];
    for (const el of section.querySelectorAll(SELECTOR)) {
      const style = getComputedStyle(el);
      if (style.display === 'none' || style.visibility === 'hidden') continue;
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) continue;
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const inViewport = cx >= 0 && cx <= innerWidth && cy >= 0 && cy <= innerHeight;
      // 이 하네스는 픽스처 13개를 한 페이지에 쌓아 놓은 자리라, 다른 픽스처의 고정/절대 배치가
      // 서로를 덮는다 — 그건 하네스가 만든 겹침이지 제품의 결함이 아니다. 그래서 히트 테스트를
      // **그 픽스처 안**으로 좁힌다: 쌓인 순서에서 이 픽스처에 속한 첫 요소가 그 조작부(또는
      // 그 자손)여야 한다. 조상이 먼저 나오면 조작부가 조상의 클립 상자 밖으로 밀려난 것이다.
      const stack = inViewport ? document.elementsFromPoint(cx, cy) : [];
      const hit = stack.find(function (e) { return section.contains(e); }) || null;
      entries.push({
        el: el,
        rect: rect,
        info: {
          fixture: section.getAttribute('data-fixture'),
          tag: el.tagName,
          label: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 30),
          w: Math.round(rect.width * 10) / 10,
          h: Math.round(rect.height * 10) / 10,
          exempt: isInlineException(el),
          notOperable: isNotOperable(el),
          iconHitArea: el.classList.contains(ICON_HIT_AREA_MARKER),
          inViewport: inViewport,
          reachable: !!hit && el.contains(hit),
          blockedBy: describeHit(hit),
          covers: [],
          coverPairs: 0,
          spills: [],
          overlaid: false,
          opacity: Math.round(effectiveOpacity(el) * 1000) / 1000,
        },
      });
    }
    // 덮음 — 아이콘 표적이 **같은 픽스처의 다른 조작부**의 글자 상자를 먹는가.
    // 조상/자손 관계는 뺀다: 탭 안의 닫기처럼 담긴 자리는 겹치는 것이 정상이다.
    for (const a of entries) {
      if (!a.info.iconHitArea) continue;
      for (const b of entries) {
        if (a === b || b.info.exempt || b.info.notOperable) continue;
        if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
        a.info.coverPairs += 1;
        const box = contentBox(b.el);
        const overlapX = Math.min(a.rect.right, box.r) - Math.max(a.rect.left, box.l);
        const overlapY = Math.min(a.rect.bottom, box.b) - Math.max(a.rect.top, box.t);
        if (overlapX > 0.5 && overlapY > 0.5) {
          const name = b.el.getAttribute('aria-label') || (b.el.value || b.el.textContent || '').trim().slice(0, 20)
            || b.el.tagName;
          a.info.covers.push(
            '«' + name + '» 의 글자 자리를 ' + Math.round(overlapX) + 'x' + Math.round(overlapY) + 'px'
          );
        }
      }
    }
    // 삐져나옴 — 겹쳐 놓인(절대 배치) 표적이 자기가 얹힌 기준 상자 밖으로 자라는가.
    // 덮음 축은 글자 상자만 보므로 세로로 새는 띠를 못 잡는다 — 그 띠에는 클립이 없어 이웃 줄
    // 위에 얹힌다 (#289 리뷰: coarse 44 짜리 상자가 높이 34 짜리 입력 위아래로 5px 씩 넘쳤다).
    for (const a of entries) {
      if (!a.info.iconHitArea) continue;
      if (getComputedStyle(a.el).position !== 'absolute') continue;
      const host = findAnchor(a);
      if (!host) continue;
      a.info.overlaid = true;
      const hostRect = host.getBoundingClientRect();
      const name = host.getAttribute('aria-label') || (host.textContent || '').trim().slice(0, 20) || host.tagName;
      const sides = [
        ['위', hostRect.top - a.rect.top],
        ['아래', a.rect.bottom - hostRect.bottom],
        ['왼쪽', hostRect.left - a.rect.left],
        ['오른쪽', a.rect.right - hostRect.right],
      ];
      for (const pair of sides) {
        if (pair[1] > 0.5) a.info.spills.push('«' + name + '» 밖으로 ' + pair[0] + ' ' + Math.round(pair[1]) + 'px');
      }
    }
    for (const entry of entries) out.push(entry.info);
  }
  const pre = document.createElement('pre');
  pre.id = 'measured';
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
`;

it("아이콘 조작부의 표적이 두 입력 장치에서 각각 하한을 넘고, 그 좌표가 실제로 닿는다 (WCAG 2.5.8 · #289)", async () => {
  const fixtures = renderFixtures();
  const wrap = (parts: Array<{ name: string; markup: string }>) =>
    parts
      .map(({ name, markup }) => `<section data-fixture="${name}" style="margin:8px">${markup}</section>`)
      .join("\n");
  const body = wrap(fixtures.map(({ name, html }) => ({ name, markup: html })));
  const rawBody = wrap(fixtures.map(({ name, raw }) => ({ name, markup: raw })));
  // CSS 는 두 HTML 을 다 훑어 만든다 — 한쪽에만 있는 클래스가 빠지면 그쪽 회차가 거짓말을 한다.
  const css = await buildCss(`${body}\n${rawBody}`);
  const shell = (
    inner: string,
  ) => `<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>${css}</style></head>
<body>${inner}<script>${MEASURE_SCRIPT}</script></body></html>`;
  const page = shell(body);
  const rawPage = shell(rawBody);

  // 폭 둘 × 입력 장치 둘. 폭은 손가락으로 누르는 폭(390)과, 거기서는 `display:none` 이라 아예
  // 없는 조작부(ProductPanel 의 620 토글은 xl 이상에만 있다)가 사는 폭(1440).
  const runs = WIDTHS.flatMap((width) => POINTERS.map((pointer) => ({ width, pointer })));
  const measured = runs.flatMap(({ width, pointer }) =>
    measureInChrome(page, width, pointer.blinkPointerType, pointer.blinkHoverType).map((m) => ({
      ...m,
      pointer,
      fixture: `${m.fixture} @${width}/${pointer.name}`,
    })),
  );
  const operable = measured.filter((m) => !m.exempt && !m.notOperable);
  // 호버 전용 chrome 이 픽스처에 실제로 남아 있어야 「보이지 않는데 눌림」 축이 의미가 있다 —
  // 두 스냅샷이 같으면 `revealHoverOnlyChrome` 이 아무것도 안 세운 것이고, raw 회차는 사본이 된다.
  const revealedFixtures = fixtures.filter((f) => f.raw !== f.html).map((f) => f.name);

  // 「보이지 않는데 눌림」은 **호버를 세우기 전** HTML 로, 호버가 없는 갈래에서만 잰다.
  const hoverlessRuns = runs.filter(({ pointer }) => pointer.hoverless);
  const rawMeasured = hoverlessRuns.flatMap(({ width, pointer }) =>
    measureInChrome(rawPage, width, pointer.blinkPointerType, pointer.blinkHoverType).map((m) => ({
      ...m,
      fixture: `${m.fixture} @${width}/${pointer.name}`,
    })),
  );

  // 통과가 "위반 없음"인지 "아무것도 안 봤음"인지 읽는 사람이 구분할 수 있게 남긴다.
  console.log(
    `[2.5.8] 픽스처 ${fixtures.length}개 × 폭 ${WIDTHS.join("·")} × 포인터 ${POINTERS.map((p) => p.name).join(
      "·",
    )} 에서 조작부 ${measured.length}개를 쟀다 ` +
      `(그중 ICON_HIT_AREA ${measured.filter((m) => m.iconHitArea).length}개 · 인라인 예외 ${
        measured.filter((m) => m.exempt).length
      }개 · 조작 대상 아님 ${measured.filter((m) => m.notOperable).length}개). ` +
      `닿음 검사 ${operable.length}건 중 못 닿은 것 ${operable.filter((m) => !m.reachable).length}건. ` +
      `덮음 검사 ${measured.reduce((sum, m) => sum + m.coverPairs, 0)}짝 중 덮은 것 ${
        measured.filter((m) => m.covers.length > 0).length
      }건. 겹쳐 놓인 표적 ${measured.filter((m) => m.overlaid).length}개 중 얹힌 상자 밖으로 삐져나온 것 ${
        measured.filter((m) => m.spills.length > 0).length
      }건. 호버 없는 갈래에서 「안 보이는데 눌리는」 조작부 ${
        rawMeasured.filter((m) => !m.exempt && !m.notOperable && m.opacity === 0 && m.reachable).length
      }건(잰 것 ${rawMeasured.length}개, 호버 전용 chrome 픽스처 ${revealedFixtures.length}개). 가장 작은 다섯:\n` +
      [...operable]
        .sort((a, b) => Math.min(a.w, a.h) - Math.min(b.w, b.h))
        .slice(0, 5)
        .map((m) => `  ${m.w}x${m.h} «${m.label}» — ${m.fixture}`)
        .join("\n"),
  );

  // 픽스처가 안 그려졌는데 "위반 0건"으로 초록이 되는 것을 막는다.
  expect(measured.length, `잰 조작부가 ${measured.length}개뿐이다 — 픽스처가 안 그려졌다`).toBeGreaterThanOrEqual(
    MIN_MEASURED_PER_RUN * runs.length,
  );
  for (const { name } of fixtures) {
    for (const { width, pointer } of runs) {
      expect(
        measured.some((m) => m.fixture === `${name} @${width}/${pointer.name}`),
        `픽스처 「${name}」(폭 ${width}·${pointer.name})에서 잰 조작부가 0개다`,
      ).toBe(true);
    }
  }

  expect(
    revealedFixtures.length,
    "호버 전용 chrome 을 가진 픽스처가 0개다 — 「보이지 않는데 눌림」 축이 잴 것이 없다",
  ).toBeGreaterThanOrEqual(1);
  expect(rawMeasured.length, `호버 없는 회차에서 잰 조작부가 ${rawMeasured.length}개뿐이다`).toBeGreaterThanOrEqual(
    MIN_MEASURED_PER_RUN * hoverlessRuns.length,
  );

  // 표식이 바뀌면 44 검사가 통째로 비어 조용히 초록이 된다 — 건수로 막는다.
  const iconSites = measured.filter((m) => m.iconHitArea);
  expect(
    iconSites.length,
    `ICON_HIT_AREA 자리가 ${iconSites.length}개뿐이다 — 표식(${ICON_HIT_AREA_MARKER})이 바뀌었는지 보라`,
  ).toBeGreaterThanOrEqual(MIN_ICON_HIT_AREA_PER_RUN * runs.length);

  // 예외로 빠지는 것은 문장 속 인라인 링크뿐이어야 한다.
  expect(measured.filter((m) => m.exempt).map((m) => m.label)).toEqual(runs.flatMap(() => EXPECTED_EXEMPT_PER_RUN));
  expect(measured.filter((m) => m.notOperable).map((m) => m.fixture)).toEqual(
    runs.flatMap(({ width, pointer }) =>
      EXPECTED_NOT_OPERABLE_PER_RUN.map((name) => `${name} @${width}/${pointer.name}`),
    ),
  );

  // ① 크기 — 모든 조작부는 어느 갈래에서도 2.5.8 하한을 넘고,
  //    `ICON_HIT_AREA` 자리는 그 갈래의 하한(마우스 24 · 손가락 44)을 넘는다.
  const tooSmall = operable
    .filter((m) => {
      const floor = m.iconHitArea ? m.pointer.iconFloor : WCAG_FLOOR;
      return m.w < floor || m.h < floor;
    })
    .map((m) => {
      const floor = m.iconHitArea ? m.pointer.iconFloor : WCAG_FLOOR;
      return `${m.w}x${m.h} < ${floor} «${m.label}» ${m.tag} — ${m.fixture}`;
    });
  expect(tooSmall, `하한 미만인 조작부:\n${tooSmall.join("\n")}`).toEqual([]);

  // ② 닿음 — 중심 좌표를 히트 테스트해 그 조작부(또는 자손)가 최상단이어야 한다.
  //    화면 밖이면 잰 것이 아니므로 그것도 실패로 센다(WINDOW_HEIGHT 를 올려야 한다는 신호).
  const unreachable = operable
    .filter((m) => !m.reachable)
    .map((m) =>
      m.inViewport
        ? `«${m.label}» ${m.tag} — ${m.fixture}: 그 좌표의 최상단은 ${m.blockedBy} 다`
        : `«${m.label}» ${m.tag} — ${m.fixture}: 중심이 화면 밖이다 (WINDOW_HEIGHT=${WINDOW_HEIGHT})`,
    );
  expect(unreachable, `중심 좌표로 못 닿는 조작부:\n${unreachable.join("\n")}`).toEqual([]);

  // ③ 덮음 — 아이콘 표적이 남의 글자 자리를 먹으면 안 된다. 크기·닿음은 초록인 채로 사람이
  //    엉뚱한 것을 누르게 되는 축이라, 짝을 실제로 몇 개 봤는지도 하한으로 잠근다.
  const coverPairs = measured.reduce((sum, m) => sum + m.coverPairs, 0);
  expect(
    coverPairs,
    `덮음 축이 짝지어 본 것이 ${coverPairs}건뿐이다 — 아이콘 표적이나 픽스처가 사라졌는지 보라`,
  ).toBeGreaterThanOrEqual(MIN_COVER_PAIRS_PER_RUN * runs.length);
  const covering = measured
    .filter((m) => m.covers.length > 0)
    .map((m) => `«${m.label}» ${m.w}x${m.h} — ${m.fixture}: ${m.covers.join(" · ")}`);
  expect(covering, `남의 글자 자리를 덮는 아이콘 표적:\n${covering.join("\n")}`).toEqual([]);

  // ③-2 삐져나옴 — 겹쳐 놓인 표적이 자기가 얹힌 조작부의 상자를 넘으면 안 된다. 넘친 띠에는
  //     클립이 없어 이웃 줄 위에 얹히고, 같은 폼에서 조작부 높이가 갈래마다 어긋난다.
  const overlaidTargets = measured.filter((m) => m.overlaid).length;
  expect(
    overlaidTargets,
    `겹쳐 놓인(absolute) 아이콘 표적을 ${overlaidTargets}개밖에 못 찾았다 — 삐져나옴 축이 빈다`,
  ).toBeGreaterThanOrEqual(MIN_OVERLAID_TARGETS_PER_RUN * runs.length);
  const spilling = measured
    .filter((m) => m.spills.length > 0)
    .map((m) => `«${m.label}» ${m.w}x${m.h} — ${m.fixture}: ${m.spills.join(" · ")}`);
  expect(spilling, `얹힌 조작부 상자 밖으로 자라는 아이콘 표적:\n${spilling.join("\n")}`).toEqual([]);

  // ④ 보이지 않는데 눌림 — 호버가 없는 갈래에서 실효 불투명도가 0 인 채 히트 테스트를 받는 조작부.
  const invisibleButHittable = rawMeasured
    .filter((m) => !m.exempt && !m.notOperable && m.opacity === 0 && m.reachable)
    .map((m) => `«${m.label}» ${m.tag} — ${m.fixture}`);
  expect(
    invisibleButHittable,
    `호버가 없는 기기에서 보이지 않는데 눌리는 조작부:\n${invisibleButHittable.join("\n")}`,
  ).toEqual(EXPECTED_INVISIBLE_HITTABLE);
  // Tailwind 컴파일 + 크롬 네 번 기동이라 기본 5초 안에 안 끝난다(전체 스위트 병렬 실행에서 실측).
}, 240_000);
