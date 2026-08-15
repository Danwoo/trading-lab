"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Button from "@/components/shared/ui/Button";
import { showToast } from "@/components/shared/Feedback";
import { getApiErrorMessage } from "@/utils/common/errors";
import { createBot, selectBot, selectStrategyCatalog, updateBot } from "@/services/bot/botService";
import { BotConversation } from "./BotConversation";
import { BotForm } from "./BotForm";
import {
  NEW_BOT_DRAFT,
  newStrategyDraft,
  toCreatePayload,
  toDraft,
  type BotDraft,
  type StrategyDraft,
} from "./botFormModel";
import type { StrategyForm } from "@/schemas/bot/bot";

interface Props {
  /** 없으면 새 봇, 있으면 저장된 봇을 열어 고친다. */
  botId?: number;
}

/**
 * 봇 만들기·고치기 — 대화(왼쪽)와 폼(오른쪽)을 나란히 놓는다 (실험대 스펙 §8.6.1).
 *
 * 폭 배분은 CSS 가 한다(`lg:grid-cols-…`) — JS 로 폭을 재서 가르면 첫 페인트가 튄다.
 */
export function BotWorkbench({ botId }: Props) {
  const router = useRouter();
  const [draft, setDraft] = useState<BotDraft>(NEW_BOT_DRAFT);
  const [strategy, setStrategy] = useState<StrategyDraft | null>(null);
  const [strategyForms, setStrategyForms] = useState<StrategyForm[]>([]);
  const [catalogErrors, setCatalogErrors] = useState<{ source: string; message: string }[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [catalog, bot] = await Promise.all([
          selectStrategyCatalog(),
          botId === undefined ? Promise.resolve(null) : selectBot(botId),
        ]);
        if (cancelled) return;

        const forms = catalog?.items ?? [];
        setStrategyForms(forms);
        setCatalogErrors(catalog?.errors ?? []);

        if (bot) {
          setDraft(toDraft(bot));
          // 저장된 값을 그대로 되돌려 놓는다 — 다시 열었을 때 조건이 그대로 보이는 것이
          // 마일스톤 2 의 완료 조건이다. 전략 파일이 사라졌으면 `form` 이 null 로 온다.
          const loaded = bot.strategies[0];
          if (loaded) {
            setStrategy({
              strategyKey: loaded.strategy_key,
              params: loaded.params,
              paramSources: loaded.param_sources as StrategyDraft["paramSources"],
            });
            if (loaded.form === null && loaded.missing_reason) setLoadError(loaded.missing_reason);
          }
        } else if (forms.length > 0) {
          setStrategy(newStrategyDraft(forms[0]));
        }
      } catch (error) {
        if (!cancelled) setLoadError(getApiErrorMessage(error));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [botId]);

  const handleDraftChange = useCallback((field: keyof BotDraft, value: unknown) => {
    setDraft((prev) => ({ ...prev, [field]: value }));
  }, []);

  const handleStrategyChange = useCallback(
    (key: string) => {
      const form = strategyForms.find((candidate) => candidate.key === key);
      if (form) setStrategy(newStrategyDraft(form));
    },
    [strategyForms],
  );

  const handleParamChange = useCallback((name: string, value: unknown) => {
    // 손댄 설정에 출처를 남긴다 — §8.6.3 「출처가 남는다」. 안 건드린 값은 선언 기본값 그대로다.
    setStrategy((prev) =>
      prev === null
        ? prev
        : {
            ...prev,
            params: { ...prev.params, [name]: value },
            paramSources: { ...prev.paramSources, [name]: "USER" },
          },
    );
  }, []);

  const handleSave = async () => {
    if (draft.bot_nm.trim() === "") {
      showToast("봇 이름을 적어주세요.", "warning");
      return;
    }
    if (strategy === null) {
      showToast("전략을 하나 고르면 저장할 수 있습니다.", "warning");
      return;
    }
    setIsSaving(true);
    try {
      const payload = toCreatePayload({ ...draft, bot_nm: draft.bot_nm.trim() }, [strategy]);
      const saved = botId === undefined ? await createBot(payload) : await updateBot(botId, payload);
      if (saved === null) return;
      showToast("봇을 저장했습니다.", "success");
      router.push("/bench/bot");
    } catch (error) {
      showToast(getApiErrorMessage(error), "error");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 p-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-medium text-ink-primary">{botId === undefined ? "봇 만들기" : "봇 고치기"}</h1>
          <p className="mt-1 text-sm text-ink-muted">
            말로 정하거나 직접 정합니다. 저장하면 이 조건이 그대로 남고, 검증은 그다음입니다.
          </p>
        </div>
        <div className="flex gap-2">
          <Button text="취소" onClick={() => router.push("/bench/bot")} />
          <Button text={isSaving ? "저장 중…" : "저장"} disabled={isSaving || isLoading} onClick={handleSave} />
        </div>
      </header>

      {loadError && (
        <p role="status" className="border border-slate-line px-3 py-2 text-sm text-ink-primary">
          {loadError}
        </p>
      )}

      {isLoading ? (
        <p className="text-sm text-ink-muted">불러오는 중입니다…</p>
      ) : (
        <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,4fr)_minmax(0,5fr)]">
          <BotConversation />
          <BotForm
            draft={draft}
            onDraftChange={handleDraftChange}
            strategy={strategy}
            strategyForms={strategyForms}
            catalogErrors={catalogErrors}
            onStrategyChange={handleStrategyChange}
            onParamChange={handleParamChange}
          />
        </div>
      )}
    </div>
  );
}
