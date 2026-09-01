"use client";

import { CheckBox } from "@/components/shared/ui/CheckBox";
import { NumberBox } from "@/components/shared/ui/NumberBox";
import { SelectBox } from "@/components/shared/ui/SelectBox";
import type { StrategyField } from "@/schemas/bot/bot";

interface Props {
  field: StrategyField;
  value: unknown;
  onChange: (name: string, value: unknown) => void;
  /** 라벨이 만든 id — 안 받으면 라벨과 안 이어져 보조기술에 이름 없는 칸이 된다 (#259). */
  id?: string;
  "aria-describedby"?: string;
  /** 서버가 이 칸을 짚었을 때의 검증 상태 — 프리미티브의 `getFieldProps` 계약 그대로. */
  getFieldProps?: (fieldName: string) => unknown;
}

/**
 * 전략이 선언한 파라미터 하나를 그린다.
 *
 * **이 파일이 아는 것은 `control` 세 종뿐이다** — 전략이 늘어도 여기는 안 바뀐다는 것이 전략
 * 규약의 약속이고(§3.4), 백엔드 `test_strategy_contract.py` 가 세 종 밖의 control 이 나오면
 * 실패한다. 즉 이 `switch` 가 규약의 화면 쪽 끝이다.
 */
export function StrategyFieldControl({ field, value, onChange, getFieldProps, ...rest }: Props) {
  // 프리미티브는 `keyof T` 로 받는다 — 이 화면의 칸 이름은 문자열뿐이다.
  const control = { ...rest, getFieldProps: getFieldProps && ((name: keyof any) => getFieldProps(String(name))) };
  switch (field.control) {
    case "number":
      return (
        <NumberBox
          {...control}
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
          {...control}
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
          {...control}
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
