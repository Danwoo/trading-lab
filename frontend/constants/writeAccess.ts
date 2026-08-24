import { GENERAL_ADMIN_AUTHOR_ID, SYS_ADMIN_AUTHOR_ID } from "./protected";

/**
 * 쓰기를 여는 권한 — backend `core/authorization.py` 의 `WRITE_ROLES` 와 짝이다.
 *
 * 백엔드는 이 두 역할만 통과시키고(`require_role(ROLE_ADMIN, ROLE_OPERATOR)`), 나머지 역할은
 * 403 「이 작업을 수행할 권한이 없습니다.」 로 돌려보낸다. 화면이 이 목록을 다르게 알면
 * **누를 수 있다고 말한 것이 403 으로 돌아온다** — 그것이 #341 의 증상이다.
 */
export const WRITE_AUTHOR_IDS: readonly string[] = [SYS_ADMIN_AUTHOR_ID, GENERAL_ADMIN_AUTHOR_ID];

/**
 * 백엔드가 operator/admin 으로 막아 둔 쓰기 라우터 prefix.
 *
 * 이 prefix 아래의 비-GET 요청은 전부 역할 게이트를 지난다 — 그래서 화면이 그 요청을 내는
 * 자리는 눌리기 **전에** 막힘을 말해야 한다. 목록은 `scripts/verify_write_gate_coverage.py` 가
 * 백엔드 라우터에서 직접 뽑아 이 상수와 정확히 대조한다(어긋나면 빨간불, 0건도 빨간불).
 *
 * 소비자가 TypeScript 밖에 있어 `@public` 을 단다 — 안 달면 knip 이 「아무도 안 부르는
 * export」로 세고, 그 말을 믿고 지우면 대조가 통째로 죽는다.
 *
 * @public
 */
export const ROLE_GATED_WRITE_PREFIXES: readonly string[] = [
  "/backtest-run",
  "/bot",
  "/ingest-run",
  "/portfolio",
  "/scheduler",
  "/watchlist",
];

/** 세션 권한으로 쓰기가 열리는지. `null`(아직 못 읽음)은 여기서 판단하지 않는다 — `useWriteAccess` 참조. */
export const canWriteWithAuthor = (authorId: string | null | undefined): boolean =>
  typeof authorId === "string" && WRITE_AUTHOR_IDS.includes(authorId);

/** 조작부 `title`·`aria-description` 에 들어가는 짧은 사유. 좁은 자리에 서므로 한 줄이다. */
export const WRITE_DENIED_SHORT = "저장·실행이 막혀 있습니다 — 이 계정은 읽기전용 게스트입니다";

/**
 * 조작부의 원래 hint(「등록」·「수정」) 뒤에 막힌 사유를 잇는다. hint 가 없는 버튼(아이콘만 있는
 * customActions)은 사유만 낸다 — 템플릿에 그대로 넣으면 `"undefined — …"` 가 화면에 뜬다.
 */
export const withWriteDeniedHint = (hint?: string): string =>
  hint ? `${hint} — ${WRITE_DENIED_SHORT}` : WRITE_DENIED_SHORT;

/** 배너 머리. 「무엇이 안 되는가」를 먼저 말한다. */
export const WRITE_DENIED_TITLE = "이 계정은 보기만 됩니다";

/** 배너 본문 — 왜 막혔나. */
export const WRITE_DENIED_REASON =
  "저장·실행은 운영자(operator) 이상만 열 수 있습니다. 이 계정은 초대받은 읽기전용 게스트라, 눌러도 서버가 막습니다.";

/** 배너 본문 — 지금 무엇을 할 수 있나. 읽기는 열려 있다는 것을 먼저 말한다. */
export const WRITE_DENIED_CAN_DO = "조회·차트·목록 보기는 그대로 열려 있습니다.";

/** 배너 본문 — 어떻게 여나. 「관리자에게 문의」로 끝내지 않고 그 관리자가 갈 자리까지 적는다. */
export const WRITE_DENIED_HOW =
  "직접 설치해 혼자 쓰는 중이라면 관리자 계정으로 /admin 의 시스템관리 › 권한관리 에서 이 계정을 운영자(operator)에 더하면 열립니다. 초대받아 들어온 계정이라면 그 워크스페이스 운영자에게 요청하세요.";
