"use client";

import { CheckBox } from "@/components/shared/ui/CheckBox";
import { NumberBox } from "@/components/shared/ui/NumberBox";
import { SelectBox } from "@/components/shared/ui/SelectBox";
import type { StrategyField } from "@/schemas/bot/bot";

interface Props {
  field: StrategyField;
  value: unknown;
  onChange: (name: string, value: unknown) => void;
}

/**
 * 전략이 선언한 파라미터 하나를 그린다.
 *
 * **이 파일이 아는 것은 `control` 세 종뿐이다** — 전략이 늘어도 여기는 안 바뀐다는 것이 전략
 * 규약의 약속이고(§3.4), 백엔드 `test_strategy_contract.py` 가 세 종 밖의 control 이 나오면
 * 실패한다. 즉 이 `switch` 가 규약의 화면 쪽 끝이다.
 */
export function StrategyFieldControl({ field, value, onChange }: Props) {
  switch (field.control) {
    case "number":
      return (
        <NumberBox
          fieldName={field.name}
          value={typeof value === "number" ? value : null}
          min={field.min}
          max={field.max}
          step={field.step}
          // 단위는 전략 선언이 준다 — 화면이 단위를 아는 순간 전략마다 화면을 고쳐야 한다.
          format={field.unit ? `#,##0${field.unit}` : undefined}
          onValueChanged={(name, next) => onChange(String(name), next)}
        />
      );
    case "select":
      return (
        <SelectBox
          fieldName={field.name}
          value={typeof value === "string" ? value : null}
          items={field.options ?? []}
          displayExpr="label"
          valueExpr="value"
          onValueChanged={(name, next) => onChange(String(name), next)}
        />
      );
    case "toggle":
      return (
        <CheckBox
          fieldName={field.name}
          value={value === true}
          onValueChanged={(name, next) => onChange(String(name), next)}
        />
      );
    default: {
      // 규약에 control 이 하나 늘면 **여기서 컴파일이 깨진다** — 화면이 모르는 컨트롤을 조용히
      // 빈 칸으로 그리는 것을 막는다(백엔드 `test_strategy_contract.py` 의 화면 쪽 짝).
      const unhandled: never = field.control;
      throw new Error(`화면이 모르는 컨트롤입니다: ${String(unhandled)}`);
    }
  }
}
