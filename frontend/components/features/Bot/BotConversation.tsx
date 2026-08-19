"use client";

import { useEffect, useRef, useState } from "react";
import { TextArea } from "@/components/shared/ui/TextArea";
import Button from "@/components/shared/ui/Button";
import { getApiErrorMessage } from "@/utils/common/errors";
import {
  selectBotAgentReadiness,
  streamBotAgent,
  type BotAgentEvent,
  type BotFormState,
} from "@/services/bot/botAgentService";

/** 대화가 낸 설정 제안 — 폼이 이것을 받아 채운다. */
export interface BotProposal {
  strategyKey: string;
  params: Record<string, unknown>;
  note: string | null;
}

interface Turn {
  role: "user" | "agent";
  text: string;
  /** 에이전트가 무엇을 읽었는지 — 판단의 근거가 숨지 않게 함께 보인다. */
  tools?: string[];
  /** 이 턴이 폼에 채운 것 — 대화만 보고도 무엇이 바뀌었는지 알 수 있어야 한다. */
  filled?: string[];
  /** 스트림 도중 실패했다 — 조용히 빈 턴으로 끝나지 않게 이유를 남긴다. */
  failed?: boolean;
}

/**
 * 대화 — 실험대 스펙 §8.6.1 「문이 두 개다」의 왼쪽 문.
 *
 * **못 쓰는 상태를 숨기지 않되, 대신 막지도 않는다.** 준비 상태가 「아니오」면 이유를 띠로 보여주고
 * 지금 할 수 있는 것(오른쪽 폼)을 가리키지만, 입력은 잠그지 않는다 — 준비 판정은 서비스가 아는
 * 것(키 설정 여부)만 보고, 실제로 도는지는 걸어봐야 안다(실측: 키가 없어도 기계의 Claude Code
 * 로그인으로 왕복했다). 못 도는 경우에는 `unavailable` 이벤트가 이유를 들고 온다.
 *
 * 빈 대화창만 있으면 「고장」으로 읽히고, 그럴싸한 가짜 답을 채우면 「된다」로 읽힌다 — 둘 다 안 한다.
 */
export function BotConversation({
  onProposal,
  formState,
}: {
  onProposal?: (proposal: BotProposal) => void;
  /** 매 턴 함께 보낸다 — 사용자가 손으로 고친 값을 대화가 모르면 「그대로 뒀습니다」가 거짓이 된다. */
  formState?: BotFormState;
}) {
  const [reasons, setReasons] = useState<string[] | null>(null);
  const [ready, setReady] = useState<boolean | null>(null);
  const [draft, setDraft] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    selectBotAgentReadiness().then((state) => {
      if (cancelled) return;
      setReady(state.ready);
      setReasons(state.ready ? null : state.reasons);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [turns]);

  const send = async () => {
    const message = draft.trim();
    if (message === "" || isStreaming) return;
    setDraft("");
    setTurns((prev) => [...prev, { role: "user", text: message }, { role: "agent", text: "", tools: [] }]);
    setIsStreaming(true);

    const apply = (update: (turn: Turn) => Turn) =>
      setTurns((prev) => prev.map((turn, index) => (index === prev.length - 1 ? update(turn) : turn)));

    try {
      await streamBotAgent(
        message,
        (event: BotAgentEvent) => {
          if (event.type === "text") apply((turn) => ({ ...turn, text: turn.text + event.text }));
          else if (event.type === "tool") {
            // 폼을 채우는 도구는 「읽음」이 아니다 — 그 결과는 아래 「폼에 채움」 줄이 말한다.
            // 내부 이름(`mcp__…`)이 화면에 새는 것도 여기서 막는다.
            if (!event.name.startsWith("mcp__")) {
              apply((turn) => ({ ...turn, tools: [...(turn.tools ?? []), event.name] }));
            }
          } else if (event.type === "proposal") {
            onProposal?.({ strategyKey: event.strategy_key, params: event.params, note: event.note });
            const filled = Object.entries(event.params).map(([name, value]) => `${name}=${String(value)}`);
            apply((turn) => ({ ...turn, filled: [...(turn.filled ?? []), ...filled] }));
          } else if (event.type === "unavailable") {
            // 정상 응답이다 — 대화가 왜 안 도는지 그대로 보여준다.
            setReady(false);
            setReasons(event.reasons);
            apply((turn) => ({ ...turn, text: event.reasons.join("\n") }));
          }
        },
        { form: formState },
      );
    } catch (error) {
      // 스트림이 시작된 뒤 난 실패도 여기로 온다 — `fetchSSE` 가 `{type:"error"}` 이벤트를
      // 가로채 예외로 바꾸기 때문이다. 그래서 이 한 자리가 실패의 유일한 출구다.
      apply((turn) => ({ ...turn, text: getApiErrorMessage(error), failed: true }));
    } finally {
      setIsStreaming(false);
    }
  };

  // 준비 안 됨은 **경고**지 잠금이 아니다. 잠그면 실제로 도는 환경에서도 못 쓰게 된다.
  const warned = ready === false;

  return (
    <section className="flex min-h-[16rem] flex-col border border-line bg-bg-panel">
      <header className="flex items-baseline justify-between gap-2 border-b border-line px-3 py-2">
        <h2 className="font-mono text-xs text-ink">대화</h2>
        <span className="font-mono text-2xs text-ink-muted">말하면 오른쪽 폼이 채워집니다</span>
      </header>

      {warned && (
        <div role="status" className="border-b border-line px-3 py-2">
          <p className="text-2xs leading-relaxed text-ink">
            대화가 안 될 수 있습니다. 안 되면 오른쪽 폼으로 직접 정할 수 있고, 정한 것은 그대로 남습니다.
          </p>
          <ul className="mt-1 flex flex-col gap-0.5">
            {(reasons ?? []).map((reason) => (
              <li key={reason} className="font-mono text-2xs leading-relaxed text-ink-muted">
                {reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div ref={logRef} className="min-h-0 flex-1 overflow-auto px-3 py-3">
        {turns.length === 0 ? (
          <p className="text-sm leading-relaxed text-ink-muted">
            &ldquo;코스피 대형주 눌림목 봇&rdquo; 처럼 말해보세요. 오른쪽 폼이 그 말대로 채워집니다.
          </p>
        ) : (
          <ul className="flex flex-col gap-3">
            {turns.map((turn, index) => (
              <li key={index} className="text-sm leading-relaxed">
                <span className="mr-2 font-mono text-2xs text-ink-muted">{turn.role === "user" ? "나" : "봇"}</span>
                <span
                  className={`whitespace-pre-wrap ${
                    turn.failed ? "text-danger" : turn.role === "user" ? "text-ink" : "text-ink-muted"
                  }`}
                >
                  {turn.text || (isStreaming && index === turns.length - 1 ? "…" : "")}
                </span>
                {turn.tools && turn.tools.length > 0 && (
                  <p className="mt-1 font-mono text-2xs text-ink-muted">읽음: {turn.tools.join(" · ")}</p>
                )}
                {turn.filled && turn.filled.length > 0 && (
                  <p className="mt-1 font-mono text-2xs text-ink-muted">폼에 채움: {turn.filled.join(" · ")}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex items-end gap-2 border-t border-line p-2">
        <div className="min-w-0 flex-1">
          <TextArea
            fieldName="message"
            value={draft}
            height="3.5rem"
            maxLength={4000}
            readOnly={ready === null}
            // placeholder 는 접근 가능한 이름이 아니다 — 입력이 시작되면 사라지고, 보조기술이
            // 이름으로 읽어 준다는 보장이 없다.
            aria-label="봇에게 할 말"
            placeholder="무엇을 만들까요?"
            onValueChanged={(_field, value) => setDraft(String(value ?? ""))}
          />
        </div>
        <Button
          text={isStreaming ? "받는 중…" : "보내기"}
          disabled={ready === null || isStreaming || draft.trim() === ""}
          onClick={send}
        />
      </div>
    </section>
  );
}
