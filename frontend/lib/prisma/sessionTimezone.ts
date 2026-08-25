/**
 * DB 세션 타임존 규약 (#359) — 이 앱이 붙는 Postgres 세션은 **항상 UTC** 다.
 *
 * 감사·운영 시각 컬럼이 `timestamptz` 로 옮겨진 뒤, Prisma 어댑터(`@prisma/adapter-pg`)는
 * 오프셋 없는 UTC 자릿수 문자열을 보낸다(`formatDateTime`). 서버는 그 자릿수를 **세션 tz 로**
 * 해석하므로, 세션이 UTC 가 아니면 저장되는 인스턴트가 그만큼 어긋난다. 그래서 세션 tz 는
 * 환경(사용자 `.env`·서버 `postgresql.conf`)이 아니라 코드가 정한다.
 */

export const SESSION_TIMEZONE = "UTC";

const TIMEZONE_OPTION = `-c timezone=${SESSION_TIMEZONE}`;

/** 붙여 쓴 `-ctimezone=…` 한 토큰. */
const GLUED_TIMEZONE_OPTION = /^-c\s*timezone=/i;
/** 떼어 쓴 `-c timezone=…` 의 뒤 토큰. */
const TIMEZONE_ASSIGNMENT = /^timezone=/i;

/**
 * libpq `options` 문자열에서 timezone 지정만 UTC 로 바꾼다. 나머지 옵션은 순서대로 보존한다.
 *
 * libpq 는 `-c name=value` 를 **두 토큰으로도, 한 토큰(`-cname=value`)으로도** 받는다 — 둘 다
 * 걸러야 한다. 한 토큰 꼴만 보면 `-c timezone=Asia/Seoul` 이 살아남아 결과에 timezone 지정이
 * 둘이 되고, 뒤에 오는 것이 이기는지는 서버 구현에 기대게 된다.
 */
export function mergeUtcTimezoneOption(options: string): string {
  const tokens = options.split(/\s+/).filter((token) => token.length > 0);
  const kept: string[] = [];
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (token === "-c" && index + 1 < tokens.length) {
      const value = tokens[index + 1];
      index += 1;
      if (!TIMEZONE_ASSIGNMENT.test(value)) kept.push(token, value);
      continue;
    }
    if (GLUED_TIMEZONE_OPTION.test(token)) continue;
    kept.push(token);
  }
  return [...kept, TIMEZONE_OPTION].join(" ");
}

/**
 * `DATABASE_URL` 을 pg PoolConfig 로 옮기면서 세션 tz 를 UTC 로 못박는다.
 *
 * URL 의 `options=` 를 **떼어내** 코드가 병합한 값으로 넘기는 이유: pg 는 두 곳에 다 있으면
 * **URL 쪽을 쓴다**(실측 — `pg.Pool({connectionString:"…?options=-c timezone=Asia/Seoul",
 * options:"-c timezone=UTC"})` → `SHOW timezone` 이 `Asia/Seoul`). 그대로 두면 사용자 `.env`
 * 한 줄이 이 규약을 조용히 뒤집는다.
 */
export function poolConfigWithUtcTimezone(url: string): { connectionString: string; options: string } {
  const parsed = new URL(url);
  const urlOptions = parsed.searchParams.get("options") ?? "";
  parsed.searchParams.delete("options");
  return { connectionString: parsed.toString(), options: mergeUtcTimezoneOption(urlOptions) };
}

export class SessionTimezoneError extends Error {
  constructor(actual: string) {
    super(
      `DB 세션 타임존이 ${SESSION_TIMEZONE} 이 아니다: ${actual}. ` +
        "앱과 DB 사이의 무언가가 커넥션 startup 옵션을 떼어냈다는 뜻이다 " +
        "(예: ignore_startup_parameters 가 걸린 PgBouncer, 트랜잭션 풀링). " +
        "이 상태로 뜨면 감사 시각이 조용히 어긋나므로 기동을 멈춘다 (#359).",
    );
    this.name = "SessionTimezoneError";
  }
}

/** 기동 시 1회 — 세션 tz 가 UTC 가 아니면 던진다. 우회 env 는 두지 않는다(fail-closed). */
export async function ensureSessionTimezoneUtc(client: {
  $queryRaw: (query: TemplateStringsArray, ...values: unknown[]) => Promise<unknown>;
}): Promise<void> {
  const rows = (await client.$queryRaw`SHOW timezone`) as Array<Record<string, string>>;
  const actual = rows?.[0] ? Object.values(rows[0])[0] : undefined;
  if (actual !== SESSION_TIMEZONE) throw new SessionTimezoneError(String(actual));
}
