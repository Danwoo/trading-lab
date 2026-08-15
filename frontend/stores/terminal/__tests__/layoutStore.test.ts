import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * vitest 환경은 jsdom 이 아니라 node(O0 결정)라 `localStorage` 가 없다 — 진짜 `Storage`
 * 계약을 구현한 메모리 스토리지로 대신한다. `vi.resetModules()` + 동적 import 로 매 테스트
 * "새로고침"(모듈 재평가 = 새 스토어 인스턴스)을 시뮬레이션한다. 싱글턴 모듈을 그대로 재사용하면
 * 인메모리 상태가 남아 있어 "새로고침해도 유지"를 증명하지 못한다(껐다 켜도 원래 안 꺼졌던 것).
 */
class MemoryStorage implements Storage {
  private store = new Map<string, string>();

  get length() {
    return this.store.size;
  }

  clear(): void {
    this.store.clear();
  }

  getItem(key: string): string | null {
    return this.store.has(key) ? (this.store.get(key) ?? null) : null;
  }

  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null;
  }

  removeItem(key: string): void {
    this.store.delete(key);
  }

  setItem(key: string, value: string): void {
    this.store.set(key, value);
  }
}

let sharedStorage: MemoryStorage;

beforeEach(() => {
  vi.resetModules();
  // 실제 브라우저의 localStorage 는 탭·새로고침을 넘어 살아남는다 — 인스턴스를 테스트 스코프에서
  // 공유해 "모듈은 새로 평가되지만 저장소는 그대로"인 진짜 새로고침을 재현한다.
  sharedStorage = new MemoryStorage();
  vi.stubGlobal("localStorage", sharedStorage);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function freshStore() {
  const mod = await import("@/stores/terminal/layoutStore");
  return mod.useLayoutStore;
}

describe("layoutStore", () => {
  it("워크스페이스를 정하지 않으면 기본 레이아웃 상태로 시작한다", async () => {
    const store = await freshStore();

    expect(store.getState().workspaceId).toBeNull();
    expect(store.getState().layout.panels.map((p) => p.type)).toEqual(["chart", "symbol-info"]);
  });

  it("패널 구성을 바꾸고 '새로고침'해도 그대로 열린다 (FR-005)", async () => {
    const store1 = await freshStore();
    store1.getState().setWorkspace("ws-a");
    store1.getState().closePanel("chart-1");
    expect(store1.getState().layout.panels.map((p) => p.instanceId)).toEqual(["symbol-info-1"]);

    // "새로고침" — 모듈을 새로 평가해 완전히 새 스토어 인스턴스를 만들고, 같은 워크스페이스로 연다
    const store2 = await freshStore();
    store2.getState().setWorkspace("ws-a");

    expect(store2.getState().layout.panels.map((p) => p.instanceId)).toEqual(["symbol-info-1"]);
    expect(store2.getState().recovered).toBe(false);
  });

  it("워크스페이스를 바꾸면 그 워크스페이스 구성이 나오고, 되돌아오면 원래 구성이 보존돼 있다 (FR-024)", async () => {
    const store = await freshStore();

    store.getState().setWorkspace("ws-a");
    store.getState().closePanel("chart-1");

    store.getState().setWorkspace("ws-b");
    // ws-b 는 아직 저장본이 없다 — 기본 구성으로 열려야 하고, ws-a 값이 새어 들어오면 안 된다
    expect(store.getState().layout.panels.map((p) => p.instanceId)).toEqual(["chart-1", "symbol-info-1"]);
    store.getState().closePanel("symbol-info-1");

    store.getState().setWorkspace("ws-a");
    expect(store.getState().layout.panels.map((p) => p.instanceId)).toEqual(["symbol-info-1"]);

    store.getState().setWorkspace("ws-b");
    expect(store.getState().layout.panels.map((p) => p.instanceId)).toEqual(["chart-1"]);
  });

  it("한 워크스페이스의 localStorage 키가 다른 워크스페이스 키와 물리적으로 분리돼 있다", async () => {
    const store = await freshStore();

    store.getState().setWorkspace("ws-a");
    store.getState().closePanel("chart-1");
    store.getState().setWorkspace("ws-b");
    store.getState().closePanel("symbol-info-1");

    const rawA = sharedStorage.getItem("terminal-layout:ws-a");
    const rawB = sharedStorage.getItem("terminal-layout:ws-b");
    expect(rawA).not.toBeNull();
    expect(rawB).not.toBeNull();
    expect(JSON.parse(rawA!).state.layout.panels.map((p: { instanceId: string }) => p.instanceId)).toEqual([
      "symbol-info-1",
    ]);
    expect(JSON.parse(rawB!).state.layout.panels.map((p: { instanceId: string }) => p.instanceId)).toEqual(["chart-1"]);
  });

  it("손상된 저장본을 만나면 기본 구성으로 폴백하고 recovered:true 로 알린다", async () => {
    sharedStorage.setItem(
      "terminal-layout:ws-broken",
      JSON.stringify({ state: { layout: { panels: "not-an-array" } }, version: 0 }),
    );

    const store = await freshStore();
    store.getState().setWorkspace("ws-broken");

    expect(store.getState().recovered).toBe(true);
    expect(store.getState().layout.panels.map((p) => p.type)).toEqual(["chart", "symbol-info"]);
  });

  it("dismissRecovered 는 알림만 닫고 구성은 유지한다", async () => {
    sharedStorage.setItem(
      "terminal-layout:ws-broken",
      JSON.stringify({ state: { layout: { panels: "not-an-array" } }, version: 0 }),
    );
    const store = await freshStore();
    store.getState().setWorkspace("ws-broken");
    expect(store.getState().recovered).toBe(true);

    store.getState().dismissRecovered();

    expect(store.getState().recovered).toBe(false);
    expect(store.getState().layout.panels.map((p) => p.type)).toEqual(["chart", "symbol-info"]);
  });

  it("closePanel·toggleCollapsed·updateSettings 가 panels 를 유지한다", async () => {
    const store = await freshStore();
    store.getState().setWorkspace("ws-a");

    store.getState().toggleCollapsed("chart-1");
    expect(store.getState().layout.panels.find((p) => p.instanceId === "chart-1")?.collapsed).toBe(true);

    store.getState().updateSettings("chart-1", { interval: "1h" });
    expect(store.getState().layout.panels.find((p) => p.instanceId === "chart-1")?.settings).toEqual({
      interval: "1h",
    });

    store.getState().closePanel("chart-1");
    expect(store.getState().layout.panels.map((p) => p.instanceId)).not.toContain("chart-1");
  });

  it("resetPanels 가 닫은 패널을 되돌린다 — 자유 배치와 함께 사라진 「패널 추가」의 대체 경로", async () => {
    const store = await freshStore();
    store.getState().setWorkspace("ws-a");

    store.getState().closePanel("chart-1");
    store.getState().closePanel("symbol-info-1");
    expect(store.getState().layout.panels).toEqual([]);

    store.getState().resetPanels();

    expect(store.getState().layout.panels.map((p) => p.instanceId)).toEqual(["chart-1", "symbol-info-1"]);
  });

  it("좌표(grid)가 들어 있는 옛 v1 저장본으로도 복원이 깨지지 않는다", async () => {
    sharedStorage.setItem(
      "terminal-layout:ws-legacy",
      JSON.stringify({
        state: {
          layout: {
            schemaVersion: 1,
            panels: [{ instanceId: "chart-1", type: "chart", collapsed: false, settings: {} }],
            grid: [{ i: "chart-1", x: 3, y: 3, w: 6, h: 6 }],
          },
        },
        version: 0,
      }),
    );

    const store = await freshStore();
    store.getState().setWorkspace("ws-legacy");

    expect(store.getState().recovered).toBe(false);
    expect(store.getState().layout.panels.map((p) => p.instanceId)).toEqual(["chart-1"]);
    expect(store.getState().layout).not.toHaveProperty("grid");
  });
});
