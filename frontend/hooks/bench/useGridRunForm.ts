"use client";

import { useEffect, useRef, useState } from "react";
import { sweepValues } from "@/lib/bench/sweep";
import type { BacktestGridIn } from "@/schemas/backtest/backtest";
import type { BotDetailOut, BotStrategyOut, StrategyField } from "@/schemas/bot/bot";
import { selectBot } from "@/services/bot/botService";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";

/** 축마다 훑는 칸 수 기본값 — 두 축이면 25칸. 격자는 지형을 보는 도구지 봉우리 찾기가 아니다. */
const DEFAULT_STEPS = 5;

export interface AxisChoice {
  field: StrategyField;
  enabled: boolean;
  steps: number;
}

export interface GridRunFormState {
  market: string;
  symbol: string;
  period_from: string;
  period_to: string;
  initial_cash: number | null;
}

export interface GridRunFormController {
  botId: number | null;
  strategy: BotStrategyOut | null;
  botDetailError: string | null;
  form: GridRunFormState;
  axes: AxisChoice[];
  formError: string | null;
  comboCount: number;
  changeBot: (botId: number | null) => void;
  changeField: (fieldName: keyof GridRunFormState, value: unknown) => void;
  toggleAxis: (index: number, enabled: boolean) => void;
  changeAxisSteps: (index: number, steps: number) => void;
  /** 입력이 성해야 input 을 만든다 — 아니면 사유를 `formError` 에 적고 null 을 준다. */
  buildInput: () => BacktestGridIn | null;
}

function isoDate(daysAgo: number): string {
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);
  return date.toISOString().slice(0, 10);
}

/** 훑을 수 있는 필드 — 숫자이면서 범위가 선언된 것만 축이 된다. */
function sweepableFields(strategy: BotStrategyOut): StrategyField[] {
  return (strategy.form?.fields ?? []).filter(
    (field) => field.control === "number" && field.min !== undefined && field.max !== undefined,
  );
}

/**
 * 격자 실행 폼의 상태 (#203) — **페이지가 한 번만 만든다.**
 *
 * 격자 자리는 넓은 배치와 좁은 배치에 두 벌 마운트된다(§21.6 — 폭 구간은 CSS 가 가른다).
 * 상태가 폼 컴포넌트 로컬이면 두 사본이 갈라져, 좁은 화면에서 채운 입력이 넓혀지는 순간
 * 사라진다. 그래서 상태는 여기 하나고 폼은 그리기만 한다.
 */
export function useGridRunForm(): GridRunFormController {
  const [botId, setBotId] = useState<number | null>(null);
  const [botDetail, setBotDetail] = useState<BotDetailOut | null>(null);
  const [botDetailError, setBotDetailError] = useState<string | null>(null);
  const [axes, setAxes] = useState<AxisChoice[]>([]);
  const [formError, setFormError] = useState<string | null>(null);
  const [form, setForm] = useState<GridRunFormState>({
    market: "KOSPI",
    symbol: "",
    period_from: isoDate(365 * 3),
    period_to: isoDate(0),
    initial_cash: 10_000_000,
  });

  const strategy = botDetail?.strategies[0] ?? null;

  const changeBot = (value: number | null) => {
    setBotId(value);
    setBotDetail(null);
    setBotDetailError(null);
    setAxes([]);
    if (value === null) return;
    selectBot(value)
      .then((detail) => {
        if (detail === null) throw new Error("봇을 불러오지 못했습니다");
        setBotDetail(detail);
        const fields = detail.strategies[0] ? sweepableFields(detail.strategies[0]) : [];
        // 앞의 두 축만 기본으로 켠다 — 격자는 2축까지 표로 펴진다. 셋째부터는 사용자가 켠다.
        setAxes(fields.map((field, i) => ({ field, enabled: i < 2, steps: DEFAULT_STEPS })));
      })
      .catch((error: unknown) => setBotDetailError(getApiErrorMessage(error)));
  };

  // 봇 화면의 「이 봇으로 검증하러 가기」가 `/bench?bot=<id>` 로 온다 — 그 봇을 집어 든다.
  // `useSearchParams` 대신 주소를 직접 읽는다: 그 훅은 정적 렌더에서 Suspense 경계를 요구하고
  // 라우터 컨텍스트 없이는 null 이라, 폼 하나 때문에 페이지 구조를 바꾸게 된다.
  // 한 번만 집는다 — 사용자가 폼에서 다른 봇으로 바꾼 뒤 되돌리면 안 된다.
  const pickedFromUrl = useRef(false);
  useEffect(() => {
    if (pickedFromUrl.current) return;
    const asked = Number(new URLSearchParams(window.location.search).get("bot"));
    if (!Number.isInteger(asked) || asked <= 0) return;
    pickedFromUrl.current = true;
    changeBot(asked);
  }, []);

  const changeField = (fieldName: keyof GridRunFormState, value: unknown) => {
    setForm((prev) => ({ ...prev, [fieldName]: value as never }));
  };

  const toggleAxis = (index: number, enabled: boolean) => {
    setAxes((prev) => prev.map((axis, i) => (i === index ? { ...axis, enabled } : axis)));
  };

  const changeAxisSteps = (index: number, steps: number) => {
    setAxes((prev) => prev.map((axis, i) => (i === index ? { ...axis, steps: steps || DEFAULT_STEPS } : axis)));
  };

  const enabledAxes = axes.filter((axis) => axis.enabled);
  const comboCount = enabledAxes.reduce(
    (acc, axis) => acc * Math.max(sweepValues(axis.field, axis.steps).length, 1),
    enabledAxes.length > 0 ? 1 : 0,
  );

  const buildInput = (): BacktestGridIn | null => {
    if (botId === null || strategy === null) {
      setFormError("봇을 먼저 고르세요.");
      return null;
    }
    if (strategy.form === null) {
      setFormError(`이 봇의 전략 파일을 읽지 못해 돌릴 수 없습니다 — ${strategy.missing_reason ?? "사유 없음"}`);
      return null;
    }
    if (form.symbol.trim() === "") {
      setFormError("종목을 적으세요 — 적재된 캔들이 있는 종목이어야 합니다.");
      return null;
    }
    // 못 읽은 날짜·금액은 프리미티브가 값을 비워 올린다 — 그 빈 값이 여기서 0 이나 옛 날짜로
    // 둔갑하지 않게 막는다. 시작 자금은 성과의 분모라 0 이면 격자 전 칸이 뜻을 잃는다.
    if (!form.period_from || !form.period_to) {
      setFormError("구간을 YYYY-MM-DD 로 다 적으세요.");
      return null;
    }
    // 두 값 다 화면이 이미 갖고 있어 서버까지 갈 필요가 없다. 사유는 **폼의 칸 이름**으로 적는다 —
    // 서버가 내는 같은 판정은 요청 본문의 이름(`date_from`)을 모르는 사람에게 닿는다.
    // `YYYY-MM-DD` 는 사전순이 날짜순이라 문자열 비교로 갈린다.
    if (form.period_from > form.period_to) {
      setFormError("구간 시작이 구간 끝보다 뒤입니다 — 두 날짜를 바꿔 적으세요.");
      return null;
    }
    if (form.initial_cash === null || !(form.initial_cash > 0)) {
      setFormError("시작 자금을 0보다 크게 적으세요 — 성과를 재는 분모입니다.");
      return null;
    }
    if (enabledAxes.length === 0) {
      setFormError("훑을 축을 하나 이상 켜세요 — 격자 실행은 축이 있어야 합니다.");
      return null;
    }
    setFormError(null);

    return {
      strategy_key: strategy.strategy_key,
      params: strategy.params,
      market: form.market,
      symbol: form.symbol.trim().toUpperCase(),
      period_from: form.period_from,
      period_to: form.period_to,
      initial_cash: form.initial_cash,
      bot_id: botId,
      sweep: Object.fromEntries(enabledAxes.map((axis) => [axis.field.name, sweepValues(axis.field, axis.steps)])),
    };
  };

  return {
    botId,
    strategy,
    botDetailError,
    form,
    axes,
    formError,
    comboCount,
    changeBot,
    changeField,
    toggleAxis,
    changeAxisSteps,
    buildInput,
  };
}
