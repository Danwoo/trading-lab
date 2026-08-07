/** @type {import('tailwindcss').Config} */
export const content = ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"];
export const theme = {
  extend: {
    fontFamily: {
      Pretendard: ["Pretendard"],
    },
    colors: {
      // 터미널 패널 시스템 — 값은 styles/globals.css 의 CSS 변수가 SoT (#242 O3 착수 코멘트).
      // 변수는 "R G B" 채널 문자열(예: "217 164 65")로 저장하고 여기서 rgb() + <alpha-value>
      // 로 감싼다 — Tailwind v3 는 순수 var() 문자열엔 opacity modifier(`/40` 등)를 적용하지
      // 못하고 그 유틸리티를 조용히 생략한다(#313). 이 패턴이라야 `bg-signal-warn/10` 같은
      // 조합이 실제 CSS 로 생성된다. 채널을 직접 읽는 다른 소비자(lib/terminal/candleChart.ts
      // 의 getComputedStyle, lib/terminal/marketColorPreset.ts 의 setProperty)도 같은 형식을
      // 맞춰야 한다 — 전수 확인은 #313 커밋 참고.
      slate: {
        void: "rgb(var(--slate-void) / <alpha-value>)",
        panel: "rgb(var(--slate-panel) / <alpha-value>)",
        line: "rgb(var(--slate-line) / <alpha-value>)",
      },
      ink: {
        primary: "rgb(var(--ink-primary) / <alpha-value>)",
        muted: "rgb(var(--ink-muted) / <alpha-value>)",
      },
      signal: {
        warn: "rgb(var(--signal-warn) / <alpha-value>)",
      },
      market: {
        up: "rgb(var(--market-up) / <alpha-value>)",
        down: "rgb(var(--market-down) / <alpha-value>)",
      },
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
