/**
 * 테스트에서 **폭 구간을 정한다** — jsdom 은 `matchMedia` 를 구현하지 않는다.
 *
 * ## 왜 필요한가
 *
 * jsdom 에서 `window.matchMedia` 는 **아예 없다**(이 레포 설정에서 확인). 그래서 그것을 쓰는
 * 훅은 테스트 환경에서 늘 같은 답을 내고, 「좁은 폭에서 이렇게 된다」를 단언할 방법이 없었다 —
 * 독립 리뷰가 두 차례 그 자리를 지적했고 그때마다 「테스트를 쓸 수 없다」로 남았다(#191).
 *
 * ## 왜 훅을 안 고치나
 *
 * 훅이 `matchMedia` 를 주입받게 만들면 **테스트 편의를 위해 프로덕션 API 가 넓어진다.**
 * 대신 여기서 브라우저가 주는 것과 같은 모양의 `matchMedia` 를 세운다 — 훅은 자기가
 * 테스트 중인지 모른 채 그대로 돈다.
 *
 * ## 쓰는 법
 *
 * ```ts
 * const viewport = installViewport(1280);   // 넓은 폭
 * // …render·단언…
 * viewport.resize(900);                     // 좁혀 본다 — 구독자에게 change 가 간다
 * viewport.restore();                       // afterEach 에서
 * ```
 */

type Listener = (event: { matches: boolean }) => void;

interface FakeMediaQueryList {
  media: string;
  matches: boolean;
  addEventListener: (type: "change", listener: Listener) => void;
  removeEventListener: (type: "change", listener: Listener) => void;
  /** 옛 API — 쓰는 코드가 있을 수 있어 함께 둔다. */
  addListener: (listener: Listener) => void;
  removeListener: (listener: Listener) => void;
  onchange: Listener | null;
  dispatchEvent: () => boolean;
}

export interface Viewport {
  /** 폭을 바꾸고 구독자에게 알린다. */
  resize: (width: number) => void;
  /** 원래 `matchMedia`(대개 없음)로 되돌린다. */
  restore: () => void;
  /** 지금 폭. */
  readonly width: number;
}

/** `(min-width: 1024px)` 류 질의만 푼다 — 이 레포가 쓰는 형태다. */
function evaluate(query: string, width: number): boolean {
  const min = /\(min-width:\s*(\d+)px\)/.exec(query);
  if (min) return width >= Number(min[1]);
  const max = /\(max-width:\s*(\d+)px\)/.exec(query);
  if (max) return width <= Number(max[1]);
  throw new Error(
    `이 테스트 유틸이 풀 수 없는 미디어 질의다: ${query}. ` +
      "min-width·max-width 만 지원한다 — 새 형태를 쓰면 여기도 함께 넓혀라.",
  );
}

export function installViewport(initialWidth: number): Viewport {
  const original = Object.getOwnPropertyDescriptor(window, "matchMedia");
  const lists = new Map<string, { list: FakeMediaQueryList; listeners: Set<Listener> }>();
  let width = initialWidth;

  const make = (query: string): FakeMediaQueryList => {
    const listeners = new Set<Listener>();
    const list: FakeMediaQueryList = {
      media: query,
      matches: evaluate(query, width),
      addEventListener: (_type, listener) => void listeners.add(listener),
      removeEventListener: (_type, listener) => void listeners.delete(listener),
      addListener: (listener) => void listeners.add(listener),
      removeListener: (listener) => void listeners.delete(listener),
      onchange: null,
      dispatchEvent: () => true,
    };
    lists.set(query, { list, listeners });
    return list;
  };

  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (query: string) => lists.get(query)?.list ?? make(query),
  });

  return {
    get width() {
      return width;
    },
    resize(next: number) {
      width = next;
      for (const [query, entry] of lists) {
        const matches = evaluate(query, width);
        if (matches === entry.list.matches) continue;
        entry.list.matches = matches;
        for (const listener of entry.listeners) listener({ matches });
        entry.list.onchange?.({ matches });
      }
    },
    restore() {
      if (original) Object.defineProperty(window, "matchMedia", original);
      else Reflect.deleteProperty(window, "matchMedia");
      lists.clear();
    },
  };
}
