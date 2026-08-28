// @vitest-environment jsdom
//
// #398 (이 레포 이슈 — https://github.com/Danwoo/trading-lab/issues/398) — **「칸 수」에 상한을 넘긴
// 값을 치면 폼이 그 자리에서 되돌리고, 실행은 요청으로 이어진다.**
//
// 실측(이슈 본문): 「평균선 기간」 칸 수에 `99` → Tab → 「격자 실행」. 폼은 `891칸 — … 시도 891회를
// 씁니다.` 라고 약속했는데, 누르면 요청 0건·콘솔 0건·`role=alert` 0건이었다. 입력의 네이티브
// `max=9` 위반이라 제출이 `onSubmit` 에 닿기 전에 브라우저 단에서 막힌 것이다 — 폼이 선언한 상한과
// 상태가 받는 상한이 따로 놀았다.
//
// 같은 클래스의 재발 조건은 둘이다. ㉠ 상태가 범위 밖 값을 받는다. ㉡ 폼의 네이티브 `min`/`max` 가
// 상태의 범위와 다른 숫자를 말한다. 어느 쪽이든 「약속은 크게, 제출은 침묵」이 다시 난다. 그래서
// 진짜 훅(`useGridRunForm`)에 진짜 폼(`GridRunForm`)을 물려 사용자가 치는 대로 관통해 본다.
//
// 배치: 훅 + 폼 + 프리미티브(`NumberBox`)를 관통하는 회귀라 tests/regressions/ 에 둔다.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { GridRunForm } from "@/components/features/Bench/GridRunForm";
import { NumberBox } from "@/components/shared/ui/NumberBox";
import { useGridRunForm } from "@/hooks/bench/useGridRunForm";
import { STEPS_MAX, STEPS_MIN } from "@/lib/bench/sweep";
import type { BacktestGridIn } from "@/schemas/backtest/backtest";
import { selectBot } from "@/services/bot/botService";

vi.mock("@/services/bot/botService", () => ({ selectBot: vi.fn() }));

// 이슈가 재현한 봇과 같은 모양 — 축 둘(기간 5~120 · 눌림 깊이 0.5~15, 0.5 간격).
const A_BOT = {
  bot_id: 1,
  strategies: [
    {
      bot_strategy_id: 1,
      strategy_key: "ma_pullback",
      params: { ma_period: 20, dip_pct: 3 },
      param_sources: {},
      weight: null,
      sort_order: 0,
      form: {
        key: "ma_pullback",
        name: "이동평균 눌림목",
        timeframe: "1d",
        fields: [
          {
            name: "ma_period",
            label: "평균선 기간",
            control: "number",
            default: 20,
            min: 5,
            max: 120,
            step: 1,
            unit: "일",
          },
          {
            name: "dip_pct",
            label: "눌림 깊이",
            control: "number",
            default: 3,
            min: 0.5,
            max: 15,
            step: 0.5,
            unit: "%",
          },
        ],
      },
      missing_reason: null,
    },
  ],
};

afterEach(() => {
  cleanup();
  vi.mocked(selectBot).mockReset();
});

function Harness({ onRun }: { onRun: (input: BacktestGridIn) => void }) {
  const controller = useGridRunForm();
  return (
    <GridRunForm
      bots={[{ bot_id: 1, bot_nm: "봇" } as never]}
      controller={controller}
      isRunning={false}
      onRun={onRun}
    />
  );
}

async function givenFormWithBot() {
  vi.mocked(selectBot).mockResolvedValue(A_BOT as never);
  const onRun = vi.fn<(input: BacktestGridIn) => void>();
  const view = render(<Harness onRun={onRun} />);
  // 봇 선택은 드롭다운 프리미티브의 몫이 아니라 훅의 계약이다 — 훅을 직접 부르는 대신, 폼이 준 봇을
  // 고르는 것과 같은 경로(`changeBot`)를 페이지가 타듯 `?bot=` 로 탄다.
  return { onRun, ...view };
}

/**
 * 축 fieldset 안의 칸 수 입력 전부. **0건이면 실패다** — 축이 안 그려졌는데 초록이면 아무것도
 * 안 본 것이다. 몇 건을 봤는지 출력에 남긴다.
 */
function stepsInputs(container: HTMLElement): HTMLInputElement[] {
  const inputs = Array.from(container.querySelectorAll<HTMLInputElement>('fieldset input[type="number"]'));
  expect(inputs.length, "칸 수 입력이 0건 — 축이 안 그려져 아무것도 검사하지 못했다").toBeGreaterThan(0);
  console.log(`#398 검사한 칸 수 입력: ${inputs.length}건`);
  return inputs;
}

describe("#398 — 칸 수 상한을 넘긴 입력은 그 자리에서 눌리고, 실행은 요청으로 이어진다", () => {
  it("폼이 선언한 네이티브 범위와 상태가 받는 범위가 같은 숫자다", async () => {
    window.history.replaceState({}, "", "/bench?bot=1");
    const { container } = await givenFormWithBot();
    await waitFor(() => expect(screen.getByText("평균선 기간", { exact: false })).toBeTruthy());

    for (const input of stepsInputs(container)) {
      expect(input.min).toBe(String(STEPS_MIN));
      expect(input.max).toBe(String(STEPS_MAX));
    }
  });

  it("99 를 치면 칸이 상한을 보이고, 브라우저 판정도 유효하며, 약속한 칸 수가 상한 안이다", async () => {
    window.history.replaceState({}, "", "/bench?bot=1");
    const user = userEvent.setup();
    const { container } = await givenFormWithBot();
    await waitFor(() => expect(screen.getByText("평균선 기간", { exact: false })).toBeTruthy());
    const [period] = stepsInputs(container);

    await user.clear(period);
    await user.type(period, "99");
    await user.tab();

    expect(period.value).toBe(String(STEPS_MAX));
    // 네이티브 제약 위반이 남아 있으면 제출이 `onSubmit` 전에 조용히 막힌다 — 그 길이 닫혔는지 본다.
    expect(period.validity.valid).toBe(true);
    const promised = screen.getByText(/\d+칸 —/).textContent ?? "";
    const combos = Number(/(\d+)칸/.exec(promised)?.[1]);
    expect(combos).toBeLessThanOrEqual(STEPS_MAX * STEPS_MAX);
  });

  it("그 상태로 「격자 실행」을 누르면 요청이 만들어지고, 축마다 값이 상한을 넘지 않는다", async () => {
    window.history.replaceState({}, "", "/bench?bot=1");
    const user = userEvent.setup();
    const { container, onRun } = await givenFormWithBot();
    await waitFor(() => expect(screen.getByText("평균선 기간", { exact: false })).toBeTruthy());
    await user.type(screen.getByPlaceholderText("005930 또는 AAPL"), "005930");
    const [period, dip] = stepsInputs(container);
    await user.clear(period);
    await user.type(period, "99");
    await user.clear(dip);
    await user.type(dip, "59");

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "격자 실행" }));
    });

    expect(onRun).toHaveBeenCalledTimes(1);
    const sweep = onRun.mock.calls[0][0].sweep;
    expect(Object.keys(sweep)).toEqual(["ma_period", "dip_pct"]);
    for (const values of Object.values(sweep)) expect(values.length).toBeLessThanOrEqual(STEPS_MAX);
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 클래스 — 「칸 수」만의 일이 아니다.
//
// 네이티브 `min`/`max` 를 단 칸은 전부 같은 구조를 갖는다: 상태가 그 범위를 벗어나는 순간
// 제출이 브라우저 단에서 막히고, 두 벌 마운트 때문에 말풍선조차 안 뜬다. 이 레포에는 그런 칸이
// 「칸 수」 말고도 여럿 있다(전략 파라미터 · 손절/익절 % · 스케줄 시/분 · 메뉴 정렬순서).
// 그래서 그물을 두 축으로 친다:
//
//   ㉠ 범위를 선언한 칸을 **전수로 센다** — 0건이면 실패한다(아무것도 안 본 통과를 막는다).
//   ㉡ 그 범위가 DOM 속성이 되는 자리가 `NumberBox` **하나뿐**이다 — 두 번째가 생기면 이 그물이
//      안 보는 새 우회로가 된다.
//
// 그리고 그 하나뿐인 자리가 범위 밖 값을 **글로 말하는지**를 렌더로 확인한다. 값을 대신 눌러
// 주는 것은 범위가 한 자리인 칸(칸 수)에서만 상태 소유자가 한다 — 위의 훅 테스트가 그쪽이다.
// ─────────────────────────────────────────────────────────────────────────────

const FRONTEND_ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));
const SCAN_ROOTS = ["app", "components", "hooks", "lib", "utils"];
const NUMBERBOX_SOURCE = "components/shared/ui/NumberBox.tsx";

/**
 * 네이티브 범위(`min`/`max`)를 DOM 속성으로 그리는 파일 — **등록된 것이 전부여야 한다.**
 * 세 번째가 생기면 이 그물이 안 보는 새 우회로가 되므로, 늘리는 대신 프리미티브를 쓰게 고친다.
 *
 * `DateBox` 도 여기 있다 — 날짜 갈래는 텍스트 입력 + 자체 사유(`dateProblem`)라 침묵하지 않지만,
 * ㉠ 달력 팝업 앵커로 세워 둔 `aria-hidden` 숨은 `type="date"` 입력과 ㉡ `datetime`/`time` 갈래의
 * 네이티브 입력은 범위를 달고도 사유를 말하지 않는다. **지금은 `min`/`max` 를 넘기는 호출부가
 * 하나도 없어 잠복이다**(이 테스트가 전수로 확인한다). 살아나면 #398 과 같은 침묵이 된다.
 */
const BOUND_RENDERERS = [NUMBERBOX_SOURCE, "components/shared/ui/DateBox.tsx"];

function listSourceFiles(dir: string): string[] {
  if (!fs.existsSync(dir)) return [];
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules" || entry.name === "generated") continue;
      out.push(...listSourceFiles(full));
    } else if (entry.isFile() && /\.tsx?$/.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

const rel = (file: string) => path.relative(FRONTEND_ROOT, file).split(path.sep).join("/");

/** `<Tag … />` 한 덩어리씩 — 자기 닫는 태그까지 붙여 자른다(속성이 여러 줄이어도 통째로 잡힌다). */
function usagesOf(source: string, tag: string): string[] {
  const out: string[] = [];
  let from = 0;
  for (;;) {
    const open = source.indexOf(`<${tag}`, from);
    if (open === -1) return out;
    const close = source.indexOf("/>", open);
    if (close === -1) return out;
    out.push(source.slice(open, close + 2));
    from = close + 2;
  }
}

/** 그 덩어리가 네이티브 범위를 선언하는가. */
const declaresBound = (usage: string) => /(?<![\w-])(min|max)=/.test(usage);

describe("#398 클래스 — 네이티브 범위를 단 칸의 전수와, 그 범위를 그리는 자리의 개수", () => {
  const files = listSourceFiles(path.join(FRONTEND_ROOT, SCAN_ROOTS[0])).concat(
    ...SCAN_ROOTS.slice(1).map((root) => listSourceFiles(path.join(FRONTEND_ROOT, root))),
  );

  it("범위를 선언한 칸이 0건이 아니다 — 몇 건을 봤는지 남긴다", () => {
    const sites: string[] = [];
    for (const file of files) {
      if (rel(file) === NUMBERBOX_SOURCE) continue;
      const source = fs.readFileSync(file, "utf8");
      for (const usage of usagesOf(source, "NumberBox")) if (declaresBound(usage)) sites.push(rel(file));
    }
    console.info(
      `[#398 census] 스캔한 소스 파일 ${files.length}개 (${SCAN_ROOTS.join(", ")}) · ` +
        `네이티브 범위를 선언한 NumberBox ${sites.length}건 — ${[...new Set(sites)].join(", ")}`,
    );
    expect(files.length).toBeGreaterThan(0);
    expect(sites.length).toBeGreaterThan(0);
  });

  it("범위를 DOM 속성으로 그리는 자리가 등록된 목록과 정확히 같다", () => {
    // 판정은 넓게 — `<input` 과 `min=`/`max=` 속성이 **같은 파일에** 있으면 후보로 본다.
    // `<input …>` 한 태그 안으로 좁히면 속성 순서만 바꿔도(앞선 속성 식에 `>` 가 섞이면) 조용히
    // 빠져나간다. 넓은 쪽의 오탐(무관한 raw input 과 NumberBox 가 한 파일에 있는 경우)은 사람이
    // 한 번 보면 끝나지만, 좁은 쪽의 누락은 아무도 못 본다.
    const renderers = files
      .filter((file) => {
        const source = fs.readFileSync(file, "utf8");
        return source.includes("<input") && /(?<![\w-])(min|max)=[{"]/.test(source);
      })
      .map(rel)
      .sort();
    console.info(`[#398 census] 범위를 직접 그리는 파일 ${renderers.length}개 — ${renderers.join(", ")}`);
    expect(renderers).toEqual([...BOUND_RENDERERS].sort());
  });

  it("DateBox 에 범위를 넘기는 호출부가 아직 없다 — 잠복이 살아나면 여기가 먼저 빨개진다", () => {
    const callers = files.filter((file) => {
      if (BOUND_RENDERERS.includes(rel(file))) return false;
      return usagesOf(fs.readFileSync(file, "utf8"), "DateBox").some(declaresBound);
    });
    console.info(`[#398 census] DateBox 에 범위를 넘기는 호출부 ${callers.length}건`);
    expect(callers.map(rel)).toEqual([]);
  });
});

describe("#398 클래스 — 범위를 선언한 칸은 벗어난 값을 글로 말한다", () => {
  it("상한을 넘긴 값은 사유를 보이고 aria-invalid 가 선다", () => {
    render(<NumberBox fieldName="hour" value={99} min={0} max={23} onValueChanged={() => {}} />);
    const input = screen.getByRole("spinbutton") as HTMLInputElement;
    expect(input.getAttribute("aria-invalid")).toBe("true");
    const reason = screen.getByText("0~23 사이로 적으세요.");
    // 사유가 보조기술에도 닿아야 한다 — 보이기만 하면 화면을 못 보는 사람에게는 여전히 침묵이다.
    expect(input.getAttribute("aria-describedby")?.split(" ")).toContain(reason.id);
  });

  it("범위 안 값은 아무 말도 하지 않는다 — 거짓 경보를 만들지 않는다", () => {
    render(<NumberBox fieldName="hour" value={9} min={0} max={23} onValueChanged={() => {}} />);
    const input = screen.getByRole("spinbutton") as HTMLInputElement;
    expect(input.getAttribute("aria-invalid")).toBeNull();
    expect(screen.queryByText(/사이로 적으세요/)).toBeNull();
  });
});
