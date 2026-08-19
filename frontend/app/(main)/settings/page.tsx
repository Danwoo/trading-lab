import { DataKeyList } from "@/components/features/Settings/DataKeyList";

/** 이 설치에 매인 값을 다루는 자리 — 지금은 데이터 소스 키의 상태만 보인다 (#225). */
export default function Page() {
  return (
    <div className="flex min-h-full min-w-0 flex-col gap-4 p-4 xl:p-6">
      <header className="min-w-0">
        <h1 className="break-keep text-base font-title text-ink-strong">설정</h1>
        <p className="mt-1 break-keep text-sm text-ink-muted">
          어느 소스에 어떤 키가 필요하고 지금 채워져 있는지 보입니다. 키 값은 이 화면에 오지 않습니다.
        </p>
      </header>

      <section aria-label="데이터 소스 키" className="min-w-0 border border-line px-3 py-2">
        <h2 className="text-sm text-ink">데이터 소스 키</h2>
        <p className="mt-1 break-keep text-2xs text-ink-muted">
          값을 넣고 저장하면 <code className="font-mono">.env</code> 에 그 한 줄만 갈립니다 —{" "}
          <strong className="font-normal text-ink">반영에는 재기동이 필요합니다</strong>. 저장 전에 「연결 확인」으로 그
          키가 통하는지 볼 수 있습니다. 넣은 값은 저장 뒤 화면에 남지 않습니다.
        </p>
        <div className="mt-2">
          <DataKeyList />
        </div>
      </section>
    </div>
  );
}
