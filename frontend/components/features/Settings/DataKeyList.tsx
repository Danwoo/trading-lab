"use client";

import { useCallback, useEffect, useState } from "react";

import { selectDataKeyStatus, type DataKeyStatus } from "@/services/dataKey/dataKeyService";
import { DataKeyRow } from "@/components/features/Settings/DataKeyRow";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";

/**
 * 데이터 소스 키가 **어디에 있고 지금 채워졌는지**.
 *
 * 값은 오지도 가지도 않는다 — 지금은 읽기만 한다. 넣는 경로(`.env` 쓰기)는 승인 뒤에 온다
 * (결정 로그 2026-08-19 — 앱이 각 서비스의 `.env` 에 직접 쓴다).
 */
export function DataKeyList() {
  const [rows, setRows] = useState<DataKeyStatus[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    selectDataKeyStatus()
      .then((result) => setRows(result?.items ?? []))
      .catch((cause: unknown) => setError(getApiErrorMessage(cause)));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (error !== null) {
    // 「못 읽었다」와 「없다」를 가른다 — 둘 다 회색이면 같아 보인다.
    return <p className="break-keep text-sm text-danger">키 상태를 읽지 못했습니다 — {error}</p>;
  }
  if (rows === null) {
    return <p className="break-keep text-sm text-ink-muted">불러오는 중입니다…</p>;
  }
  if (rows.length === 0) {
    return <p className="break-keep text-sm text-ink-muted">키로 여는 소스가 없습니다.</p>;
  }

  return (
    <ul className="flex min-w-0 flex-col">
      {rows.map((row) => (
        <DataKeyRow key={`${row.source}:${row.setting}`} row={row} onSaved={load} />
      ))}
    </ul>
  );
}
