"use client";

import { useEffect, useMemo, useState } from "react";
import { SplitPane } from "@/components/shared/Layout/SplitPane";
import { showToast } from "@/components/shared/Feedback";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";
import { selectAccounts, selectHolders } from "@/services/devActivity/devActivityService";
import { AccountInfo, HolderInfo } from "@/schemas/devActivity/devActivity";
import { DevActivityControlBar } from "./DevActivityControlBar";
import { AccountListPanel } from "./AccountListPanel";
import { ChatPanel } from "./ChatPanel";

export default function DevActivityContainer() {
  const [accounts, setAccounts] = useState<AccountInfo[]>([]);
  const [holders, setHolders] = useState<HolderInfo[]>([]);
  const [account, setAccount] = useState<string | null>(null);
  const [scope, setScope] = useState("all"); // all | kind:<계좌유형>
  const [assetClass, setAssetClass] = useState("all"); // 화면 필터 (자산군)
  const [holderEmails, setHolderEmails] = useState<string[]>([]);
  const [since, setSince] = useState<string | null>(null);
  const [until, setUntil] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [as, hs] = await Promise.all([selectAccounts(), selectHolders()]);
        setAccounts(as);
        setHolders(hs);
      } catch (error) {
        showToast(getApiErrorMessage(error), "error");
      }
    })();
  }, []);

  // 범위 → kind + 좌측 목록 필터
  const kind = useMemo(() => (scope.startsWith("kind:") ? scope.slice(5) : null), [scope]);

  const visibleAccounts = useMemo(() => accounts.filter((a) => !kind || a.kind === kind), [accounts, kind]);

  // 입력창 위 "현재 적용 조건" 요약
  const summary = useMemo(() => {
    const kindLabel: Record<string, string> = { cash: "현금성", margin: "신용", pension: "연금" };
    const scopeLabel = account
      ? (accounts.find((a) => a.account_id === account)?.name ?? account)
      : kind
        ? (kindLabel[kind] ?? kind)
        : "전체";
    const holderNames = holderEmails.map((e) => holders.find((h) => h.email === e)?.name ?? e);
    const assetLabel: Record<string, string> = { equity: "주식", bond: "채권", fund: "펀드", cash: "현금성" };
    return [
      assetClass === "all" ? "전체 자산군" : (assetLabel[assetClass] ?? assetClass),
      scopeLabel,
      holderNames.length ? holderNames.join(", ") : null,
      since || until ? `${since ?? "…"} ~ ${until ?? "…"}` : "기간 자동",
    ]
      .filter(Boolean)
      .join(" · ");
  }, [account, kind, holderEmails, holders, accounts, assetClass, since, until]);

  return (
    <div className="h-full flex flex-col">
      <DevActivityControlBar
        accounts={accounts}
        holders={holders}
        scope={scope}
        assetClass={assetClass}
        holderEmails={holderEmails}
        since={since}
        until={until}
        onScopeChange={(s) => {
          setScope(s);
          setAccount(null); // 범위 변경 시 선택 계좌 초기화
        }}
        onAssetClassChange={setAssetClass}
        onHoldersChange={setHolderEmails}
        onRangeChange={(s, u) => {
          setSince(s);
          setUntil(u);
        }}
      />
      <div className="flex-1 min-h-0 border-t">
        <SplitPane orientation="horizontal" initialSizes={[28, 72]}>
          {[
            <AccountListPanel
              key="accounts"
              accounts={visibleAccounts}
              selectedAccount={account}
              onSelect={setAccount}
            />,
            <ChatPanel key="chat" scope={{ account, since, until, holders: holderEmails, kind }} summary={summary} />,
          ]}
        </SplitPane>
      </div>
    </div>
  );
}
