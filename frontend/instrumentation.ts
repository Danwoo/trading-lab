export async function register() {
  // `process.env.NEXT_RUNTIME` 을 **직접** 본다 (`@/env` 래퍼가 아니라). Next 는 번들마다 이
  // 값을 빌드 시점에 치환하므로, edge 번들에서는 이 분기가 죽은 코드로 접혀 아래 import 가
  // 아예 추적되지 않는다. 래퍼를 거치면 값이 정적으로 안 보여 Prisma 클라이언트가 edge
  // instrumentation 번들까지 끌려 들어가고 `node:url` 류 경고가 뜬다 (#359 리뷰).
  if (process.env.NEXT_RUNTIME !== "nodejs") return;

  await import("./lib/logger/victoria");
  // DB 세션 타임존이 UTC 인지 기동 시 1회 본다 (이슈 359). 어긋나면 던져 기동을 멈춘다 —
  // 우회 env 는 두지 않는다(fail-closed). 검사 대상은 `lib/prisma/client.ts` 가 만든
  // 커넥션이므로, 코드가 박은 `-c timezone=UTC` 가 실제로 살아서 서버까지 갔는지를 잰다.
  const { prisma } = await import("./lib/prisma/client");
  const { ensureSessionTimezoneUtc } = await import("./lib/prisma/sessionTimezone");
  await ensureSessionTimezoneUtc(prisma);
}
