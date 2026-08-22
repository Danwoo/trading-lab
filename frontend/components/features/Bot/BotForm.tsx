"use client";

import { useId } from "react";

import { NumberBox } from "@/components/shared/ui/NumberBox";
import { SelectBox } from "@/components/shared/ui/SelectBox";
import { TextArea } from "@/components/shared/ui/TextArea";
import { TextBox } from "@/components/shared/ui/TextBox";
import { StrategyFieldControl } from "./StrategyFieldControl";
import { cn } from "@/components/shared/ui/primitives/cn";
import {
  BOT_ROLE_ITEMS,
  COMBINE_RULE_ITEMS,
  UNIVERSE_KIND_ITEMS,
  type BotDraft,
  type StrategyDraft,
} from "./botFormModel";
import type { StrategyForm } from "@/schemas/bot/bot";

interface Props {
  draft: BotDraft;
  onDraftChange: (field: keyof BotDraft, value: unknown) => void;
  strategy: StrategyDraft | null;
  strategyForms: StrategyForm[];
  catalogErrors: { source: string; message: string }[];
  onStrategyChange: (key: string) => void;
  onParamChange: (name: string, value: unknown) => void;
  /** 372px 패널처럼 좁은 자리 — 라벨과 컨트롤을 나란히 두지 않고 위아래로 쌓는다. */
  dense?: boolean;
}

/** 설정 한 줄이 어디서 왔는지 — 사람이 손댄 것과 선언 기본값이 섞이면 무엇을 정했는지 모른다. */
function SourceTag({ source }: { source?: "USER" | "AI_SUGGESTED" }) {
  const label = source === "AI_SUGGESTED" ? "AI 제안 수락" : source === "USER" ? "내가 정함" : "선언 기본값";
  return <span className="font-mono text-2xs text-ink-muted">{label}</span>;
}

/** `sourced` 는 **전략 파라미터 줄에만** 준다 — 봇 자체 설정에는 「선언」이 없어서 꼬리표가 거짓말이 된다. */
function Row({
  label,
  help,
  sourced,
  source,
  children,
}: {
  label: string;
  help?: string;
  sourced?: boolean;
  source?: "USER" | "AI_SUGGESTED";
  /**
   * 컨트롤을 만드는 함수. **라벨이 만든 id 를 받아 컨트롤에 달아야** 둘이 이어진다 —
   * 눈에 보이는 라벨을 `<span>` 으로만 그리면 보조기술에는 이름 없는 칸이고, 라벨을 눌러도
   * 포커스가 안 간다(#259). 설명(`help`)도 `aria-describedby` 로 함께 읽히게 잇는다.
   */
  children: (control: { id: string; "aria-describedby"?: string }) => React.ReactNode;
}) {
  const id = useId();
  const helpId = `${id}-help`;
  return (
    <div data-row className="grid gap-1.5 sm:grid-cols-[minmax(9rem,14rem)_minmax(0,1fr)] sm:items-start sm:gap-3">
      <div className="pt-1.5">
        <div className="flex items-baseline gap-2">
          <label htmlFor={id} className="text-sm text-ink">
            {label}
          </label>
          {sourced && <SourceTag source={source} />}
        </div>
        {help && (
          <p id={helpId} className="mt-0.5 text-2xs leading-relaxed text-ink-muted">
            {help}
          </p>
        )}
      </div>
      <div className="min-w-0">{children({ id, ...(help ? { "aria-describedby": helpId } : {}) })}</div>
    </div>
  );
}

function Section({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="border border-line bg-bg-panel">
      <header className="border-b border-line px-3 py-2">
        <h2 className="font-mono text-xs text-ink">{title}</h2>
        {note && <p className="mt-0.5 text-2xs text-ink-muted">{note}</p>}
      </header>
      <div className="flex flex-col gap-4 p-3">{children}</div>
    </section>
  );
}

/**
 * 봇 폼 — 대화의 짝(실험대 스펙 §8.6.1 「문이 두 개다」). 대화가 채워도 **사용자가 언제든 직접
 * 고칠 수 있어야** 하므로 이 폼이 언제나 지금 값을 보여주는 단일 표시면이다.
 *
 * 전략 파라미터 칸은 **전략 선언이 만든다** — 전략이 늘어도 이 파일은 안 바뀐다.
 */
export function BotForm({
  draft,
  onDraftChange,
  strategy,
  strategyForms,
  catalogErrors,
  onStrategyChange,
  onParamChange,
  dense = false,
}: Props) {
  const selectedForm = strategyForms.find((form) => form.key === strategy?.strategyKey) ?? null;

  return (
    <div
      className={cn(
        "flex min-h-0 min-w-0 flex-col gap-3 overflow-auto",
        // 미디어쿼리는 뷰포트를 본다 — 넓은 화면의 372px 패널 안에서도 `sm:` 이 켜져 라벨이
        // 폭을 다 가져가고 컨트롤이 「관 ▼」처럼 잘린다. 좁은 자리에서는 라벨을 위로 올린다.
        dense && "[&_[data-row]]:grid-cols-1",
      )}
    >
      <Section title="봇">
        <Row label="이름">
          {(control) => (
            <TextBox
              {...control}
              fieldName="bot_nm"
              value={draft.bot_nm}
              placeholder="예: 대형주 20일선 눌림목"
              onValueChanged={(field, value) => onDraftChange(field as keyof BotDraft, value)}
            />
          )}
        </Row>
        <Row label="설명" help="나중에 「왜 이렇게 샀지」를 되짚을 때 읽는 줄입니다.">
          {(control) => (
            <TextArea
              {...control}
              fieldName="bot_desc"
              value={draft.bot_desc}
              height="4.5rem"
              maxLength={500}
              onValueChanged={(field, value) => onDraftChange(field as keyof BotDraft, value)}
            />
          )}
        </Row>
      </Section>

      <Section
        title="전략"
        note={
          selectedForm
            ? `${selectedForm.timeframe} 기준 · ${selectedForm.fields.length}개 설정`
            : "전략 파일이 폼을 만듭니다."
        }
      >
        {catalogErrors.length > 0 && (
          // 「전략이 없다」와 「전략을 못 읽었다」는 다르다 — 후자를 빈 목록으로 뭉개지 않는다.
          <div className="border border-line px-3 py-2">
            <p className="text-2xs text-ink">읽지 못한 전략 파일이 {catalogErrors.length}개 있습니다.</p>
            <ul className="mt-1 flex flex-col gap-0.5">
              {catalogErrors.map((error) => (
                <li key={error.source} className="font-mono text-2xs text-ink-muted">
                  {error.source} — {error.message}
                </li>
              ))}
            </ul>
          </div>
        )}

        <Row label="고른 전략">
          {(control) => (
            <SelectBox
              {...control}
              fieldName="strategy_key"
              value={strategy?.strategyKey ?? null}
              items={strategyForms.map((form) => ({ value: form.key, label: form.name }))}
              displayExpr="label"
              valueExpr="value"
              noDataText="읽은 전략이 없습니다"
              onValueChanged={(_field, value) => onStrategyChange(String(value))}
            />
          )}
        </Row>

        {selectedForm?.summary && <p className="text-2xs leading-relaxed text-ink-muted">{selectedForm.summary}</p>}

        {selectedForm?.fields.map((field) => (
          <Row
            key={field.name}
            label={field.label}
            help={field.help}
            sourced
            source={strategy?.paramSources[field.name]}
          >
            {(control) => (
              <StrategyFieldControl
                {...control}
                field={field}
                value={strategy?.params[field.name]}
                onChange={onParamChange}
              />
            )}
          </Row>
        ))}
      </Section>

      <Section title="굴리는 규칙" note="아직 봇을 돌리지는 않습니다 — 저장되는 조건입니다.">
        <Row label="대상 종목">
          {(control) => (
            <SelectBox
              {...control}
              fieldName="universe_kind"
              value={draft.universe_kind}
              items={UNIVERSE_KIND_ITEMS}
              displayExpr="label"
              valueExpr="value"
              onValueChanged={(field, value) => onDraftChange(field as keyof BotDraft, value)}
            />
          )}
        </Row>
        <Row label="조건 결합" help="전략을 여럿 실으면 어떻게 합칠지입니다.">
          {(control) => (
            <SelectBox
              {...control}
              fieldName="combine_rule"
              value={draft.combine_rule}
              items={COMBINE_RULE_ITEMS}
              displayExpr="label"
              valueExpr="value"
              onValueChanged={(field, value) => onDraftChange(field as keyof BotDraft, value)}
            />
          )}
        </Row>
        <Row label="봇이 하는 일" help="실주문은 아직 없습니다. 지금 고를 수 있는 것은 보기와 제안뿐입니다.">
          {(control) => (
            <SelectBox
              {...control}
              fieldName="bot_role"
              value={draft.bot_role}
              items={BOT_ROLE_ITEMS}
              displayExpr="label"
              valueExpr="value"
              onValueChanged={(field, value) => onDraftChange(field as keyof BotDraft, value)}
            />
          )}
        </Row>
        <Row label="손절" help="산 값보다 이만큼 내리면 접습니다 (0~100%). 비우면 손절하지 않습니다.">
          {(control) => (
            <NumberBox
              {...control}
              fieldName="stop_loss_pct"
              value={draft.stop_loss_pct}
              min={0}
              max={100}
              step={0.5}
              format="#,##0.##%"
              onValueChanged={(field, value) => onDraftChange(field as keyof BotDraft, value)}
            />
          )}
        </Row>
        <Row label="익절" help="산 값보다 이만큼 오르면 챙깁니다 (0% 이상). 비우면 익절하지 않습니다.">
          {(control) => (
            <NumberBox
              {...control}
              fieldName="take_profit_pct"
              value={draft.take_profit_pct}
              min={0}
              step={0.5}
              format="#,##0.##%"
              onValueChanged={(field, value) => onDraftChange(field as keyof BotDraft, value)}
            />
          )}
        </Row>
        <Row
          label="종목당 비중"
          help="한 종목에 넣을 비중 (0% 이상). 무엇 대비인지는 봇을 굴리는 엔진이 정하는데 아직 없습니다. 비우면 배분을 정하지 않습니다."
        >
          {(control) => (
            <NumberBox
              {...control}
              fieldName="alloc_per_symbol"
              value={draft.alloc_per_symbol}
              min={0}
              step={1}
              format="#,##0.##%"
              onValueChanged={(field, value) => onDraftChange(field as keyof BotDraft, value)}
            />
          )}
        </Row>
        <Row label="최대 보유 종목" help="동시에 들고 갈 종목 수 (1종목 이상). 비우면 제한하지 않습니다.">
          {(control) => (
            <NumberBox
              {...control}
              fieldName="max_positions"
              value={draft.max_positions}
              min={1}
              step={1}
              format="#,##0종목"
              onValueChanged={(field, value) => onDraftChange(field as keyof BotDraft, value)}
            />
          )}
        </Row>
        <Row label="하루 최대 매매" help="하루에 낼 매매 횟수 (1회 이상). 비우면 제한하지 않습니다.">
          {(control) => (
            <NumberBox
              {...control}
              fieldName="max_trades_per_day"
              value={draft.max_trades_per_day}
              min={1}
              step={1}
              format="#,##0회"
              onValueChanged={(field, value) => onDraftChange(field as keyof BotDraft, value)}
            />
          )}
        </Row>
      </Section>
    </div>
  );
}
