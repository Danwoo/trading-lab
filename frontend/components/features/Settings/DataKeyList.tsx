"use client";

import { useCallback, useEffect, useState } from "react";

import { selectDataKeyStatus, type DataKeyStatus } from "@/services/dataKey/dataKeyService";
import { DataKeyRow } from "@/components/features/Settings/DataKeyRow";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";
import { useSessionContext } from "@/hooks/shared/useSessionContext";

/**
 * 데이터 소스 키가 **어디에 있고 지금 채워졌는지**.
 *
 * 값은 오지도 가지도 않는다. 상태는 누구나 읽지만 **넣는 것은 시스템관리자만** 한다 —
 * `.env` 한 줄은 워크스페이스에 속하지 않고 이 설치를 쓰는 모두에게 가기 때문이다 (#344).
 * 판정의 정본은 백엔드(`require_role(ROLE_ADMIN)`)이고, 여기서는 **할 수 없는 일을 권하지
 * 않으려고** 같은 경계를 화면에도 그린다 — 감추지는 않는다. 누가 바꿀 수 있는지 적어 둬야
 * 읽은 사람이 다음에 무엇을 할지 안다.
 */
export function DataKeyList() {
  const [rows, setRows] = useState<DataKeyStatus[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { isSysAdmin, isLoaded } = useSessionContext();

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
  if (rows === null || !isLoaded) {
    // 세션이 오기 전에 그리면 시스템관리자에게도 「할 수 없습니다」가 한 번 스쳤다가 뒤집힌다.
    return <p className="break-keep text-sm text-ink-muted">불러오는 중입니다…</p>;
  }
  if (rows.length === 0) {
    return <p className="break-keep text-sm text-ink-muted">키로 여는 소스가 없습니다.</p>;
  }

  return (
    <>
      {!isSysAdmin && (
        <p className="mb-2 break-keep text-2xs text-ink-muted">
          값을 넣는 것은 <strong className="font-normal text-ink">시스템관리자</strong>만 할 수 있습니다 — 이 설치를
          쓰는 모두에게 적용되는 값이라서입니다. 아래는 상태만 보입니다.
        </p>
      )}
      <ul className="flex min-w-0 flex-col">
        {rows.map((row) => (
          <DataKeyRow key={`${row.source}:${row.setting}`} row={row} canWrite={isSysAdmin} onSaved={load} />
        ))}
      </ul>
    </>
  );
}
