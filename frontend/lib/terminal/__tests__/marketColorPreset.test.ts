import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  applyMarketColorPreset,
  DEFAULT_MARKET_COLOR_PRESET,
  isMarketColorPreset,
  MARKET_PRESET_ATTRIBUTE,
  readStoredMarketColorPreset,
  storeMarketColorPreset,
} from "@/lib/terminal/marketColorPreset";

describe("marketColorPreset", () => {
  it("기본값은 한국식이다", () => {
    expect(DEFAULT_MARKET_COLOR_PRESET).toBe("kr");
  });

  it("isMarketColorPreset 은 kr/us 만 인정한다", () => {
    expect(isMarketColorPreset("kr")).toBe(true);
    expect(isMarketColorPreset("us")).toBe(true);
    expect(isMarketColorPreset("KR")).toBe(false);
    expect(isMarketColorPreset(null)).toBe(false);
    expect(isMarketColorPreset(undefined)).toBe(false);
    expect(isMarketColorPreset("green")).toBe(false);
  });

  it("kr 과 us 가 서로 다른 속성값을 싣는다 (뒤집힘 방지)", () => {
    const setAttribute = vi.fn();
    applyMarketColorPreset("kr", { setAttribute });
    applyMarketColorPreset("us", { setAttribute });

    const values = setAttribute.mock.calls.map(([, value]) => value);
    expect(values).toEqual(["kr", "us"]);
  });

  it("applyMarketColorPreset 은 속성 하나만 싣는다 — 인라인 스타일을 박지 않는다", () => {
    // 인라인 스타일은 모든 선택자를 이기므로 값을 박으면 라이트 모드의 등락색이 다크 값에
    // 영원히 덮인다(#73 S1). 이 테스트가 그 회귀를 막는다.
    const setAttribute = vi.fn();
    applyMarketColorPreset("kr", { setAttribute });
    expect(setAttribute).toHaveBeenCalledTimes(1);
    expect(setAttribute).toHaveBeenCalledWith(MARKET_PRESET_ATTRIBUTE, "kr");
  });
});

describe("readStoredMarketColorPreset / storeMarketColorPreset", () => {
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

  beforeEach(() => {
    vi.stubGlobal("localStorage", new MemoryStorage());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("저장된 값이 없으면 null 이다", () => {
    expect(readStoredMarketColorPreset()).toBeNull();
  });

  it("저장 후 그대로 읽힌다 (왕복)", () => {
    storeMarketColorPreset("us");
    expect(readStoredMarketColorPreset()).toBe("us");
  });

  it("손상된 값(직접 조작)은 null 로 취급한다", () => {
    localStorage.setItem("terminal-market-color-preset", "not-a-preset");
    expect(readStoredMarketColorPreset()).toBeNull();
  });

  it("저장소가 예외를 던져도 조용히 실패한다", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    });
    expect(() => storeMarketColorPreset("kr")).not.toThrow();
    expect(readStoredMarketColorPreset()).toBeNull();
  });
});
