"use client";

import { AccountInfo } from "@/schemas/devActivity/devActivity";

interface Props {
  accounts: AccountInfo[]; // 범위 필터가 적용된 목록 (Container 에서 전달)
  selectedAccount: string | null;
  onSelect: (account: string | null) => void;
}

export function AccountListPanel({ accounts, selectedAccount, onSelect }: Props) {
  const itemClass = (active: boolean) =>
    `px-4 py-2.5 cursor-pointer text-sm truncate transition-colors border-l-4 ${
      active
        ? "bg-blue-50 border-blue-500 text-blue-700 font-medium"
        : "border-transparent hover:bg-gray-50 text-gray-700"
    }`;

  // 최근활동일 기준 그룹핑은 두지 않는다 — portfolio-mcp 계좌 계약에 활동일 필드가 없다 (#368)
  const renderItem = (a: AccountInfo) => (
    <div
      key={a.account_id}
      className={itemClass(selectedAccount === a.account_id)}
      onClick={() => onSelect(a.account_id)}
      title={a.base_ccy ? `${a.name} · ${a.base_ccy}` : a.name}
    >
      {a.name}
    </div>
  );

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="px-4 py-3 border-b shrink-0">
        <h3 className="text-base font-semibold text-gray-800">계좌·포트폴리오</h3>
        <p className="text-xs text-gray-400 mt-0.5">{accounts.length}개 · 전체</p>
      </div>
      <div className="flex-1 overflow-y-auto">
        <div className={itemClass(selectedAccount === null)} onClick={() => onSelect(null)}>
          전체 (자동 탐색)
        </div>
        {accounts.map(renderItem)}
      </div>
    </div>
  );
}
