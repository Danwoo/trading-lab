/** @type {import('tailwindcss').Config['content']} */
export const content = ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"];

/** @type {import('tailwindcss').Config['theme']} */
export const theme = {
  extend: {
    fontFamily: {
      Pretendard: ["Pretendard"],
    },
    colors: {
      // 터미널 패널 시스템 — 값은 styles/globals.css 의 CSS 변수가 SoT (#242 O3 착수 코멘트).
      // 변수는 "R G B" 채널 문자열(예: "230 228 224")로 저장하고 여기서 rgb() + <alpha-value>
      // 로 감싼다 — Tailwind v3 는 순수 var() 문자열엔 opacity modifier(`/40` 등)를 적용하지
      // 못하고 그 유틸리티를 조용히 생략한다(#313). 이 패턴이라야 `bg-bg-panel/60` 같은
      // 조합이 실제 CSS 로 생성된다. 채널을 직접 읽는 소비자는 차트 팩토리 둘이다 —
      // lib/terminal/candleChart.ts · lib/bench/equityChart.ts 의 getComputedStyle 이고, 그
      // 폴백 채널도 같은 형식이어야 한다. marketColorPreset.ts 는 속성만 싣고 값은
      // globals.css 가 소유한다(#73 S1).
      bg: {
        base: "rgb(var(--bg-base) / <alpha-value>)",
        panel: "rgb(var(--bg-panel) / <alpha-value>)",
        raised: "rgb(var(--bg-raised) / <alpha-value>)",
      },
      hairline: "rgb(var(--hairline) / <alpha-value>)",
      line: {
        DEFAULT: "rgb(var(--line) / <alpha-value>)",
        strong: "rgb(var(--line-strong) / <alpha-value>)",
      },
      btn: {
        from: "rgb(var(--btn-from) / <alpha-value>)",
        to: "rgb(var(--btn-to) / <alpha-value>)",
        line: "rgb(var(--btn-line) / <alpha-value>)",
      },
      danger: "rgb(var(--danger) / <alpha-value>)",
      success: "rgb(var(--success) / <alpha-value>)",
      market: {
        up: "rgb(var(--market-up) / <alpha-value>)",
        down: "rgb(var(--market-down) / <alpha-value>)",
      },
      ink: {
        DEFAULT: "rgb(var(--ink) / <alpha-value>)",
        strong: "rgb(var(--ink-strong) / <alpha-value>)",
        muted: "rgb(var(--ink-muted) / <alpha-value>)",
        faint: "rgb(var(--ink-faint) / <alpha-value>)",
      },
    },
    // 타이포 — 크기 대역은 12–13px 로 좁고 위계는 굵기·잉크 명도가 만든다(디자인 시스템 §3).
    // **`xs`·`sm`·`base` 를 여기서 덮지 않는다** — Tailwind 기본값(12/14/16px)을 토큰값
    // (12/12.5/14px)으로 바꾸면 그 유틸리티를 쓰는 기존 화면 55개 파일의 글자가 이 커밋에서
    // 한꺼번에 작아진다. 화면과 함께 옮기는 것이 #73 S2~S5 다. 여기서는 충돌하지 않는
    // 두 이름만 연다.
    fontSize: {
      "2xs": ["var(--text-2xs)", { lineHeight: "var(--text-2xs-lh)" }],
      num: ["var(--text-num)", { lineHeight: "var(--text-num-lh)", letterSpacing: "var(--tracking-num)" }],
    },
    fontWeight: {
      body: "var(--weight-body)",
      ui: "var(--weight-ui)",
      title: "var(--weight-title)",
    },
    letterSpacing: {
      ui: "var(--tracking-ui)",
      num: "var(--tracking-num)",
    },
    lineHeight: {
      prose: "var(--leading-prose)",
      ui: "var(--leading-ui)",
    },
    borderRadius: {
      badge: "var(--radius-badge)",
      control: "var(--radius-control)",
      panel: "var(--radius-panel)",
      full: "var(--radius-full)",
    },
    spacing: {
      "panel-x": "var(--space-panel-x)",
      "panel-top": "var(--space-panel-top)",
      "panel-gap": "var(--space-panel-gap)",
      "icon-gap": "var(--space-icon-gap)",
      group: "var(--space-group)",
      section: "var(--space-section)",
      row: "var(--size-row)",
      // 셸 치수 (§21.6) — `w-shell-*` 로 쓴다. 값은 globals.css 가 SoT.
      "shell-rail": "var(--shell-rail)",
      "shell-panel": "var(--shell-panel)",
      "shell-panel-compact": "var(--shell-panel-compact)",
      "shell-panel-expanded": "var(--shell-panel-expanded)",
      // 누를 수 있는 영역 — 셸 폭과 다른 축(손가락)이다. #230
      "touch-rail-target": "var(--touch-rail-target)",
      "touch-min": "var(--touch-min)",
    },
    minHeight: {
      // 좁은 화면·터치 기기에서 촘촘한 표적이 갖는 하한 (#230). spacing 과 별개 스케일이다.
      "touch-min": "var(--touch-min)",
    },
    boxShadow: {
      e1: "var(--e1)",
    },
    // 오버레이 프리미티브(components/shared/ui/primitives/dialog.tsx) 전용 트랜지션.
    // `tailwindcss-animate` 플러그인 없이 네이티브 keyframes/animation 확장만 쓴다(#341 O8-3
    // — 명세 밖 신규 의존성 금지). `motion-safe:` 변형과 함께 써서 prefers-reduced-motion 사용자는
    // 애니메이션이 아예 적용되지 않는다(Tailwind 내장, 별도 설정 불필요).
    //
    // **여기 transform 에는 scale/opacity 만 넣는다 — 위치(translate/left/top 류) 금지 (#391 B1).**
    // dialog.tsx 는 중앙정렬·드래그 오프셋을 `transform` 이 아니라 별도의 `translate` 프로퍼티에
    // 싣는다(CSS 는 translate/rotate/scale 을 transform 과 독립으로 합성한다). 여기가
    // scale/opacity 만 지키는 한 위치와 애니메이션은 물리적으로 충돌할 수 없다 — 위치를
    // keyframes 로 가져오는 순간 그 분리가 깨진다.
    // #391 B1 이 그 사고였다: `dialog-scale-*` 가 shadcn 원본의 절대중앙정렬 잔재인
    // `translate(-50%, -50%)` 를 물려받고 있어서, 보정 대상이 없는 translate 가 150ms 동안 얹혀
    // 열릴 때마다 자기 크기 절반만큼 어긋난 채 있다가 애니메이션 종료 시 순간 이동했다.
    // 회귀 그물: tests/components/shared/ui/dialogPrimitive.test.tsx 가 이 keyframes 를 전수
    // 검사한다(검사 건수 0건이면 실패).
    keyframes: {
      "dialog-fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
      "dialog-fade-out": { from: { opacity: "1" }, to: { opacity: "0" } },
      "dialog-scale-in": {
        from: { opacity: "0", transform: "scale(0.96)" },
        to: { opacity: "1", transform: "scale(1)" },
      },
      "dialog-scale-out": {
        from: { opacity: "1", transform: "scale(1)" },
        to: { opacity: "0", transform: "scale(0.96)" },
      },
    },
    animation: {
      "dialog-fade-in": "dialog-fade-in 150ms ease-out",
      "dialog-fade-out": "dialog-fade-out 150ms ease-in",
      "dialog-scale-in": "dialog-scale-in 150ms ease-out",
      "dialog-scale-out": "dialog-scale-out 150ms ease-in",
    },
  },
};
export const plugins = [];
