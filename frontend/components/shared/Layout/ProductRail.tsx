"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { usePathname, useRouter } from "next/navigation";
import { showToast } from "@/components/shared/Feedback";
import { Icon } from "@/components/shared/ui/primitives/icons";
import { cn } from "@/components/shared/ui/primitives/cn";
import { RAIL_ITEMS, type RailItem } from "@/constants/shell";

interface Props {
  /** 지금 열려 있는 패널 항목 id. 닫혀 있으면 null */
  openPanelId: string | null;
  /** 패널 항목을 눌렀을 때 — 같은 id 를 다시 누르면 닫는다 */
  onTogglePanel: (id: string) => void;
  /** 패널이 그려지는 영역의 DOM id (`aria-controls`) */
  panelRegionId: string;
  /**
   * 이 항목 버튼으로 포커스를 되돌린다 — 패널이 닫힐 때 호출자가 준다. 사라진 요소에 포커스가
   * 남으면 브라우저가 `<body>` 로 떨어뜨려 키보드 위치를 잃는다.
   */
  focusItemId?: string | null;
  /** 되돌리기를 처리했음을 알린다 — 호출자가 값을 비워야 다음 요청이 다시 걸린다 */
  onFocusHandled?: () => void;
}

/**
 * 46px 아이콘 레일 — 제품 셸의 세로줄 하나 (화면 결정 §20).
 *
 * 항목은 두 갈래다(§20.2 이동 규칙): `route` 는 화면을 바꾸고, `panel` 은 보드를 그대로 둔 채
 * 옆 패널만 여닫는다. **화면이 아직 없는 항목도 지운 대신 남겨 둔다** — 지우면 「원래 없는 것」
 * 으로 읽히는데 실제로는 「아직 안 만든 것」이고, 둘은 다르다(§25.2 ①의 같은 논지).
 * 그래서 누르면 아무 일도 안 일어나는 대신 무엇이 없는지 토스트로 말한다.
 *
 * 접근성: 항목은 전부 실제 `<button>` 이라 Tab 으로 닿고 Enter/Space 로 동작한다.
 * 아이콘만 있으므로 각 버튼에 `aria-label` 로 이름을 준다. 패널 토글은 `aria-expanded` +
 * `aria-controls` 로 패널 영역을 가리키고, 화면 전환 항목은 현재 경로일 때 `aria-current="page"`
 * 를 단다. 아직 없는 자리는 `disabled` 대신 `aria-disabled` 다 — `disabled` 는 포커스를 못 받아
 * 「왜 안 되는지」에 키보드로 도달할 방법이 사라진다.
 */
export function ProductRail({ openPanelId, onTogglePanel, panelRegionId, focusItemId, onFocusHandled }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const buttonRefs = useRef(new Map<string, HTMLButtonElement>());

  useEffect(() => {
    if (!focusItemId) return;
    buttonRefs.current.get(focusItemId)?.focus();
    onFocusHandled?.();
  }, [focusItemId, onFocusHandled]);

  const isRouteActive = (item: RailItem) =>
    !!item.path && (pathname === item.path || pathname.startsWith(item.path + "/"));

  // 이동은 즉시 끝나지 않는다 — 그동안 화면은 이전 자리 그대로다. 누른 버튼이 반응하지 않으면
  // 「눌리긴 한 건가」를 알 수 없다. 전체 화면 로딩 대신 **누른 버튼만** 표시하는 이유는,
  // 빠른 이동에서 화면 전체가 한 번 깜빡이는 것이 더 나쁘기 때문이다.
  const [navigatingTo, setNavigatingTo] = useState<string | null>(null);
  const [, startNavigation] = useTransition();

  useEffect(() => {
    // 도착의 정의는 경로가 바뀐 것이다 — 타이머로 끄면 느린 이동에서 먼저 꺼진다.
    setNavigatingTo(null);
  }, [pathname]);

  const handleClick = (item: RailItem) => {
    if (item.kind === "panel") {
      onTogglePanel(item.id);
      return;
    }
    if (!item.path) {
      showToast(item.pending, "info");
      return;
    }
    // 이미 그 화면이면 아무 데도 안 간다 — 그래도 바쁘다고 켜면 도착 신호(경로 변경)가
    // 영영 안 와서 「계속 로딩 중」이 굳는다. 반응이 없는 것보다 끝나지 않는 반응이 나쁘다.
    if (isRouteActive(item)) return;

    const path = item.path;
    setNavigatingTo(item.id);
    startNavigation(() => router.push(path));
  };

  const renderItem = (item: RailItem) => {
    const isPanel = item.kind === "panel";
    const isOpen = isPanel && openPanelId === item.id;
    const isActive = !isPanel && isRouteActive(item);
    // 두 축을 가른다.
    //
    // `isPending` — **스스로 미완이라 선언했다**(`pending` 문구가 있다). 표식은 이 축이다.
    //   종전 판정은 라우트만 봐서, 패널로 열리지만 안이 빈 넷(에이전트·거래 로그·내 기준·
    //   포트폴리오)을 놓쳤다. 눌러야 「아직 없습니다」가 나오면 몇 번 겪고 레일을 안 누르게 된다.
    // `leadsNowhere` — **눌러도 갈 곳이 없다**(라우트인데 경로가 없어 안내만 띄운다).
    //   `aria-disabled` 는 이 축이다 — 패널은 실제로 열리므로 못 쓴다고 말하면 거짓이다.
    const isPending = Boolean(item.pending);
    const leadsNowhere = !isPanel && !item.path;
    const isNavigating = navigatingTo === item.id;

    return (
      <li key={item.id}>
        <button
          ref={(el) => {
            if (el) buttonRefs.current.set(item.id, el);
            else buttonRefs.current.delete(item.id);
          }}
          type="button"
          aria-label={item.label}
          title={item.pending ? `${item.label} — ${item.pending}` : item.label}
          aria-current={isActive ? "page" : undefined}
          aria-expanded={isPanel ? isOpen : undefined}
          aria-controls={isPanel ? panelRegionId : undefined}
          aria-disabled={leadsNowhere || undefined}
          aria-busy={isNavigating || undefined}
          onClick={() => handleClick(item)}
          className={cn(
            // 테두리 색은 **가지마다 정확히 하나씩** 준다. `border-transparent` 를 기본으로 깔면
            // Tailwind 가 그것을 색 유틸리티 중 마지막에 내보내 뒤에 오는 조건부 색을 전부 덮는다
            // (같은 명시도 → 소스 순서 승). 그렇게 두면 활성·열림 테두리가 코드엔 있고 화면엔 없다.
            "relative flex h-touch-rail-target w-touch-rail-target items-center justify-center rounded-lg border transition-colors",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted",
            isActive && "border-line-strong bg-bg-raised text-ink",
            isOpen && "border-ink-strong bg-bg-raised text-ink-strong",
            !isActive && !isOpen && "border-transparent text-ink-muted hover:bg-bg-raised hover:text-ink",
            isPending && "opacity-60",
            isNavigating && "animate-pulse border-line-strong bg-bg-raised",
          )}
        >
          <Icon name={item.icon} size={18} />
          {isPending && (
            // 흐리기만으로는 「미완」이 안 읽힌다 — 점 하나를 얹어 눌러보기 전에 알게 한다.
            <span aria-hidden className="absolute right-1 top-1 h-1 w-1 rounded-full bg-ink-muted" />
          )}
        </button>
      </li>
    );
  };

  const mainItems = RAIL_ITEMS.filter((item) => !item.footer);
  const footerItems = RAIL_ITEMS.filter((item) => item.footer);

  const renderGroup = (items: readonly RailItem[]) => {
    const rendered: React.ReactNode[] = [];
    items.forEach((item) => {
      rendered.push(renderItem(item));
      if (item.dividerAfter) {
        rendered.push(<li key={`${item.id}-divider`} aria-hidden className="my-1 w-[22px] border-t border-line" />);
      }
    });
    return rendered;
  };

  // 레일은 어느 폭에서도 46px 이다 — 18px 아이콘 한 줄이라 늘려도 담을 것이 없고 줄이면
  // 표적이 무너진다. 그래서 여기만 구간을 안 탄다(값은 globals.css 의 `--shell-rail`).
  //
  // 표적 크기는 폭과 **다른 축**이다 — 손가락으로 누르는 기기에서는 버튼이 44px 로 커진다
  // (`--touch-rail-target`). 그러면 가로로 누운 폰처럼 짧은 화면에서 9개가 안 들어가므로
  // 주 목록만 스크롤시킨다 — 잘라 내면 마지막 항목이 조용히 사라진다.
  return (
    <nav
      aria-label="제품 레일"
      className="flex h-full w-shell-rail flex-none flex-col items-center gap-1 border-r border-line bg-bg-panel py-2"
    >
      <ul className="flex min-h-0 flex-col items-center gap-1 overflow-y-auto">{renderGroup(mainItems)}</ul>
      <ul className="mt-auto flex flex-none flex-col items-center gap-1">{renderGroup(footerItems)}</ul>
    </nav>
  );
}
