"use client";

import { useEffect, useState } from "react";

import { selectDataKeyStatus, type DataKeyStatus } from "@/services/dataKey/dataKeyService";
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

  useEffect(() => {
    let cancelled = false;
    selectDataKeyStatus()
      .then((result) => {
        if (cancelled) return;
        setRows(result?.items ?? []);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setError(getApiErrorMessage(cause));
      });
    return () => {
      cancelled = true;
    };
  }, []);

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
        <li key={row.source} className="flex min-w-0 flex-col gap-0.5 border-b border-line py-2 last:border-b-0">
          <div className="flex min-w-0 flex-wrap items-baseline gap-x-2">
            <span className="text-sm text-ink">{row.source}</span>
            <span className="min-w-0 break-all font-mono text-2xs text-ink-muted">{row.setting}</span>
            <span className={row.filled ? "text-2xs text-ink" : "text-2xs text-danger"}>
              {row.filled ? "설정됨" : "없음"}
            </span>
          </div>
          {row.guidance && <p className="min-w-0 break-keep text-2xs text-ink-muted">{row.guidance}</p>}
        </li>
      ))}
    </ul>
  );
}
