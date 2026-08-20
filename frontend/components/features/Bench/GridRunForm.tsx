"use client";

import { CheckBox } from "@/components/shared/ui/CheckBox";
import { DateBox } from "@/components/shared/ui/DateBox";
import { NumberBox } from "@/components/shared/ui/NumberBox";
import { SelectBox } from "@/components/shared/ui/SelectBox";
import { TextBox } from "@/components/shared/ui/TextBox";
import type { GridRunFormController } from "@/hooks/bench/useGridRunForm";
import type { BacktestGridIn } from "@/schemas/backtest/backtest";
import type { BotOut } from "@/schemas/bot/bot";

// bar 라우터가 받는 시장 목록과 같다 (backend-service/app/routers/bar/bar_router.py)
const MARKETS = ["KOSPI", "KOSDAQ", "KONEX", "NASDAQ", "NYSE", "AMEX"].map((value) => ({ value, label: value }));

/**
 * 격자 실행 폼 (#203) — 봇 하나를 골라 그 전략의 파라미터 지형을 훑는다.
 *
 * 실행이 곧 격자 실행이다(스펙 D-Q1) — 단일 점을 돌리는 길은 여기 없다. 축·칸 수를 사용자가
 * 보게 두는 이유: 칸 수가 곧 시도 수(§8.5.2)라, 무엇을 몇 번 시도하는지는 제품이 대신 정하지
 * 않고 보여 준 뒤 고르게 한다.
 *
 * 상태는 `useGridRunForm`(페이지가 한 번만 만든다)의 것이다 — 이 폼은 넓은·좁은 배치에 두 벌
 * 마운트되므로(§21.6) 여기서 상태를 가지면 두 사본이 갈라진다.
 */
export function GridRunForm({
  bots,
  controller,
  isRunning,
  onRun,
}: {
  bots: BotOut[] | null;
  controller: GridRunFormController;
  isRunning: boolean;
  onRun: (input: BacktestGridIn) => void;
}) {
  const { strategy, axes, form, formError, botDetailError, comboCount } = controller;

  return (
    <form
      aria-label="격자 실행"
      className="flex min-w-0 flex-col gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        const input = controller.buildInput();
        if (input !== null) onRun(input);
      }}
    >
      <div className="grid min-w-0 gap-2 sm:grid-cols-2">
        <label className="flex min-w-0 flex-col gap-1">
          <span className="break-keep text-2xs text-ink-muted">돌릴 봇</span>
          <SelectBox
            fieldName="bot_id"
            value={controller.botId}
            items={bots ?? []}
            displayExpr="bot_nm"
            valueExpr="bot_id"
            placeholder="봇 선택"
            onValueChanged={(_name, value) => controller.changeBot(value)}
          />
        </label>
        <label className="flex min-w-0 flex-col gap-1">
          <span className="break-keep text-2xs text-ink-muted">시장</span>
          <SelectBox
            fieldName="market"
            value={form.market}
            items={MARKETS}
            onValueChanged={(name, value) => controller.changeField(name, value)}
          />
        </label>
        <label className="flex min-w-0 flex-col gap-1">
          <span className="break-keep text-2xs text-ink-muted">종목</span>
          <TextBox
            fieldName="symbol"
            value={form.symbol}
            placeholder="005930 또는 AAPL"
            onValueChanged={(name, value) => controller.changeField(name!, value)}
          />
        </label>
        <label className="flex min-w-0 flex-col gap-1">
          <span className="break-keep text-2xs text-ink-muted">시작 자금</span>
          <NumberBox
            fieldName="initial_cash"
            value={form.initial_cash}
            onValueChanged={(name, value) => controller.changeField(name, value)}
          />
        </label>
        <label className="flex min-w-0 flex-col gap-1">
          <span className="break-keep text-2xs text-ink-muted">구간 시작</span>
          <DateBox
            fieldName="period_from"
            value={form.period_from}
            onValueChanged={(name, value) => controller.changeField(name, value)}
          />
        </label>
        <label className="flex min-w-0 flex-col gap-1">
          <span className="break-keep text-2xs text-ink-muted">구간 끝</span>
          <DateBox
            fieldName="period_to"
            value={form.period_to}
            onValueChanged={(name, value) => controller.changeField(name, value)}
          />
        </label>
      </div>

      {botDetailError && (
        <p role="alert" className="break-keep text-sm text-ink">
          {botDetailError}
        </p>
      )}

      {strategy && strategy.form === null && (
        <p role="alert" className="break-keep text-sm text-ink">
          전략 파일을 읽지 못했습니다 — {strategy.missing_reason ?? "사유 없음"}
        </p>
      )}

      {strategy?.form && (
        <fieldset className="min-w-0">
          <legend className="break-keep text-2xs text-ink-muted">
            훑을 축 — {strategy.form.name}의 범위 선언에서 왔습니다
          </legend>
          {axes.length === 0 ? (
            <p className="break-keep text-sm text-ink">이 전략에는 범위가 선언된 숫자 파라미터가 없습니다.</p>
          ) : (
            <ul className="mt-1 flex min-w-0 flex-col gap-1">
              {axes.map((axis, index) => (
                <li key={axis.field.name} className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
                  <CheckBox
                    fieldName={axis.field.name}
                    value={axis.enabled}
                    text={`${axis.field.label} (${axis.field.min}~${axis.field.max}${axis.field.unit ?? ""})`}
                    onValueChanged={(_name, checked) => controller.toggleAxis(index, Boolean(checked))}
                  />
                  {axis.enabled && (
                    <span className="flex items-center gap-1 text-2xs text-ink-muted">
                      칸 수
                      <NumberBox
                        fieldName="steps"
                        value={axis.steps}
                        min={2}
                        max={9}
                        width={72}
                        showSpinButtons
                        onValueChanged={(_name, value) => controller.changeAxisSteps(index, Number(value))}
                      />
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </fieldset>
      )}

      <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
        {/* 공용 Button 은 아직 팔레트 직결(파랑 액센트)이라 여기선 §1.4 버튼 서피스 토큰으로
            직접 그린다 — BenchPaths 와 같은 관례. 액센트 없는 시스템에서 버튼은 재질로 선다. */}
        <button
          type="submit"
          disabled={isRunning}
          className="rounded-control border border-btn-line bg-gradient-to-b from-btn-from to-btn-to px-3 py-1.5 text-sm font-ui text-ink disabled:opacity-45 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink-muted"
        >
          {isRunning ? "돌리는 중…" : "격자 실행"}
        </button>
        {comboCount > 0 && (
          <span className="break-keep text-2xs text-ink-muted">
            {comboCount}칸 — 훑는 것도 시도라 시도 {comboCount}회를 씁니다.
          </span>
        )}
      </div>

      {/* 실행 실패는 이 자리가 아니라 격자 자리의 머리(`BoardZone` 의 사유)가 말한다 —
          머리가 「아직 돌리지 않았습니다」인데 폼 아래에만 실패가 뜨면 한 자리가 두 말을 한다. */}
      {formError && (
        <p role="alert" className="break-keep border border-danger p-2 text-sm text-ink">
          {formError}
        </p>
      )}
    </form>
  );
}
