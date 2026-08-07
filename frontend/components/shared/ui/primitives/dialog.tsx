// components/shared/ui/primitives/dialog.tsx
//
// shadcn/ui 의 Dialog 소스를 시작점으로 이 레포 Tailwind 관례(border-gray-200/300, `rounded`,
// 별도 디자인 토큰 없음 — CheckBoxGroup.tsx·ExpandableCard.tsx 참고)에 맞춰 다시 쓴 벤더링
// 컴포넌트다(라이선스 고지: 레포 루트 THIRD-PARTY-NOTICES.md §3 "shadcn/ui — primitives/dialog.tsx
// 소스 벤더링, MIT License"). `tailwindcss-animate` 플러그인(비승인 의존성)을 쓰지 않고
// Tailwind 3.4 내장 `motion-safe:`/`motion-reduce:` 변형 + `tailwind.config.mjs` 의 네이티브
// keyframes 확장만으로 트랜지션을 구성한다 — `prefers-reduced-motion` 이 완료 조건에 있기
// 때문(#341 오더).
//
// ## 이 파일이 지키는 불변식 셋 (셋 다 실제 사고에서 나왔다)
//
// **(1) `DialogPrimitive.Content` 노드 = 눈에 보이는 다이얼로그 박스 그 자체 (#391 N1).**
// Radix `DismissableLayer` 는 "바깥 클릭"을 좌표가 아니라 **레이어 노드의 React 트리**로
// 판정한다(react-dismissable-layer 소스 `usePointerDownOutside` — 레이어의
// `onPointerDownCapture` 가 `isPointerInsideReactTreeRef = true` 를 세우면 document 레벨
// pointerdown 핸들러가 그 이벤트를 inside 로 흘린다). 한때 이 파일은 `Content` 에
// `fixed inset-0 flex items-center justify-center p-4` 를 주고 시각적 박스를 그 안의 평범한
// `<div>` 로 분리했었다 — 그 순간 **뷰포트 전체가 레이어**가 되어, 딤 배경처럼 보이는 여백을
// 눌러도 전부 inside 로 판정됐다. `onPointerDownOutside` 는 한 번도 불리지 않았고
// `Popup.hideOnOutsideClick`(기본 true)은 통째로 사문화됐다. ESC·닫기 버튼은 멀쩡해서 조용히
// 죽어 있었다. 그래서 **래퍼를 두지 않는다** — 위치·애니메이션·시각적 박스가 모두 이 한 노드다.
// 여백은 `DialogOverlay`(별도 노드, `pointer-events: auto`)가 받으므로 Radix 가 바깥으로
// 정확히 판정한다. **다이얼로그를 감싸는 중간 노드를 추가하지 마라.**
//
// **(2) 위치는 `translate` 프로퍼티 · 애니메이션은 `transform` (#391 B1).**
// 이 커널은 `tailwind-merge` 를 들이지 않기로 했다(cn.ts 참고). 즉 두 클래스 문자열이 같은 CSS
// 속성을 두고 경합하면 어느 쪽이 이기는지 신뢰할 수 없다(Tailwind 는 클래스 등장 순서가 아니라
// 생성된 스타일시트 순서로 우선순위를 정한다). 그래서 위치(position/left/top/translate)처럼
// 호출부마다 달라지는 값은 유틸리티 클래스로 두지 않고 `style` prop 으로만 제어한다.
// 여기에 더해 **위치를 `transform` 이 아니라 별도의 `translate` 프로퍼티에 싣는다.** 사고
// 사례: `dialog-scale-in/out` keyframes 가 shadcn 원본의 절대중앙정렬 잔재인
// `translate(-50%, -50%)` 를 물려받은 채 남아 있어서, 보정 대상이 없는 translate 가 150ms 동안
// 얹혀 열릴 때마다 자기 크기 절반만큼 어긋난 채 있다가 애니메이션 종료 시 순간 이동했다.
// CSS 에서 `translate`/`rotate`/`scale` 은 `transform` 과 **독립된 프로퍼티**이고 최종 변환은
// `translate → rotate → scale → transform` 순으로 합성된다 — 그래서 keyframes 가
// `transform: scale(...)` 를 아무리 덮어써도 중앙정렬·드래그 오프셋은 건드리지 못한다. 두
// 관심사가 물리적으로 분리돼 있어 B1 계열 사고가 구조적으로 재발할 수 없다.
// **keyframes 에는 여전히 scale/opacity 만 넣어라**(tailwind.config.mjs 주석 참고) — 위치를
// keyframes 로 옮기는 순간 이 분리가 깨진다.
// 이 불변식은 주석이 아니라 코드가 지킨다 — 층 셋(`KERNEL_OWNED_STYLE_KEYS` 근처 참고):
// ① 타입 `CallerStyle` 이 호출부 `style` 에서 위치 키를 지운다(객체 리터럴이면 컴파일 에러),
// ② `resolveDialogContentStyle` 이 커널 소유 키를 호출부 값에서 **빼고**(값을 비우는 게 아니다)
//    커널 값을 맨 뒤에 얹어 인라인 경합에서 이기게 하고,
// ③ 그래도 넘어온 키는 개발 빌드에서 경고한다(조용히 무시되지 않게).
// ②는 사고를 두 번 냈다. 처음엔 커널 값이 `...style` **앞**에 있어서 호출부가 `style.translate`
// 하나만 줘도 중앙정렬이 조용히 날아갔고, 순서를 뒤집으며 "커널이 안 쓰는 키도 `undefined` 로
// 눌러 두자"고 한 것이 **더 나쁜 회귀**를 만들었다: React 는 `undefined` 인 style 키를
// `element.style[key] = ""` 로 적용하는데 그건 CSSOM `removeProperty` 와 같고, `inset` 은
// `top/right/bottom/left` 의 shorthand 라 **같은 객체에서 위에 쓴 `left`/`top` 까지 지웠다**
// (CSSOM §6.7.2). 결과는 호출부와 무관한 상시 오작동 — 모든 다이얼로그가 (0,0) 근처에 렌더돼
// 대부분 화면 밖이었다. **소유 키는 지운다. `undefined` 로 누르지 마라.**
// **여기서도 못 막는 것**: 호출부 클래스의 `!important` 는 인라인 스타일보다 세다
// (`cn()` 은 클래스를 그대로 이어 붙일 뿐이라 걸러지지 않는다). 리터럴이 아닌 `style` 변수는
// ①을 통과한다 — ②·③이 받는다. ③의 경고는 **브라우저 콘솔에만** 뜬다(`"use client"` 컴포넌트라
// 서버 로거 계측을 거치지 않는다) — 개발자가 직접 보는 것 말고 다른 수집 경로는 없다.
//
// **(3) 애니메이션이 걸린 노드는 `DialogPortal` 의 직계 자식이어야 한다 (#391 D1).**
// Radix `DialogPortal` 은 **자신의 직계 자식마다** 개별로 `Presence` 를 씌워(react-dialog 소스
// `DialogPortal` 구현 확인) 그 자식 노드 자체에 진행 중인 CSS 애니메이션이 있는지로 unmount
// 시점을 늦춘다. 예전 구현은 `DialogPortal` 의 자식으로 애니메이션이 없는 순수 `<div>`
// centering wrapper 를 두고 실제 애니메이션은 그 안의 `Content`(Portal 의 손자)에 걸었다 —
// `Presence` 는 wrapper 자신의 computed style 만 보므로 애니메이션이 하나도 없다고 판단해
// `data-state="closed"` 가 관측되기도 전에 즉시 unmount 했다(닫힘 애니메이션이 실행될 기회
// 자체가 없는 죽은 코드, Overlay 만 별도로 fade-out 됨). 불변식 (1) 과 같은 결론이다 —
// **중간 노드를 두지 않으면 셋 다 자동으로 지켜진다.** 뒤이어 만들 `popover.tsx` 도 같은
// 이유로 이 세 불변식을 기본값으로 삼는다.
//
// 이 셋은 전부 **브라우저를 켜야만 보이는** 결함이었다(단위 테스트는 초록이었다).
// `tests/components/shared/ui/dialogPrimitive.test.tsx` 에 회귀 그물이 있지만 **그 그물은 위
// 불변식을 잠그지 못한다** — jsdom 에는 레이아웃도 계산된 스타일도 없어서, 세 사고를 만든
// 구현 형태의 지문(클래스 이름·자식 노드 모양·인라인 style 값)만 본다. 표면 클래스를 남긴 채
// 레이어만 뷰포트 크기로 키우면 그 검사를 전부 통과하면서 N1 이 그대로 재발한다(실증됨 —
// 그 파일 상단의 «우회 B 재현 절차»). **이 파일의 구조를 바꾸기 전에 그 상단을 먼저 읽고,
// 초록을 안전 신호로 읽지 마라 — 레이어 박스와 시각 박스의 일치는 실브라우저에서만 확인된다.**
// 인라인 style 도 안전지대가 아니다: jsdom 의 `cssstyle` 은 `inset` 을 shorthand 로 취급하지
// 않아 `style.inset=""` 이 `left`/`top` 을 안 지운다 — 그래서 `dialog.style.left` 가 `"50%"`
// 라는 단언이 실브라우저에서 거짓인 채로 초록이었다(위 ② 사고). 그 축은 렌더 결과가 아니라
// `resolveDialogContentStyle` 의 반환 객체로 잠근다.
//
// **주의 — 이 primitive 를 고쳐도 닫힘 애니메이션이 안 보이는 소비자가 있다면 primitive 문제가
// 아닐 수 있다**: 소비자가 `visible=false` 로 넘기지 않고 자기 쪽에서 조건부로 `<Popup>` 자체를
// 언마운트하면(`if (!x) return null` 류) React 가 Presence 보다 먼저 트리를 뽑아버려 여기서
// 아무리 애니메이션을 잘 걸어도 재생될 기회가 없다. `MessagePopup.tsx` 가 정확히 그 패턴이었고
// (#394), 마지막 메시지를 로컬에 캐시해 `Popup` 을 상시 마운트하고 `visible` 만 토글하도록
// 고쳤다 — 그 파일 헤더 주석 참고. **소비자는 항상 `visible` 토글만으로 열고 닫아야 한다**
// (`FormModal`/`SelectGridPanel`/`MessagePopup` 처럼). 이 파일에서는 막을 수 없는 클래스다.
//
// **오버레이/모달 프리미티브의 커널이다.** `ui/Popup.tsx` 가 첫 소비자이고, 뒤이어 이관할
// `Lookup`·`DropDownBox`·`Autocomplete`·`Calendar`·`ColorBox` 는 이 파일이 아니라 Radix
// `Popover`(비-모달, 트리거에 앵커링) 기반 별도 프리미티브가 필요하다 — Dialog 는 모달 전용.
"use client";

import * as React from "react";
import { Dialog as DialogPrimitive } from "radix-ui";
import { cn } from "./cn";

const Dialog = DialogPrimitive.Root;
const DialogPortal = DialogPrimitive.Portal;

interface DialogOverlayProps extends React.ComponentProps<typeof DialogPrimitive.Overlay> {
  /** DevExtreme `shadingColor` 대응 — 지정 시 기본 bg-black/50 대신 이 색을 쓴다 */
  shadingColor?: string;
  /** DevExtreme `shading=false` 대응 — 배경을 투명하게(모달성 자체는 유지, 실사용 0건 확인) */
  transparent?: boolean;
}

function DialogOverlay({ className, style, shadingColor, transparent, ...props }: DialogOverlayProps) {
  return (
    <DialogPrimitive.Overlay
      className={cn(
        "fixed inset-0 z-50",
        !shadingColor && !transparent && "bg-black/50",
        "motion-safe:data-[state=open]:animate-dialog-fade-in",
        "motion-safe:data-[state=closed]:animate-dialog-fade-out",
        className,
      )}
      style={{ ...(shadingColor ? { backgroundColor: shadingColor } : undefined), ...style }}
      {...props}
    />
  );
}

/**
 * 커널이 소유하는 스타일 프로퍼티 — 호출부 `style` 은 이 키를 못 쓴다(불변식 (2)).
 *
 * 경계는 **박스를 어디에 놓는가**다: 위치 오프셋(inset 계열 물리·논리 shorthand·longhand
 * 전부)과 변환 두 프로퍼티. 커널이 실제로 값을 쓰는 것은 `position/left/top/translate` 넷이고,
 * 나머지는 커널도 호출부도 안 쓴다 — 그 키들은 최종 style 에서 **지워진다**(값을 비우는 게
 * 아니다, 아래 `resolveDialogContentStyle` 주석). `transform` 은 keyframes 전용이라 인라인이
 * 비어 있어야 한다.
 * 크기·여백(width/height/margin 등)은 호출부 몫이라 여기 없다 — `Popup` 의 width/height 가
 * 그 경로다. 다이얼로그를 옮기려면 `offset` prop 을 쓴다.
 */
const KERNEL_OWNED_STYLE_KEYS = [
  "position",
  "left",
  "top",
  "right",
  "bottom",
  // `inset` 은 `top/right/bottom/left` 의 shorthand, `insetInline`/`insetBlock` 은 각각
  // start/end 의 논리 shorthand 다. 셋 다 커널의 `left`/`top` 과 같은 자리를 가리키므로
  // 호출부에서 받지 않는다 — 값을 지워서 무력화하는 게 아니라 **키째로 뺀다**(아래 주석).
  "inset",
  "insetInline",
  "insetInlineStart",
  "insetInlineEnd",
  "insetBlock",
  "insetBlockStart",
  "insetBlockEnd",
  "translate",
  "transform",
] as const satisfies readonly (keyof React.CSSProperties)[];

type KernelOwnedStyleKey = (typeof KERNEL_OWNED_STYLE_KEYS)[number];

/**
 * 호출부가 쓸 수 있는 `style`. 커널 소유 키를 빼 두면 **객체 리터럴로 넘길 때 컴파일 에러**가
 * 난다(TS 초과 프로퍼티 검사). 소비자 3개가 전부 `Popup` 을 거쳐 리터럴을 넘기므로 실제 경로를
 * 덮는다. 리터럴이 아닌 값(변수·스프레드)은 구조적 타이핑이라 이 층을 통과한다 — 그 경로는
 * 아래 런타임 경고 + 스프레드 순서가 받는다.
 */
type CallerStyle = Omit<React.CSSProperties, KernelOwnedStyleKey>;

/** 호출부가 커널 소유 키를 넘겼는지 — 조용히 무시되면 원인을 못 찾으니 개발 빌드에서 알린다. */
function findKernelOwnedKeys(style: CallerStyle | undefined): string[] {
  if (!style) return [];
  // 타입에서 지운 키를 런타임에 되짚는 자리라 넓은 타입으로 되돌려 읽는다.
  const widened = style as React.CSSProperties;
  return KERNEL_OWNED_STYLE_KEYS.filter((key) => widened[key] !== undefined);
}

const KERNEL_OWNED_STYLE_KEY_SET: ReadonlySet<string> = new Set<string>(KERNEL_OWNED_STYLE_KEYS);

/**
 * 최종 인라인 style — 호출부 값에서 커널 소유 키를 **지우고**, 커널 값을 **맨 뒤에** 얹는다.
 *
 * ### 왜 `undefined` 로 덮지 않고 지우는가 (#391 — 실브라우저에서 다이얼로그가 항상 화면 밖)
 *
 * 한때 이 자리는 `{...style, left:"50%", top:"50%", inset: undefined, …}` 였다. React 는 값이
 * `undefined` 인 style 키를 `element.style[key] = ""` 로 적용하는데, 빈 문자열 대입은 CSSOM 의
 * `removeProperty` 와 같고 **shorthand 를 지우면 그 롱핸드가 전부 선언 블록에서 제거된다**
 * (CSSOM §6.7.2). `inset` 은 `top/right/bottom/left` 의 shorthand 라서 `inset: undefined` 한
 * 줄이 **바로 위에서 세운 `left`/`top` 을 같이 날렸다** — 호출부 style 이 없는 기본 케이스에서
 * 다이얼로그가 (0,0) 근처에 그려져 대부분 화면 밖이었다(1600×900 실측: rect x=-32 y=-48.4).
 * 호출부가 마침 `inset` 을 넘긴 경우에만 우연히 멀쩡했다 — 그때는 키 삽입 순서가 `...style`
 * 자리에 고정돼 `left`/`top` **앞**에서 지워졌기 때문이다.
 * 지워서 넘기면 shorthand 를 건드릴 일 자체가 없다 — 이 함수는 **값이 `undefined` 인 키를
 * 하나도 내보내지 않는다**(회귀 그물이 그 성질을 직접 단언한다).
 *
 * 그래도 커널 값을 뒤에 두는 이유: 커널이 소유하지 않는 shorthand(예: `all`)를 호출부가 넘길 수
 * 있는데, 나중에 선언된 쪽이 이긴다. 필터링과 순서는 서로를 대신하지 못한다.
 *
 * 테스트에서 쓰려고 export 한다 — jsdom 의 `cssstyle` 은 `inset` 을 shorthand 로 취급하지 않아
 * 이 축을 **렌더 결과로는 관측할 수 없다**(dialogPrimitive.test.tsx 헤더 참고). 그래서 그물은
 * DOM 이 아니라 이 함수의 반환 객체를 본다.
 */
export function resolveDialogContentStyle(
  style: CallerStyle | undefined,
  offset: { x: number; y: number } | undefined,
): React.CSSProperties {
  const resolved: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(style ?? {})) {
    if (KERNEL_OWNED_STYLE_KEY_SET.has(key)) continue;
    // 호출부가 `{ minWidth: undefined }` 처럼 빈 값을 넘기는 것은 정상이다(Popup 이 그렇게
    // 넘긴다). 그 키도 빼서 내보낸다 — 안 넘긴 것과 결과가 같고, `undefined` 를 통과시키면
    // 위 shorthand 함정이 호출부 경로로 되돌아온다.
    if (value === undefined || value === null) continue;
    resolved[key] = value;
  }
  resolved.position = "fixed";
  resolved.left = "50%";
  resolved.top = "50%";
  resolved.translate = `calc(-50% + ${offset?.x ?? 0}px) calc(-50% + ${offset?.y ?? 0}px)`;
  return resolved as React.CSSProperties;
}

interface DialogContentProps extends Omit<React.ComponentProps<typeof DialogPrimitive.Content>, "style"> {
  /** 커널 소유 위치 프로퍼티를 뺀 `style` — 위 `CallerStyle` 주석 참고 */
  style?: CallerStyle;
  /** 접근 가능한 이름 — 화면에 보이는 제목이 없을 때도 스크린리더용으로 필요하다(Radix 요구사항) */
  accessibleTitle: string;
  /** 제목을 시각적으로도 보여줄지 (false 면 sr-only) */
  showVisibleTitle?: boolean;
  visibleTitle?: React.ReactNode;
  container?: React.ComponentProps<typeof DialogPrimitive.Portal>["container"];
  showCloseButton?: boolean;
  shadingColor?: string;
  transparentOverlay?: boolean;
  /** 뷰포트 중앙에서의 오프셋(px) — 드래그 이동용. 중앙정렬과 **같은 `translate` 프로퍼티에**
   * 합성한다(위 불변식 (2)): 호출부가 `style.transform` 으로 직접 옮기면 열림/닫힘 애니메이션의
   * keyframes 가 그 transform 을 150ms 동안 덮어써 드래그한 다이얼로그가 닫힐 때 중앙으로
   * 튄다. 위치는 언제나 `translate`, 애니메이션은 언제나 `transform`. */
  offset?: { x: number; y: number };
}

function DialogContent({
  className,
  style,
  children,
  accessibleTitle,
  showVisibleTitle = false,
  visibleTitle,
  container,
  showCloseButton = true,
  shadingColor,
  transparentOverlay,
  offset,
  ...props
}: DialogContentProps) {
  if (process.env.NODE_ENV !== "production") {
    const ignored = findKernelOwnedKeys(style);
    if (ignored.length > 0) {
      console.warn(
        `[DialogContent] style.${ignored.join(" / style.")} 은(는) 무시된다 — 위치는 커널이 소유한다` +
          ` (primitives/dialog.tsx 불변식 (2)). 다이얼로그를 옮기려면 offset prop 을 써라.`,
      );
    }
  }
  return (
    <DialogPortal container={container}>
      <DialogOverlay shadingColor={shadingColor} transparent={transparentOverlay} />
      {/* Portal 의 직계 자식이자 Radix DismissableLayer 의 레이어 노드이자 눈에 보이는 박스 —
          셋이 전부 이 한 노드다(위 파일 헤더의 불변식 1·2·3). 중간 래퍼를 끼우지 마라. */}
      <DialogPrimitive.Content
        aria-describedby={undefined}
        {...props}
        className={cn(
          "z-50 flex flex-col rounded border border-gray-200 bg-white shadow-lg",
          "motion-safe:data-[state=open]:animate-dialog-scale-in",
          "motion-safe:data-[state=closed]:animate-dialog-scale-out",
          "focus:outline-none",
          className,
        )}
        // 커널 소유 키는 호출부 style 에서 **지우고**, 커널 값을 뒤에 얹는다 — 두 규칙 다
        // 강제 수단이다(`resolveDialogContentStyle` 주석). 지우는 대신 `undefined` 로 덮는
        // 형태로 되돌리지 마라: `inset` 은 shorthand 라서 빈 값 대입이 `left`/`top` 까지
        // 지웠다(#391 — 다이얼로그가 항상 화면 밖).
        style={resolveDialogContentStyle(style, offset)}
      >
        <DialogPrimitive.Title
          className={showVisibleTitle ? "shrink-0 border-b border-gray-200 px-4 py-3 text-sm font-semibold" : "sr-only"}
        >
          {visibleTitle ?? accessibleTitle}
        </DialogPrimitive.Title>
        {children}
        {showCloseButton && (
          // onClick 을 따로 안 건다 — Close 는 클릭 시 Radix 가 내부적으로 이미
          // `Root.onOpenChange(false)` 를 호출한다(react-dialog 소스 확인). 여기 onClick 을
          // 추가하면 Popup.tsx 의 onHiding 이 두 번(이 onClick + Root.onOpenChange) 불린다
          // — 실제로 그렇게 만들었다가 잡은 결함(#341 오더).
          <DialogPrimitive.Close
            aria-label="닫기"
            className={cn(
              "absolute right-3 top-3 rounded p-1 text-gray-400",
              "hover:bg-gray-100 hover:text-gray-600",
              "focus:outline-none focus:ring-2 focus:ring-blue-500/40",
            )}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M3 3L13 13M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Content>
    </DialogPortal>
  );
}

export { Dialog, DialogPortal, DialogOverlay, DialogContent };
