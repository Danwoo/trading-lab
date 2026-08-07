// @vitest-environment jsdom
//
// components/shared/ui/primitives/dialog.tsx 와 그 첫 소비자 ui/Popup.tsx 의 회귀 그물.
//
// ## 왜 이 파일이 생겼나
//
// PR #391 리뷰에서 다이얼로그 결함이 세 번 연속 나왔는데(열림 위치 점프 B1, 닫힘 애니메이션
// 사문화 D1, 바깥 클릭 사문화 N1) **셋 다 사람이 브라우저를 켜야만 보이는 자리**에 있었다.
// 단위 테스트 315건은 내내 초록이었다 — 다이얼로그 동작을 보는 테스트가 0건이었기 때문이다.
//
// ## jsdom 이 잡을 수 있는 것 / 없는 것 (정직하게)
//
// jsdom 에는 **레이아웃 엔진도 히트테스트도 CSS 도 없다**. `getBoundingClientRect()` 는 전부 0
// 이고 `elementFromPoint()` 는 없으며 Tailwind 클래스는 아무 계산된 스타일도 만들지 않는다.
// 그래서:
//
// - **잡을 수 있음(동작)**: 바깥 클릭 → 닫힘 배선, `hideOnOutsideClick` 의 boolean·함수 형태
//   veto, ESC, 닫기 버튼, 중첩 시 안쪽만 닫히기. Radix 는 "바깥"을 좌표가 아니라 **React 트리**
//   로 판정하므로 이벤트를 오버레이 노드에 직접 쏘면 실제 경로가 그대로 돈다.
//   호출부 `style` 과 커널의 **경합**(누가 이겼나)도 여기 속한다 — 단, 아래 «거짓 안전 신호»
//   가 보여주듯 **인라인 style 을 DOM 에서 읽는 것은 실브라우저와 결과가 다를 수 있다.**
// - **잡을 수 있음(옛 구현의 지문)**: 아래 세 사고를 만든 **구현 형태** — DOM 구조·인라인
//   스타일·설정값 — 이 다시 들어오는 것. 형태가 전부 구조라 CSS 없이도 검사된다.
// - **못 잡음**: "여백을 클릭하면 무엇이 히트되는가"(N1 의 증상 자체), 실제 픽셀 좌표(B1 의
//   증상 자체), rAF 프레임별 `data-state` 유지(D1 의 증상 자체) — 애니메이션이 아예 안 돈다.
//   이 셋은 실브라우저 검증(PR #391 코멘트의 CDP 측정)이 담당한다.
// - **못 잡음(추가 — 실제로 뚫린 자리)**: **CSS shorthand ↔ longhand 상호작용.** jsdom 의
//   `cssstyle` 은 `inset`/`insetInline`/`insetBlock` 을 shorthand 로 모델링하지 않는다. 실브라우저
//   에서는 `element.style.inset = ""`(= React 가 `style` 값 `undefined` 를 적용하는 방식)이
//   CSSOM `removeProperty` 와 같아 **`top/right/bottom/left` 를 전부 함께 지우는데**(CSSOM
//   §6.7.2), jsdom 에서는 `left`/`top` 이 그대로 남는다. 아래 «거짓 안전 신호» 참고.
//
// ## 거짓 안전 신호였던 단언 (#391, 2026-08-04)
//
// 커널이 `style={{ ...style, left:"50%", top:"50%", inset: undefined, … }}` 였던 시절,
// 이 파일의 `expect(dialog.style.left).toBe("50%")` / `.top).toBe("50%")` 는 **초록이었다.**
// 같은 코드를 실브라우저에서 렌더하면 `left`/`top` 이 아예 없었다 — 호출부 style 과 무관하게
// 모든 다이얼로그가 원점 근처에 그려져 대부분 화면 밖이었다(chrome-headless-shell 1600×900
// 실측: `role=dialog` 의 rect `{x:-32, y:-48.4, w:64, h:96.8}`, style 속성에 left/top 부재).
// **330건 전부 초록은 「안 깨졌다」가 아니라 「jsdom 이 이 상호작용을 못 본다」였다.**
// 그래서 이 축은 DOM 이 아니라 **`resolveDialogContentStyle` 의 반환 객체**로 잠근다(아래
// 「커널 style 해석」 describe) — 그 함수가 값이 `undefined` 인 키를 하나도 내보내지 않으면
// shorthand 를 지울 일 자체가 없다. 렌더 기반 단언은 남겨 두되(경합 자체는 여전히 유효)
// **그 초록을 위치 정확성의 증거로 읽지 마라 — 위치는 실브라우저에서만 확인된다.**
//
// ## 아래 「구조·스타일 소유권」 절이 실제로 하는 일 (과장하지 않기)
//
// 그 절에는 힘이 다른 두 종류가 섞여 있다. 섞인 채로 "구조 불변식을 잠근다"고 뭉뚱그리면
// 안 된다 — 실제로 그렇게 적어 놨다가 뚫렸다.
//
// **(가) 정말 잠기는 것** — 호출부 `style` 대 커널의 경합, keyframes 선언 내용, 레이어가
// Portal 의 직계 자식인지. 셋 다 **결과값·구조를 직접** 읽으므로 CSS 가 없어도 판정이 정확하다.
//
// **(나) 잠기지 않는 것** — 불변식 (1)·N1 의 「Radix 레이어 노드의 박스 == 눈에 보이는
// 다이얼로그 박스」. jsdom 에는 레이아웃 엔진도 계산된 스타일도 없어 이 성질 자체를 볼 수
// 없고, 검사는 옛 코드의 **지문**(표면 클래스 존재·자식 노드 모양)을 대신 본다. 즉 여기서는
// **불변식이 아니라 N1 을 만든 그 구현 형태의 재도입만** 막힌다.
//
// 실제로 뚫렸다 — PR #391 3회차 리뷰가 (나)의 검사를 전부 통과시킨 채로 N1 을 그대로 재현했다.
//
// ### 우회 B 재현 절차 (다음 저자가 속지 않도록)
//
// 1. `primitives/dialog.tsx` 의 Content `cn(...)` 첫 줄 **뒤에 한 줄을 덧붙인다**:
//    `"w-screen h-screen bg-transparent border-transparent shadow-none"`.
//    앞줄의 `bg-white`·`border-gray-200`·`shadow-lg` 는 **지우지 않는다** — 뒤 클래스가 실제
//    화면을 덮어쓰지만 `classList.contains` 는 계산된 스타일이 아니라 클래스 목록만 보므로
//    계속 참이다.
// 2. `npx vitest run tests/components/shared/ui/dialogPrimitive.test.tsx`
//    → 아래 «레이어 크기를 클래스로 잡지 않는다» **하나만** 빨갛고 나머지는 전부 초록이다.
//    특히 바로 위 «role=dialog 노드가 시각적 표면 자신이다» 를 포함한 옛 구조 검사 4개가
//    전부 통과한다 — 그게 이 절의 한계다 (실측 2026-08-04: 1 failed / 18 passed).
//    크기 유틸리티를 `w-[9999px] h-[9999px]` 로 바꿔도 결과는 같다(한때는 15/15 초록이었다).
// 3. 실브라우저에서 다이얼로그를 열고 여백(예: 40,40)을 클릭 → 닫히지 않는다. 레이어가
//    뷰포트 전체를 덮어 Radix 가 모든 클릭을 inside 로 판정한다 = N1 재발
//    (PR #391 3회차 리뷰가 1600×900 뷰포트에서 실측한 결과 — 이 단계는 jsdom 이 못 본다).
//
// 그래서 (1) 검사에 «레이어 크기를 클래스로 잡지 않는다» 를 덧붙여 **그 형태만** 좁혔다.
// 처음엔 그 검사가 `vw/vh/vmin/vmax`·`screen/full/dvw…` 토큰만 봐서 **`w-[9999px] h-[9999px]`
// 로 그냥 통과했다**(리뷰 6변형 공격 중 1건 관통, 15/15 초록). 뷰포트 단위인지가 아니라
// **레이어 크기를 클래스로 잡는지**가 규칙이므로, 지금은 크기 유틸리티(`w-`/`h-`/`size-`
// + `min-`/`max-` 접두)를 **전면 금지**한다 — 정상 경로에서 다이얼로그 크기는 언제나
// `style` prop(Popup 의 width/height)으로 온다.
// **좁힌 뒤에도 못 막는 것** (알고 남긴 구멍이다):
//
// - **인라인 style 로 키우는 형태** (`width: "100vw"` 등). `fullScreen` 이 정확히 그렇게
//   하므로 정상 사용과 구별할 수 없다.
// - **크기가 아닌 속성으로 박스를 부풀리는 형태** (`p-[9999px]` 등 패딩·보더). 히트 영역은
//   border-box 라 같은 결과가 되지만, 정상적인 패딩 사용과 구별할 규칙이 없어 넣지 않았다.
// - **소비자가 `className` 으로 넘기는 크기 클래스.** 이 검사는 이 테스트가 렌더한 것만 본다 —
//   런타임 강제가 아니라 커널·`Popup` 의 고정 클래스 목록에 대한 검사다.
// - **레이어 대신 자식의 히트 영역을 넓히는 형태** (음수 inset 자식 등). 지금 이걸 막는 것은
//   이 그물이 아니라 `Popup.tsx` 가 항상 넘기는 `overflow-hidden` 의 클리핑이다 — 우발적
//   방어이고 검사 항목이 아니다.
// - **표면 클래스를 지우지 않고 뒤에서 덮어쓰는 형태 일반** (`classList.contains` 의 한계).
// - keyframes 검사는 `tailwind.config.mjs` 만 본다 — `globals.css` 에 직접 쓴 `@keyframes`,
//   그리고 `transform: matrix(...)` 형태로 쓴 위치값은 빠져나간다.
//
// **레이어 박스와 시각 박스가 실제로 일치하는지는 실브라우저에서만 확인된다.** (나)가
// 초록인 것은 "N1 이 없다"가 아니라 "N1 을 만든 그 형태가 아니다"라는 뜻이다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";

import { Popup } from "@/components/shared/ui/Popup";
import { Dialog, DialogContent, resolveDialogContentStyle } from "@/components/shared/ui/primitives/dialog";
import { theme } from "@/tailwind.config.mjs";

afterEach(cleanup);

/** Radix 는 pointerdown 문서 리스너를 setTimeout(0) 으로 단다 — 매크로태스크를 한 번 비운다. */
async function flushMacrotasks() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

/** 다이얼로그 박스 = Radix DismissableLayer 의 레이어 노드 = `role="dialog"` */
function getDialog(): HTMLElement {
  return screen.getByRole("dialog");
}

/**
 * 딤 배경(Overlay). Radix Overlay 에는 role 이 없어서 "portal 직계 자식 중 role=dialog 가
 * 아닌 data-state 노드"로 찾는다.
 */
function getOverlay(): HTMLElement {
  const candidates = Array.from(document.body.querySelectorAll<HTMLElement>("[data-state]")).filter(
    (el) => el.getAttribute("role") !== "dialog",
  );
  expect(candidates, "딤 배경(Overlay) 노드를 찾지 못했다").toHaveLength(1);
  return candidates[0];
}

/**
 * 사용자가 딤 배경을 클릭하는 실제 이벤트 시퀀스.
 * Radix Dialog 는 `deferPointerDownOutside: true` 라 pointerdown 만으로는 닫히지 않고
 * 뒤따르는 click 까지 봐야 한다(react-dismissable-layer 소스 확인) — 그래서 전 시퀀스를 쏜다.
 */
async function clickOutside(target: HTMLElement = getOverlay()) {
  await act(async () => {
    fireEvent.pointerDown(target, { button: 0, pointerId: 1, isPrimary: true });
    fireEvent.mouseDown(target, { button: 0 });
    fireEvent.pointerUp(target, { button: 0, pointerId: 1, isPrimary: true });
    fireEvent.mouseUp(target, { button: 0 });
    fireEvent.click(target, { button: 0 });
  });
  await flushMacrotasks();
}

async function openPopup(props: Partial<React.ComponentProps<typeof Popup>> = {}) {
  const onHiding = vi.fn();
  render(
    <Popup visible width={400} height={200} title="테스트 팝업" onHiding={onHiding} {...props}>
      <button type="button">내용 버튼</button>
    </Popup>,
  );
  await flushMacrotasks();
  return { onHiding };
}

describe("dialog primitive — 바깥 클릭 (#391 N1)", () => {
  it("hideOnOutsideClick 미지정(기본 true) — 딤 배경 클릭이 닫는다", async () => {
    const { onHiding } = await openPopup();
    expect(onHiding).not.toHaveBeenCalled();

    await clickOutside();

    expect(onHiding).toHaveBeenCalledTimes(1);
  });

  it("hideOnOutsideClick={false} — 딤 배경을 눌러도 닫히지 않는다 (현 소비자 3개의 계약)", async () => {
    const { onHiding } = await openPopup({ hideOnOutsideClick: false });

    await clickOutside();

    expect(onHiding).not.toHaveBeenCalled();
  });

  it("hideOnOutsideClick 함수 형태 — 반환값대로 닫거나 막고, 원본 이벤트를 받는다", async () => {
    const allow = vi.fn().mockReturnValue(true);
    const { onHiding } = await openPopup({ hideOnOutsideClick: allow });

    await clickOutside();

    expect(allow).toHaveBeenCalledTimes(1);
    // Radix 가 넘기는 CustomEvent — detail.originalEvent 가 실제 pointerdown 이다.
    expect(allow.mock.calls[0][0]?.detail?.originalEvent?.type).toBe("pointerdown");
    expect(onHiding).toHaveBeenCalledTimes(1);
  });

  it("hideOnOutsideClick 함수가 false 를 반환하면 닫히지 않는다", async () => {
    const deny = vi.fn().mockReturnValue(false);
    const { onHiding } = await openPopup({ hideOnOutsideClick: deny });

    await clickOutside();

    expect(deny).toHaveBeenCalledTimes(1);
    expect(onHiding).not.toHaveBeenCalled();
  });

  it("박스 안을 클릭하면 닫히지 않는다", async () => {
    const { onHiding } = await openPopup();

    await clickOutside(screen.getByRole("button", { name: "내용 버튼" }));

    expect(onHiding).not.toHaveBeenCalled();
  });

  it("중첩 — 안쪽 다이얼로그의 딤 배경 클릭은 안쪽만 닫는다", async () => {
    const outerHiding = vi.fn();
    const innerHiding = vi.fn();
    render(
      <>
        <Popup visible title="바깥" onHiding={outerHiding}>
          <span>바깥 내용</span>
        </Popup>
        <Popup visible title="안쪽" onHiding={innerHiding}>
          <span>안쪽 내용</span>
        </Popup>
      </>,
    );
    await flushMacrotasks();

    const overlays = Array.from(document.body.querySelectorAll<HTMLElement>("[data-state]")).filter(
      (el) => el.getAttribute("role") !== "dialog",
    );
    expect(overlays, "중첩이면 오버레이가 2개여야 한다").toHaveLength(2);

    await clickOutside(overlays[overlays.length - 1]);

    expect(innerHiding).toHaveBeenCalledTimes(1);
    expect(outerHiding).not.toHaveBeenCalled();
  });
});

// 힘이 다른 두 종류가 섞여 있다 — 무엇이 정말 잠기고 무엇이 지문뿐인지는 이 파일 헤더의
// 「(가) 정말 잠기는 것 / (나) 잠기지 않는 것」을 보라. 통째로 "불변식을 잠근다"고 읽지 마라.
describe("dialog primitive — 구조·스타일 소유권 (일부만 잠김 — 헤더 (가)/(나) 참고)", () => {
  // (1) N1: 레이어 노드가 시각적 박스 자신이어야 한다.
  // 한때 Content 가 `fixed inset-0 flex items-center justify-center` 로 뷰포트 전체를 덮고
  // 시각적 박스는 그 안의 div 였다 — Radix 가 뷰포트 전체를 "inside" 로 보게 되어 바깥 클릭이
  // 통째로 죽었다. jsdom 은 좌표를 모르므로 "레이어 노드 자신이 표면(배경·테두리·그림자)을
  // 갖고, 그 안에 또 다른 표면 래퍼가 없다"라는 **그 시절 코드의 지문**을 대신 본다.
  const SURFACE_CLASSES = ["bg-white", "border-gray-200", "shadow-lg"];

  /**
   * 레이어 크기를 클래스로 잡는 유틸리티(헤더의 «우회 B»). 정상 경로에서 다이얼로그 크기는
   * 언제나 `style` prop(Popup 의 width/height)으로 오므로, 클래스로 크기를 잡을 일이 **하나도**
   * 없다 — 그래서 뷰포트 단위 토큰만 고르지 않고 크기 유틸리티 전체를 막는다. 한때
   * `vw/vh/vmin/vmax`·`screen/full` 토큰만 봐서 `w-[9999px] h-[9999px]` 가 그대로 통과했다.
   *
   * 토큰 단위로 본다: 변형 접두(`sm:`, `data-[state=open]:`)와 `!important` 표시를 지나
   * 유틸리티 이름 자리에서 매칭한다. 인라인 style 로 키우는 형태는 못 본다 — `fullScreen`
   * 이 정당하게 `100vw/100vh` 를 쓰므로 구별할 수 없다(헤더 「좁힌 뒤에도 못 막는 것」).
   */
  const SIZE_UTILITY_PATTERN = /(^|:)!?(min-|max-)?(w|h|size)-/;

  it("role=dialog 노드가 시각적 표면 자신이다 — 전체 뷰포트 래퍼가 아니다", async () => {
    await openPopup();
    const dialog = getDialog();

    for (const cls of SURFACE_CLASSES) {
      expect(dialog.classList.contains(cls), `레이어 노드에 ${cls} 가 없다 — 표면이 분리됐다`).toBe(true);
    }
    // 뷰포트 전체를 덮는 래퍼의 지문
    expect(dialog.classList.contains("inset-0"), "레이어 노드가 뷰포트를 통째로 덮는다").toBe(false);
    // 안쪽에 또 다른 표면(=예전의 분리된 박스)이 있으면 안 된다
    expect(dialog.querySelector(".bg-white.shadow-lg"), "표면 역할의 중간 노드가 남아 있다").toBeNull();
  });

  it("레이어 크기를 클래스로 잡지 않는다 — 표면 클래스를 남긴 채 키우는 우회 차단", async () => {
    await openPopup();
    const dialog = getDialog();

    const tokens = dialog.className.split(/\s+/).filter(Boolean);
    // fail-closed: 클래스가 사라져(구현 변경) 검사 대상이 0건이면 통과가 아니다.
    expect(tokens.length, "레이어 클래스 토큰이 0건이다 — 검사한 게 없다").toBeGreaterThan(0);

    for (const token of tokens) {
      expect(
        token,
        `레이어 크기를 클래스로 잡았다(${token}) — 표면 클래스가 남아 있어도 실제 히트 영역은 ` +
          `그만큼 커진다(#391 N1 재발, 헤더 «우회 B»). 크기는 style prop 으로만 준다.`,
      ).not.toMatch(SIZE_UTILITY_PATTERN);
    }
    console.log(`[레이어 크기 유틸리티 검사] 클래스 토큰 ${tokens.length}건 검사, 위반 0건`);
  });

  // (3) D1: 애니메이션이 걸린 노드가 Portal 의 직계 자식이어야 Presence 가 닫힘을 재생한다.
  it("애니메이션 노드가 Portal 의 직계 자식이고 닫힘 애니메이션을 갖는다", async () => {
    await openPopup();
    const dialog = getDialog();

    // container 미지정이면 Radix Portal 은 body 로 붙는다(asChild — 중간 div 없음).
    expect(dialog.parentElement, "레이어와 Portal 사이에 중간 노드가 생겼다 — Presence 가 죽는다").toBe(document.body);
    expect(dialog.className).toContain("data-[state=closed]:animate-dialog-scale-out");
    expect(dialog.className).toContain("data-[state=open]:animate-dialog-scale-in");
  });

  // (2) B1: 위치는 인라인 style 의 `translate`, 애니메이션은 클래스의 `transform`.
  // ⚠ 아래 `style.left`/`style.top` 단언은 **위치가 맞다는 증거가 아니다** — jsdom 은 shorthand
  // 를 모델링하지 않아 실브라우저에서 left/top 이 지워진 상태에서도 초록이었다(헤더 «거짓 안전
  // 신호»). 그 축은 아래 「커널 style 해석」 describe 가 본다.
  it("위치는 인라인 style 로만 잡히고 transform 은 비워 둔다", async () => {
    await openPopup();
    const dialog = getDialog();

    expect(dialog.style.position).toBe("fixed");
    expect(dialog.style.left).toBe("50%");
    expect(dialog.style.top).toBe("50%");
    expect(dialog.style.translate).toBe("calc(-50% + 0px) calc(-50% + 0px)");
    // transform 은 keyframes 전용 — 인라인으로 쓰면 애니메이션이 150ms 동안 덮어써 튄다.
    expect(dialog.style.transform).toBe("");
    // 위치를 유틸리티 클래스로 되돌리면 tailwind-merge 없는 이 커널에선 승자를 알 수 없다.
    expect(dialog.className).not.toMatch(/(^|\s)(left-|top-|translate-|inset-)/);
  });

  // (2) B1 계열: 호출부가 위치를 넘겨도 커널이 이겨야 한다. 이건 지문이 아니라 **동작**이라
  // jsdom 에서도 제대로 잡힌다 — 인라인 style 값은 CSS 없이도 관측되기 때문이다.
  it("호출부 style 의 위치 키는 커널을 이기지 못하고 개발 빌드에서 경고된다", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    // 일부러 변수로 넘긴다 — 타입 층(`CallerStyle`)은 객체 리터럴만 막으므로 이 경로가
    // 스프레드 순서·런타임 경고에 실제로 도달한다(primitives/dialog.tsx 헤더 「못 막는 것」).
    const rogueStyle: React.CSSProperties = {
      position: "static",
      left: "0px",
      top: "0px",
      translate: "999px 999px",
      transform: "scale(3)",
      insetInlineStart: "0px",
      width: 400,
    };
    render(
      <Dialog open>
        <DialogContent accessibleTitle="직접 렌더" style={rogueStyle}>
          <span>내용</span>
        </DialogContent>
      </Dialog>,
    );
    await flushMacrotasks();
    const dialog = getDialog();

    expect(dialog.style.position, "호출부 position 이 커널을 이겼다").toBe("fixed");
    expect(dialog.style.left, "호출부 left 가 커널을 이겼다").toBe("50%");
    expect(dialog.style.top, "호출부 top 이 커널을 이겼다").toBe("50%");
    expect(dialog.style.translate, "호출부 translate 가 중앙정렬을 날렸다").toBe("calc(-50% + 0px) calc(-50% + 0px)");
    expect(dialog.style.transform, "호출부 transform 이 keyframes 자리를 침범했다").toBe("");
    expect(dialog.style.insetInlineStart, "호출부 논리 오프셋이 남았다").toBe("");
    // 커널이 소유하지 않는 것은 그대로 통과해야 한다 — 크기는 호출부 몫이다.
    expect(dialog.style.width, "커널 소유가 아닌 width 까지 삼켰다").toBe("400px");

    expect(warn, "조용히 무시됐다 — 개발 빌드 경고가 없다").toHaveBeenCalledTimes(1);
    expect(warn.mock.calls[0][0]).toContain("style.position");
    warn.mockRestore();
  });

  it("드래그 오프셋은 translate 에 합성된다 (transform 오염 금지)", async () => {
    await openPopup();
    const dialog = getDialog();
    const grabber = dialog.querySelector<HTMLElement>('[role="presentation"]');
    expect(grabber, "드래그 그랩 영역이 없다").not.toBeNull();

    await act(async () => {
      fireEvent.pointerDown(grabber!, { clientX: 100, clientY: 100, button: 0 });
      fireEvent.pointerMove(window, { clientX: 130, clientY: 145 });
    });

    expect(dialog.style.translate).toBe("calc(-50% + 30px) calc(-50% + 45px)");
    expect(dialog.style.transform).toBe("");
  });

  it("tailwind dialog keyframes 에 위치값이 없다 (전수 검사, 0건이면 실패)", () => {
    const keyframes: Record<string, Record<string, Record<string, string>>> = theme.extend.keyframes;
    const dialogKeyframes = Object.entries(keyframes).filter(([name]) => name.startsWith("dialog-"));

    // fail-closed: 검사 대상이 사라지면(이름 변경·삭제) 조용히 통과하지 않는다.
    expect(dialogKeyframes.length, "검사한 dialog-* keyframes 가 0건이다").toBeGreaterThan(0);

    let checkedDeclarations = 0;
    for (const [name, steps] of dialogKeyframes) {
      for (const [step, decls] of Object.entries(steps)) {
        for (const [prop, value] of Object.entries(decls)) {
          checkedDeclarations += 1;
          expect(["opacity", "transform"], `${name}/${step}: 예상 밖 속성 ${prop}`).toContain(prop);
          if (prop === "transform") {
            expect(value, `${name}/${step}: keyframes 에 위치값이 들어갔다 (#391 B1)`).not.toMatch(
              /translate|left|top|margin|inset/i,
            );
          }
        }
      }
    }
    expect(checkedDeclarations, "검사한 선언이 0건이다").toBeGreaterThan(0);
    // 무엇을 몇 건 검사했는지 남긴다 (전역 원칙 — 검사 0건은 통과가 아니다).
    console.log(
      `[dialog keyframes 검사] keyframes ${dialogKeyframes.length}건 / 선언 ${checkedDeclarations}건 검사, 위반 0건`,
    );
  });
});

// 이 describe 가 헤더 «거짓 안전 신호» 의 대응이다. 렌더 결과(DOM)가 아니라 커널이 React 에
// 넘기는 **style 객체 자체**를 본다 — jsdom 이 CSS shorthand 를 모델링하지 않아 DOM 으로는
// 실브라우저와 다른 답이 나오지만, 객체는 환경과 무관하게 같다.
describe("dialog primitive — 커널 style 해석 (resolveDialogContentStyle)", () => {
  /**
   * 커널 소유 키 14종. 구현(`KERNEL_OWNED_STYLE_KEYS`)을 import 하지 않고 **다시 적는다** —
   * 그물이 구현과 같은 상수를 보면 둘이 함께 틀려도 초록이다. 목록이 갈리면 아래 검사가
   * 빨개져서 사람이 판정하게 된다.
   */
  const KERNEL_OWNED_KEYS = [
    "position",
    "left",
    "top",
    "right",
    "bottom",
    "inset",
    "insetInline",
    "insetInlineStart",
    "insetInlineEnd",
    "insetBlock",
    "insetBlockStart",
    "insetBlockEnd",
    "translate",
    "transform",
  ] as const;
  /** 커널이 실제로 값을 쓰는 키 — 나머지 10종은 결과에서 **키째로** 빠져야 한다. */
  const KERNEL_VALUED_KEYS = ["position", "left", "top", "translate"] as const;

  /** 호출부가 커널 소유 키를 전부 밀어 넣은 style (타입 층을 통과하는 변수 경로). */
  const rogueStyle = Object.fromEntries(
    KERNEL_OWNED_KEYS.map((key) => [key, key === "position" ? "static" : "0px"]),
  ) as React.CSSProperties;

  it("결과에 값이 undefined 인 키가 하나도 없다 — shorthand 를 빈 값으로 지우면 롱핸드가 함께 죽는다 (#391)", () => {
    // React 는 값이 `undefined` 인 style 키를 `element.style[key] = ""` 로 적용하고, 그 대입은
    // CSSOM `removeProperty` 와 같다. `inset` 계열은 shorthand 라 그 한 줄이 같은 객체의
    // `left`/`top` 까지 지운다(CSSOM §6.7.2) — 실브라우저에서 다이얼로그가 항상 화면 밖이었다.
    // 그래서 "지우는 방식" 자체를 금지한다: 안 쓰는 키는 넣지 않는다.
    const inputs: Array<[string, React.CSSProperties | undefined]> = [
      ["style 없음", undefined],
      ["빈 style", {}],
      ["Popup 경로(빈 값 포함)", { width: 400, height: 200, minWidth: undefined, maxHeight: undefined }],
      ["커널 소유 키 전부", rogueStyle],
      ["inset shorthand 만", { inset: "0px" }],
    ];

    let checked = 0;
    for (const [label, input] of inputs) {
      const resolved = resolveDialogContentStyle(input, { x: 0, y: 0 }) as Record<string, unknown>;
      const emptyKeys = Object.keys(resolved).filter((key) => resolved[key] === undefined || resolved[key] === null);
      expect(emptyKeys, `${label}: 값이 빈 키를 내보냈다 — shorthand 면 롱핸드까지 지운다`).toEqual([]);
      checked += 1;
    }
    // fail-closed: 케이스가 사라지면 조용히 통과하지 않는다.
    expect(checked, "검사한 입력이 0건이다").toBe(inputs.length);
    console.log(`[커널 style 해석 검사] 입력 ${checked}건 검사, 빈 값 키 0건`);
  });

  it("커널 소유 키는 값이 비워지는 게 아니라 결과에서 사라진다 (전수 14종)", () => {
    const resolved = resolveDialogContentStyle(rogueStyle, { x: 0, y: 0 }) as Record<string, unknown>;

    let checked = 0;
    for (const key of KERNEL_OWNED_KEYS) {
      checked += 1;
      if ((KERNEL_VALUED_KEYS as readonly string[]).includes(key)) {
        expect(resolved[key], `커널이 쓰는 ${key} 가 호출부 값에 밀렸다`).not.toBe("0px");
        continue;
      }
      expect(Object.prototype.hasOwnProperty.call(resolved, key), `${key} 가 결과에 남아 있다`).toBe(false);
    }
    expect(checked, "검사한 커널 소유 키가 0건이다").toBe(14);

    expect(resolved.position).toBe("fixed");
    expect(resolved.left).toBe("50%");
    expect(resolved.top).toBe("50%");
    expect(resolved.translate).toBe("calc(-50% + 0px) calc(-50% + 0px)");
    console.log(`[커널 소유 키 검사] 키 ${checked}종 검사, 잔존 0건`);
  });

  it("비소유 키는 그대로 살아남고, 커널 키가 맨 뒤에 선언된다", () => {
    const resolved = resolveDialogContentStyle(
      { width: 320, height: 180, margin: "11px", zIndex: 1234, ...rogueStyle } as React.CSSProperties,
      { x: 30, y: 45 },
    ) as Record<string, unknown>;

    expect(resolved.width).toBe(320);
    expect(resolved.height).toBe(180);
    expect(resolved.margin).toBe("11px");
    expect(resolved.zIndex).toBe(1234);
    expect(resolved.translate).toBe("calc(-50% + 30px) calc(-50% + 45px)");
    // 순서도 계약이다 — 커널이 소유하지 않는 shorthand(`all` 등)를 호출부가 넘겨도 나중에
    // 선언된 커널 값이 이긴다. 필터링만으로는 그게 안 막힌다.
    expect(Object.keys(resolved).slice(-4)).toEqual(["position", "left", "top", "translate"]);
  });

  it("[환경 성질] jsdom 은 inset 을 shorthand 로 취급하지 않는다 — 이 파일이 DOM 으로 위치를 못 보는 이유", () => {
    const probe = document.createElement("div");
    probe.style.left = "50%";
    probe.style.top = "50%";
    probe.style.inset = ""; // React 가 `style: { inset: undefined }` 를 적용하는 방식 그대로
    expect(
      probe.style.left,
      "jsdom 이 shorthand 를 모델링하기 시작했다 — 이 파일 헤더의 «못 잡음»·«거짓 안전 신호» 절을 다시 판정하라",
    ).toBe("50%");
    // 실브라우저였다면 여기서 left/top 이 함께 사라진다(CSSOM §6.7.2, chrome-headless-shell 실측).
  });
});

describe("dialog primitive — 기존 닫기 경로 회귀", () => {
  it("ESC 로 닫힌다", async () => {
    const { onHiding } = await openPopup();

    await act(async () => {
      fireEvent.keyDown(document, { key: "Escape" });
    });

    expect(onHiding).toHaveBeenCalledTimes(1);
  });

  it("닫기 버튼(X)으로 닫히고, onHiding 은 한 번만 불린다", async () => {
    const { onHiding } = await openPopup();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "닫기" }));
    });

    expect(onHiding).toHaveBeenCalledTimes(1);
  });
});
