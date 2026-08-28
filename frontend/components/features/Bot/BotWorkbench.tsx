"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Button from "@/components/shared/ui/Button";
import { showToast } from "@/components/shared/Feedback";
import { getApiErrorMessage } from "@/utils/common/errors";
import { createBot, selectBot, selectStrategyCatalog, updateBot } from "@/services/bot/botService";
import { BotConversation, type BotProposal } from "./BotConversation";
import { BotForm } from "./BotForm";
import { deleteBotWithConfirm } from "./deleteBotWithConfirm";
import {
  NEW_BOT_DRAFT,
  fieldNameFromServerError,
  newStrategyDraft,
  toCreatePayload,
  toDraft,
  type BotDraft,
  type StrategyDraft,
} from "./botFormModel";
import { cn } from "@/components/shared/ui/primitives/cn";
import { WriteAccessNotice } from "@/components/shared/Feedback/WriteAccessNotice";
import { useWriteAccess } from "@/hooks/shared/useWriteAccess";
import type { StrategyForm } from "@/schemas/bot/bot";
import { BotRunHistory } from "@/components/features/Bot/BotRunHistory";

interface Props {
  /** 없으면 새 봇, 있으면 저장된 봇을 열어 고친다. */
  botId?: number;
  /**
   * 372px 레일 패널 안에서 그린다. 패널이 이미 여백과 제목을 가지고 있어 그 둘을 겹치지
   * 않게 접는다 — 같은 말이 두 번 서면 좁은 폭에서 내용이 밀린다.
   */
  inPanel?: boolean;
}

/**
 * 봇 만들기·고치기 — 대화(왼쪽)와 폼(오른쪽)을 나란히 놓는다 (실험대 스펙 §8.6.1).
 *
 * 폭 배분은 CSS 가 한다(`lg:grid-cols-…`) — JS 로 폭을 재서 가르면 첫 페인트가 튄다.
 */
export function BotWorkbench({ botId, inPanel = false }: Props) {
  const router = useRouter();
  const [draft, setDraft] = useState<BotDraft>(NEW_BOT_DRAFT);
  const [strategy, setStrategy] = useState<StrategyDraft | null>(null);
  /**
   * 이 화면은 전략을 **하나만** 다룬다. 그런데 저장은 전략 배열을 통째로 갈아 끼우므로
   * (백엔드 `_replace_strategies` 가 지우고 다시 넣는다), 전략이 여럿인 봇을 열어 그냥
   * 저장하면 나머지가 조용히 사라진다. 「못 고친다」는 괜찮지만 「부순다」는 안 된다.
   */
  const [loadedStrategyCount, setLoadedStrategyCount] = useState(0);
  /**
   * 서버에서 실제로 읽어 온 봇 이름. 지우기는 **이 값이 있을 때만** 선다 — 없는 봇의 주소로
   * 되돌아왔을 때(지운 뒤 뒤로가기) 폼은 빈 초안이라, `draft` 를 믿으면 확인창이 「」 를
   * 지운다고 말하고 404 가 뻔한 요청이 나간다.
   */
  const [loadedBotName, setLoadedBotName] = useState<string | null>(null);
  const [strategyForms, setStrategyForms] = useState<StrategyForm[]>([]);
  const [catalogErrors, setCatalogErrors] = useState<{ source: string; message: string }[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  /**
   * 서버가 칸을 짚어 돌려보낸 저장 오류. 토스트는 몇 초 뒤 사라지는데 폼은 열 칸이 넘어,
   * 어느 칸을 고쳐야 하는지 화면에 남는 것이 없었다 — 그 칸에 `aria-invalid` 와 문장으로 남긴다.
   * 그 칸을 다시 손대거나 전략을 바꾸면 지운다(옛 오류가 새 값 위에 남으면 그것도 거짓이다).
   */
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const writeAccess = useWriteAccess();

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
          setLoadedBotName(bot.bot_nm);
          // 저장된 값을 그대로 되돌려 놓는다 — 다시 열었을 때 조건이 그대로 보이는 것이
          // 마일스톤 2 의 완료 조건이다. 전략 파일이 사라졌으면 `form` 이 null 로 온다.
          setLoadedStrategyCount(bot.strategies.length);
          if (bot.strategies.length > 1) {
            // 누른 뒤에 막는 것보다 열자마자 보이는 것이 낫다 — 무엇을 못 하는지 먼저 안다.
            setLoadError(
              `이 봇에는 전략이 ${bot.strategies.length}개 실려 있는데 이 화면은 하나만 다룹니다. ` +
                "여기서 저장하면 나머지가 지워지므로 저장을 막아 뒀습니다.",
            );
          }
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
      setFieldErrors({});
    },
    [strategyForms],
  );

  const handleParamChange = useCallback((name: string, value: unknown) => {
    setFieldErrors((prev) => {
      if (!(name in prev)) return prev;
      const { [name]: _cleared, ...rest } = prev;
      return rest;
    });
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

  /**
   * 대화가 낸 제안을 폼에 채운다 (스펙 §8.6.1 「대화가 폼을 채우고, 폼이 대화를 검증한다」).
   *
   * **선언에 없는 이름은 버린다** — 전략이 모르는 값을 폼에 얹으면 저장에서 터지고, 사용자는
   * 자기가 안 넣은 값 때문에 막힌다. 범위 검증은 저장 시점의 백엔드가 한다(전략 규약의 소유).
   * 채운 칸에는 **`AI 제안 수락` 출처**가 붙는다(§8.6.3) — 무엇이 내 결정이고 무엇이 제안인지
   * 나중에 구분되어야 한다.
   */
  const handleProposal = useCallback(
    (proposal: BotProposal) => {
      const form = strategyForms.find((candidate) => candidate.key === proposal.strategyKey);
      if (!form) return;
      setStrategy((prev) => {
        const base = prev !== null && prev.strategyKey === proposal.strategyKey ? prev : newStrategyDraft(form);
        const declared = new Set(form.fields.map((field) => field.name));
        const accepted = Object.entries(proposal.params).filter(([name]) => declared.has(name));
        return {
          ...base,
          params: { ...base.params, ...Object.fromEntries(accepted) },
          paramSources: {
            ...base.paramSources,
            ...Object.fromEntries(accepted.map(([name]) => [name, "AI_SUGGESTED" as const])),
          },
        };
      });
    },
    [strategyForms],
  );

  const handleSave = async () => {
    if (draft.bot_nm.trim() === "") {
      showToast("봇 이름을 적어주세요.", "warning");
      return;
    }
    if (strategy === null) {
      showToast("전략을 하나 고르면 저장할 수 있습니다.", "warning");
      return;
    }
    if (loadedStrategyCount > 1) {
      showToast(
        `이 봇에는 전략이 ${loadedStrategyCount}개 실려 있는데 이 화면은 하나만 다룹니다. ` +
          "여기서 저장하면 나머지가 지워지므로 막았습니다.",
        "warning",
      );
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
      const message = getApiErrorMessage(error);
      const form = strategyForms.find((candidate) => candidate.key === strategy.strategyKey);
      const name = fieldNameFromServerError(message, form?.fields ?? []);
      setFieldErrors(name === null ? {} : { [name]: message });
      showToast(message, "error");
    } finally {
      setIsSaving(false);
    }
  };

  /**
   * 불러온 봇만 지운다 — 아직 없는 것·이미 없는 것을 지우는 조작부는 뜻이 없다.
   *
   * 이름은 폼(`draft`)이 아니라 **읽어 온 값**을 쓴다. 확인창이 말하는 대상은 사용자가 지금
   * 타이핑 중인 이름이 아니라 서버에 저장된 그 봇이다.
   *
   * 전략이 여럿이라 저장을 막은 봇도 지우는 것은 막지 않는다. 저장을 막은 이유는 「이 화면이
   * 모르는 것을 조용히 버린다」인데, 삭제는 무엇이 사라지는지 확인에서 다 말하고 지운다.
   */
  const handleDelete = async () => {
    if (botId === undefined || loadedBotName === null) return;
    setIsDeleting(true);
    try {
      if (await deleteBotWithConfirm({ bot_id: botId, bot_nm: loadedBotName })) router.push("/bench/bot");
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className={cn("flex h-full min-h-0 flex-col gap-4", inPanel ? "p-0" : "p-6")}>
      <header className="flex flex-wrap items-end justify-between gap-3">
        {inPanel ? (
          <p className="min-w-0 break-keep text-sm text-ink-muted">
            말로 정하거나 직접 정합니다. 저장하면 이 조건이 그대로 남습니다.
          </p>
        ) : (
          <div>
            <h1 className="text-lg font-medium text-ink">{botId === undefined ? "봇 만들기" : "봇 고치기"}</h1>
            <p className="mt-1 text-sm text-ink-muted">
              말로 정하거나 직접 정합니다. 저장하면 이 조건이 그대로 남고, 검증은 그다음입니다.
            </p>
          </div>
        )}
        <div className="flex gap-2">
          {loadedBotName !== null && (
            <Button
              text={isDeleting ? "삭제 중…" : "삭제"}
              type="danger"
              stylingMode="outlined"
              disabled={isDeleting || isLoading || !writeAccess.canWrite}
              hint={writeAccess.deniedHint}
              onClick={() => void handleDelete()}
            />
          )}
          <Button text="취소" onClick={() => router.push("/bench/bot")} />
          <Button
            text={isSaving ? "저장 중…" : "저장"}
            disabled={isSaving || isLoading || !writeAccess.canWrite}
            hint={writeAccess.deniedHint}
            onClick={handleSave}
          />
        </div>
      </header>

      {/* 벽은 **누르기 전에** 선다 — 종전엔 「저장」이 활성인 채로 누른 뒤에야 403 이 왔다 (#341). */}
      {writeAccess.isDenied && <WriteAccessNotice halted={["봇 저장", "봇 삭제"]} />}

      {botId !== undefined && <BotRunHistory botId={botId} />}

      {loadError && (
        <p role="status" className="border border-line px-3 py-2 text-sm text-ink">
          {loadError}
        </p>
      )}

      {isLoading ? (
        <p className="text-sm text-ink-muted">불러오는 중입니다…</p>
      ) : (
        <div
          className={cn(
            "grid min-h-0 min-w-0 flex-1 gap-4",
            // 미디어쿼리는 **뷰포트**를 본다 — 넓은 화면에서 372px 패널 안에 있어도 `lg:` 가 켜져
            // 두 단으로 갈리고 글자가 한 자씩 끊긴다. 패널 안에서는 항상 한 단으로 쌓는다.
            inPanel ? "grid-cols-1" : "lg:grid-cols-[minmax(0,4fr)_minmax(0,5fr)]",
          )}
        >
          <BotConversation
            onProposal={handleProposal}
            formState={{ strategy_key: strategy?.strategyKey ?? null, params: strategy?.params ?? {} }}
          />
          <BotForm
            dense={inPanel}
            draft={draft}
            onDraftChange={handleDraftChange}
            strategy={strategy}
            strategyForms={strategyForms}
            catalogErrors={catalogErrors}
            onStrategyChange={handleStrategyChange}
            onParamChange={handleParamChange}
            fieldErrors={fieldErrors}
          />
        </div>
      )}
    </div>
  );
}
