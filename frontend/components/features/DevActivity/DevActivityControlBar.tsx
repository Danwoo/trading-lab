"use client";

import { useMemo, type ReactNode } from "react";
import { SelectBox, TagBox, DateRangeBox } from "@/components/shared/ui";
import { ConditionBar } from "@/components/shared/Layout";
import { formatDate } from "@/utils/common/formatters/date";
import { AccountInfo, HolderInfo } from "@/schemas/devActivity/devActivity";

interface Props {
  accounts: AccountInfo[];
  holders: HolderInfo[];
  scope: string; // "all" | "kind:<계좌유형>"
  assetClass: string; // "all" | "equity" | "bond" | "fund" | "cash"
  holderEmails: string[]; // email 목록
  since: string | null;
  until: string | null;
  onScopeChange: (scope: string) => void;
  onAssetClassChange: (assetClass: string) => void;
  onHoldersChange: (holders: string[]) => void;
  onRangeChange: (since: string | null, until: string | null) => void;
}

const ASSET_CLASS_ITEMS = [
  { id: "all", text: "전체" },
  { id: "equity", text: "주식" },
  { id: "bond", text: "채권" },
  { id: "fund", text: "펀드" },
  { id: "cash", text: "현금성" },
];

const KIND_LABEL: Record<string, string> = { cash: "위탁", margin: "신용", isa: "ISA", pension: "연금" };

const Field = ({ label, children }: { label: string; children: ReactNode }) => (
  <div className="flex items-center gap-2">
    <span className="font-medium text-sm whitespace-nowrap">{label}</span>
    {children}
  </div>
);

export function DevActivityControlBar({
  accounts,
  holders,
  scope,
  assetClass,
  holderEmails,
  since,
  until,
  onScopeChange,
  onAssetClassChange,
  onHoldersChange,
  onRangeChange,
}: Props) {
  // 계좌 범위 옵션: 전체 / 실제 목록에 존재하는 계좌유형별 전체
  // (유형을 손으로 나열하지 않는다 — portfolio-mcp 가 isa 등 다른 값도 낸다)
  const scopeItems = useMemo(() => {
    const kinds = [...new Set(accounts.map((a) => a.kind).filter(Boolean))].sort();
    return [
      { id: "all", text: "전체" },
      ...kinds.map((kind) => ({ id: `kind:${kind}`, text: `${KIND_LABEL[kind] ?? kind} (전체)` })),
    ];
  }, [accounts]);

  const holderItems = useMemo(
    () => holders.map((h) => ({ email: h.email, label: h.name ? `${h.name} (${h.email})` : h.email })),
    [holders],
  );

  return (
    <ConditionBar>
      <Field label="계좌">
        <SelectBox
          fieldName="scope"
          value={scope}
          items={scopeItems}
          displayExpr="text"
          valueExpr="id"
          searchEnabled
          width={220}
          onValueChanged={(_f, v) => onScopeChange(v || "all")}
        />
      </Field>
      <Field label="자산군">
        <SelectBox
          fieldName="assetClass"
          value={assetClass}
          items={ASSET_CLASS_ITEMS}
          displayExpr="text"
          valueExpr="id"
          width={220}
          onValueChanged={(_f, v) => onAssetClassChange(v || "all")}
        />
      </Field>
      <Field label="계좌주">
        <TagBox
          fieldName="holders"
          value={holderEmails}
          items={holderItems}
          displayExpr="label"
          valueExpr="email"
          placeholder="전체"
          maxDisplayedTags={2}
          width={220}
          onValueChanged={(_f, v) => onHoldersChange(v || [])}
        />
      </Field>
      <Field label="조회기간">
        <DateRangeBox
          value={[since, until]}
          placeholder="질문에서 자동 추출"
          displayFormat="yyyy-MM-dd"
          type="date"
          onValueChanged={(_f, v) => onRangeChange(formatDate(v[0], "date"), formatDate(v[1], "date"))}
        />
      </Field>
    </ConditionBar>
  );
}
