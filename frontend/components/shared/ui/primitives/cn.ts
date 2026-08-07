// components/shared/ui/primitives/cn.ts
//
// 클래스명 조합 헬퍼 — `clsx`/`tailwind-merge` 를 새로 들이지 않는다(#341 O8-3 오더: 명세 밖
// 신규 의존성 금지, radix-ui 1.6.7 하나만 승인됨). 레포 관례(CheckBoxGroup.tsx·ExpandableCard.tsx
// 등)가 이미 조건부 템플릿 리터럴로 충분히 써 왔다 — 이 헬퍼는 그 패턴을 함수로만 감싼 것이고,
// tailwind-merge 가 하는 "충돌 클래스 마지막 값 우선 병합"은 하지 않는다(단순 join). 프리미티브
// 커널의 합성 깊이(2~3단)에서는 충돌이 드물다 — 실제로 필요해지면 그때 의존성 도입을 판단한다.
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}
