import { env } from "@/env";
export async function register() {
  if (env.NEXT_RUNTIME === "nodejs") {
    await import("./lib/logger/victoria");
    // DB 세션 타임존이 UTC 인지 기동 시 1회 본다 (#359). 어긋나면 던져 기동을 멈춘다 —
    // 우회 env 는 두지 않는다(fail-closed). 검사 대상은 `lib/prisma/client.ts` 가 만든
    // 커넥션이므로, 코드가 박은 `-c timezone=UTC` 가 실제로 살아서 서버까지 갔는지를 잰다.
    const { prisma } = await import("./lib/prisma/client");
    const { ensureSessionTimezoneUtc } = await import("./lib/prisma/sessionTimezone");
    await ensureSessionTimezoneUtc(prisma);
  }
}
