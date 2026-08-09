"use client";

import { useState } from "react";
import { Button, TextBox, SelectBox, DateBox } from "@/components/shared/ui";
import { insertIngestRun } from "@/services/terminal/ingestService";
import { JOB_KINDS } from "@/schemas/terminal/ingest";
import { scopePlaceholder, usesPeriod } from "./ingestPresentation";

const JOB_KIND_ITEMS = [
  { value: "instrument_master", label: "종목마스터" },
  { value: "daily_bar", label: "일봉" },
  { value: "minute_bar", label: "분봉" },
] satisfies Array<{ value: (typeof JOB_KINDS)[number]; label: string }>;

interface FormState {
  source: string;
  job_kind: string;
  scope: string;
  period_from: string;
  period_to: string;
}

const EMPTY_FORM: FormState = {
  source: "",
  job_kind: "daily_bar",
  scope: "",
  period_from: "",
  period_to: "",
};

/**
 * 수동 적재 요청 폼. **어떤 `source` 문자열이 유효한지 프론트가 목록으로 갖지 않는다** — 소스가
 * 늘 때마다 두 벌이 갈리고, 무엇이 유효한지는 키가 꽂힌 서버만 안다(설계 §7.4). 자유 입력으로
 * 받아 백엔드 판정에 맡기고, 실패하면 서버 문구가 토스트로 그대로 뜬다.
 */
export function IngestRunForm({ onSubmitted }: { onSubmitted: () => void }) {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const setField = (fieldName: keyof FormState, value: unknown) => {
    setForm((prev) => ({ ...prev, [fieldName]: value == null ? "" : String(value) }));
  };

  const withPeriod = usesPeriod(form.job_kind);

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      await insertIngestRun({
        source: form.source,
        job_kind: form.job_kind,
        scope: form.scope,
        // 종목마스터는 시점 스냅샷이라 기간을 싣지 않는다. 빈 문자열도 보내지 않는다 —
        // 서버에서 "값이 있는데 비었다"로 읽힐 여지를 만들지 않는다.
        period_from: withPeriod && form.period_from ? form.period_from : undefined,
        period_to: withPeriod && form.period_to ? form.period_to : undefined,
      });
      setForm((prev) => ({ ...EMPTY_FORM, source: prev.source, job_kind: prev.job_kind }));
      onSubmitted();
    } finally {
      setIsSubmitting(false);
    }
  };

  const canSubmit = form.source.trim() !== "" && form.scope.trim() !== "" && !isSubmitting;

  return (
    <form
      className="flex flex-col gap-2 border-b border-slate-line pb-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (canSubmit) void handleSubmit();
      }}
    >
      <div className="grid grid-cols-2 gap-2">
        <label className="flex flex-col gap-1">
          <span className="text-ink-muted">소스</span>
          <TextBox<FormState>
            fieldName="source"
            value={form.source}
            placeholder="예: data_go_kr"
            onValueChanged={setField}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-ink-muted">잡 종류</span>
          <SelectBox<FormState>
            fieldName="job_kind"
            value={form.job_kind}
            items={JOB_KIND_ITEMS}
            valueExpr="value"
            displayExpr="label"
            onValueChanged={setField}
          />
        </label>
      </div>

      <label className="flex flex-col gap-1">
        <span className="text-ink-muted">범위</span>
        <TextBox<FormState>
          fieldName="scope"
          value={form.scope}
          placeholder={scopePlaceholder(form.job_kind)}
          onValueChanged={setField}
        />
      </label>

      {withPeriod && (
        <div className="grid grid-cols-2 gap-2">
          <label className="flex flex-col gap-1">
            <span className="text-ink-muted">시작일</span>
            <DateBox<FormState> fieldName="period_from" value={form.period_from} onValueChanged={setField} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-ink-muted">종료일</span>
            <DateBox<FormState> fieldName="period_to" value={form.period_to} onValueChanged={setField} />
          </label>
        </div>
      )}

      <Button
        text={isSubmitting ? "넣는 중…" : "적재 요청"}
        type="default"
        disabled={!canSubmit}
        useSubmitBehavior
        hint="큐에 넣습니다 — 실행은 백그라운드 워커가 집어 갑니다"
      />
    </form>
  );
}
