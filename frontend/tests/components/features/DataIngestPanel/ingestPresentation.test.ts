import { describe, expect, it } from "vitest";
import {
  describeRunRows,
  describeRunStatus,
  scopePlaceholder,
  usesPeriod,
} from "@/components/features/DataIngestPanel/ingestPresentation";
import { RUN_STATUSES } from "@/schemas/terminal/ingest";

describe("describeRunStatus", () => {
  it("rate_limited 는 failed 와 다른 라벨·다른 색 계열로 갈린다", () => {
    const limited = describeRunStatus("rate_limited", "KOSPI:005930@2026-03-04");
    const failed = describeRunStatus("failed", null);

    expect(limited.label).not.toBe(failed.label);
    expect(limited.tone).not.toBe(failed.tone);
    expect(limited.tone).toBe("resumable");
    expect(failed.tone).toBe("failed");
  });

  it("rate_limited 는 cursor 를 사람이 읽을 문장으로 싣는다", () => {
    const view = describeRunStatus("rate_limited", "KOSPI:005930@2026-03-04");
    expect(view.note).toContain("KOSPI:005930@2026-03-04");
    expect(view.note).toContain("이어서");
  });

  it("cursor 가 없어도 이어받을 수 있다는 사실은 남는다", () => {
    const view = describeRunStatus("rate_limited", null);
    expect(view.note).toContain("이어서");
  });

  it("백엔드가 내는 상태 전부에 라벨이 있다", () => {
    for (const status of RUN_STATUSES) {
      const view = describeRunStatus(status, null);
      expect(view.label).not.toBe("");
      expect(view.label).not.toBe(status);
    }
  });

  it("모르는 상태는 삼키지 않고 원문 + 경고를 낸다", () => {
    const view = describeRunStatus("teleported", null);
    expect(view.label).toBe("teleported");
    expect(view.note).toBe("이 화면이 모르는 상태입니다");
  });
});

describe("describeRunRows", () => {
  it("0 건과 아직 없음을 가른다", () => {
    expect(describeRunRows({ written_rows: 0, skipped_rows: 0 })).toBe("받음 0 · 건너뜀 0");
    expect(describeRunRows({ written_rows: null, skipped_rows: null })).toBe("—");
  });

  it("한쪽만 있으면 있는 쪽만 적는다", () => {
    expect(describeRunRows({ written_rows: 1234, skipped_rows: null })).toBe("받음 1,234");
    expect(describeRunRows({ written_rows: null, skipped_rows: 7 })).toBe("건너뜀 7");
  });
});

describe("scope · period", () => {
  it("종목마스터는 시장 하나, 캔들 잡은 시장 + 종목", () => {
    expect(scopePlaceholder("instrument_master")).toContain("시장 하나");
    expect(scopePlaceholder("daily_bar")).toContain("시장 + 종목");
    expect(scopePlaceholder("minute_bar")).toContain("시장 + 종목");
  });

  it("종목마스터만 기간을 쓰지 않는다", () => {
    expect(usesPeriod("instrument_master")).toBe(false);
    expect(usesPeriod("daily_bar")).toBe(true);
    expect(usesPeriod("minute_bar")).toBe(true);
  });
});
