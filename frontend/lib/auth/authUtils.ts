import { prisma } from "@/lib/prisma/client";
import { Prisma } from "@/prisma/generated/client";
import { PERSONAL_WORKSPACE_DEFAULT_MENU_IDS, SYS_ADMIN_AUTHOR_ID } from "@/constants/protected";

export { hashPassword } from "better-auth/crypto";

// 이 저장소가 저장·조회에 쓰는 이메일 정규화 규칙의 단일 정의는 normalizeEmail.ts 에 있다
// (prisma·env 를 물지 않는 순수 함수라 vitest 가 가볍게 검증한다). 기존 호출부가
// `@/lib/auth/authUtils` 하나만 보고 있으므로 여기서 재수출해 import 경로를 늘리지 않는다.
export { normalizeEmail } from "@/lib/auth/normalizeEmail";
export { EMAIL_VERIFICATION_OTP_PREFIX, EMAIL_VERIFIED_GRANT_PREFIX } from "@/lib/auth/verificationIdentifier";
// 아래 deleteUserCascade 가 직접 쓰므로 재수출만으로는 부족하다 (재수출은 지역 스코프에 안 들어온다).
import { emailVerificationOtpIdentifier, emailVerifiedGrantIdentifier } from "@/lib/auth/verificationIdentifier";
export { emailVerificationOtpIdentifier, emailVerifiedGrantIdentifier };

/**
 * 가입 도중 실패했을 때 Better Auth 가 만들어 둔 사용자·계정을 되돌린다 (보상 삭제).
 *
 * Better Auth 는 자기 어댑터로 쓰기 때문에 호출자의 트랜잭션에 참여시킬 수 없다 — 가입은
 * "Better Auth 쓰기 → 나머지를 한 트랜잭션" 두 조각이고, 뒤 조각이 실패하면 앞 조각을 이걸로
 * 지워야 아무것도 안 남는다. 지우지 않으면 워크스페이스도 승인도 없는 반쪽 계정이 남고, 그
 * 이메일은 중복으로 막혀 재시도조차 그것을 치울 수 없다(#250 의 두 번째 증상).
 *
 * 지우는 대상은 Better Auth 가 만든 것뿐이다 — 뒤 조각(워크스페이스·멤버십·권한)이 만든 행은
 * `$transaction` 롤백이 이미 치웠다.
 */
export async function deleteHalfCreatedUser(userId: string): Promise<void> {
  await prisma.$transaction([
    prisma.baSession.deleteMany({ where: { userId } }),
    prisma.baAccount.deleteMany({ where: { userId } }),
    prisma.user.delete({ where: { id: userId } }),
  ]);
}

/**
 * 사용자들의 모든 활성 세션을 무효화한다 — 다음 요청부터 재로그인이 필요해진다.
 *
 * **이것만으로는 부족하다.** 세션 행을 지워도 Better Auth 의 쿠키 캐시가 그 자리를 대신
 * 채우면 인가가 그대로 통과한다 (#354, 실측 최대 5분). 캐시를 뚫는 자리는 인가 게이트
 * (`withAuth` 의 `disableCookieCache`)이고, 이 함수는 그 위에서 "세션 목록을 진실하게
 * 유지하는" 몫만 진다 — 관리자의 세션 화면과 재로그인 강제가 그것을 읽는다.
 */
export async function invalidateSessionsForUsers(emails: readonly string[]): Promise<number> {
  if (emails.length === 0) return 0;
  const users = await prisma.user.findMany({ where: { email: { in: [...emails] } }, select: { id: true } });
  if (users.length === 0) return 0;
  const { count } = await prisma.baSession.deleteMany({ where: { userId: { in: users.map((u) => u.id) } } });
  return count;
}

/**
 * 사용자 한 명의 모든 활성 세션을 무효화한다 (`invalidateSessionsForUsers` 의 단건 형태).
 */
export async function invalidateUserSessions(email: string): Promise<void> {
  await invalidateSessionsForUsers([email]);
}

/**
 * 지우는 개인 워크스페이스와 함께 비우는 `public` 스키마 테이블 — **FK 가 없어 조용히 남는 축**.
 *
 * `tn_workspace` 는 `frontend` 스키마(Prisma 소유)에 있고 이 테이블들은 `public`(alembic 소유)에
 * 있어 스키마를 가로지르는 FK 가 없다. 그래서 워크스페이스 행을 지워도 **예외도 로그도 없이**
 * 그대로 남는다 — #280 리드 결정(탈퇴자 자산을 서버가 계속 들고 있지 않는다)이 워크스페이스
 * 데이터 축에서 반쪽만 이행되던 자리다 (#363).
 *
 * 목록을 상수로 뽑아 둔 이유는 회귀 그물이 **같은 목록을 순회**하며 "삭제 후 0건"을 테이블마다
 * 확인하기 위해서다 — 코드와 그물이 각자 목록을 들면 한쪽만 늘어난다.
 * 새 워크스페이스 종속 테이블이 `public` 에 생기면 여기 추가한다 — 손으로 유지하는 목록은
 * 갈라지므로, 회귀 그물이 `information_schema` 를 원천으로 삼아 "`public` 의 `workspace_id`
 * 보유 테이블은 아래 두 목록 중 하나에 있어야 한다"를 대조한다.
 */
export const WORKSPACE_SCOPED_PUBLIC_TABLES = [
  // 백테스트 실행과 그 산출물(자산곡선·거래·신호·현금원장)은 개인 실험 결과다 — 탈퇴하면
  // 서버가 계속 들고 있지 않는다(#280 리드 결정). 자식 넷은 run_id 에 ON DELETE CASCADE 가
  // 걸려 있어 `tn_backtest_run` 만 지우면 함께 사라진다.
  "tn_backtest_run",
  "tn_bot",
  "tn_holding",
  "tn_nav",
  "tn_portfolio",
  "tn_research_document",
  "tn_scheduler",
  "tn_scheduler_member",
  "tn_watchlist",
] as const;

/**
 * `workspace_id` 를 갖지만 탈퇴 때 **일부러 안 지우는** `public` 테이블 — 제외에도 근거를 남긴다.
 *
 * - `tn_ingest_run` — 시세 적재 작업 로그다. 탈퇴자 자산이 아니고, `tn_daily_bar`·`tn_minute_bar`
 *   가 이 행을 FK 로 참조하므로 지우면 워크스페이스와 무관한 시세 데이터가 깨진다.
 * - `workspace_doc_chunk` — doc-search 가 소유하는 RAG 청크다. **별도 서비스·별도 엔진**이라
 *   이 함수의 Prisma 트랜잭션에서 지울 수 없다 (회수하려면 doc-search 에 요청해야 한다 —
 *   `delete_by_file` 이 이미 있다). 지울지 말지는 리드 결정이 필요해 **지금은 제외**이고,
 *   그 사이 그물이 조용히 깨지지 않게 여기 못 박는다 (#403).
 *   주의 — 이 테이블은 alembic·Prisma 밖이다. doc-search 가 색인 직전 `ensure_table()`
 *   (`CREATE TABLE IF NOT EXISTS`)로 **스스로 만든다**. 그래서 CI 의 `delete-user-cascade` 잡
 *   (tables.sql + alembic 으로만 DB 를 세운다)에는 **테이블 자체가 없어** 아래 대조에 안 잡힌다.
 *   "`workspace_id` 컬럼이 없어서"가 아니다 — 그 DDL 은 `workspace_id BIGINT NOT NULL` 을
 *   정의한다(`doc-search-mcp-service/app/repositories/workspace/workspace_chunk_repository.py`).
 *   개발 DB 에서 지금 안 잡히는 이유는 또 다르다: 마지막 인제스트가 레거시 `company_id` 시절이라
 *   컬럼명이 아직 옛 이름이고, 같은 파일의 리네임 DO 블록이 **다음 인제스트에 한 번 돌면** 이
 *   테이블이 대조 쿼리에 잡힌다. 이 등록이 없으면 그 순간 그물이 빨강이 된다(예약된 빨강).
 *   같은 DB 의 같은 `public` 스키마다 — 별도 `docsearch` DB 는 CONTEXT.md 결정 로그(2026-07-27)가
 *   기각했고 `.docs/5-인프라셋팅/로컬-postgres.md` 가 `DOC_VECTOR_DB_NAME=fintech` 를 지시한다.
 */
export const WORKSPACE_SCOPED_PUBLIC_TABLES_EXCLUDED = ["tn_ingest_run", "workspace_doc_chunk"] as const;

/**
 * 탈퇴자의 **식별자**(이메일 또는 `tn_user.id`)를 담는 컬럼이 있어 **사용자 축**에서 지우는 테이블.
 *
 * 워크스페이스 축(`WORKSPACE_SCOPED_PUBLIC_TABLES`)과 나눠 두는 이유는 #363 에서 이미 드러났다 —
 * 공용 워크스페이스만 쓰던 사용자(소유 개인 워크스페이스 0개)의 행은 워크스페이스 축 삭제로는
 * 하나도 안 지워진다. 이 목록은 `스키마.테이블` 로 적는다 (`frontend`·`public` 두 스키마에 걸쳐 있다).
 *
 * 회귀 그물이 `information_schema` 를 원천으로 삼아 "식별자 컬럼을 가진 테이블은 이 목록 또는
 * 아래 제외 목록에 있어야 한다"를 대조한다 — 손으로 유지하는 목록만 두면 새 테이블이 조용히 샌다.
 */
export const USER_SCOPED_IDENTIFIER_TABLES = [
  "frontend.ai_chat_history",
  "frontend.ba_account",
  "frontend.ba_session",
  "frontend.ba_verification",
  "frontend.th_email_log",
  "frontend.tn_author_member",
  "frontend.tn_user",
  "frontend.tn_workspace_member",
  "public.tn_scheduler_member",
] as const;

/**
 * 탈퇴자 식별자를 담지만 **일부러 안 지우는** 테이블 — 제외에도 근거를 남긴다.
 *
 * - `public.tn_research_document` — 리서치 문서다. 개인 워크스페이스분은 **워크스페이스 축**에서
 *   이미 지운다(`WORKSPACE_SCOPED_PUBLIC_TABLES`). 공용 워크스페이스에 남긴 것은 팀 자산이라
 *   지우지 않는다 — 2026-08-05 리드 결정(#363).
 * - `public.workspace_doc_chunk` — 위 `WORKSPACE_SCOPED_PUBLIC_TABLES_EXCLUDED` 의 근거와 같다
 *   (doc-search 자가 DDL·별도 엔진, #403).
 */
export const USER_SCOPED_IDENTIFIER_TABLES_EXCLUDED = [
  "public.tn_research_document",
  "public.workspace_doc_chunk",
] as const;

/**
 * 감사 컬럼(`reg_id`·`mod_id`)을 가진 테이블 전부 — 탈퇴 시 **삭제가 아니라 익명화**하는 축 (#3
 * 리드 결정 2026-08-12). 위 두 축(워크스페이스·식별자)과 성격이 다르다: 저 컬럼들은 「그 행의
 * 주체」가 아니라 **「그 행을 조작한 사람」**을 적으므로, 지우면 남의 행의 감사 이력이 통째로
 * 비고, 두면 탈퇴자 이메일이 남는다. 표준 처리는 연결을 끊되 기록은 남기는 것이다 —
 * 식별 데이터(이메일)는 `deletedUserAuditId(user.id)` 로 치환하고 행 자체는 보존한다.
 *
 * 제외 목록이 없다 — 감사 컬럼을 가진 테이블이면 예외 없이 이 축의 대상이다. 회귀 그물이
 * `information_schema` 를 원천으로 이 목록과 **양방향 완전 일치**를 대조하므로, 감사 컬럼을 가진
 * 테이블이 새로 생기면 그물이 빨강이 되고 여기 추가해야 한다 (deleteUserCascade.dbtest.ts).
 */
export const AUDIT_ANONYMIZED_TABLES = [
  "frontend.ai_chat_history",
  "frontend.tc_code",
  "frontend.tc_group_code",
  "frontend.tn_author",
  "frontend.tn_author_member",
  "frontend.tn_author_menu",
  "frontend.tn_menu",
  "frontend.tn_user",
  "frontend.tn_workspace",
  "frontend.tn_workspace_domain",
  "frontend.tn_workspace_member",
  "frontend.tn_workspace_menu",
  "public.tn_backtest_run",
  "public.tn_board",
  "public.tn_bot",
  "public.tn_bot_strategy",
  "public.tn_file",
  "public.tn_file_detail",
  "public.tn_holding",
  "public.tn_ingest_run",
  "public.tn_instrument",
  "public.tn_message_queue",
  "public.tn_nav",
  "public.tn_portfolio",
  "public.tn_research_document",
  "public.tn_scheduler",
  "public.tn_scheduler_member",
  "public.tn_symbol_alias",
  "public.tn_watchlist",
] as const;

/**
 * 탈퇴자의 감사 컬럼 대체값. 세 성질을 만족한다 (#3):
 * - **복원 불가** — `tn_user` 행이 같은 트랜잭션에서 지워지므로 이 id 는 커밋 시점에 아무
 *   신원에도 닿지 않는다 (이 id 를 담던 다른 자리 — `ba_*`·`tn_scheduler_member.account_id`·
 *   개인 워크스페이스 — 도 전부 같은 연쇄에서 지워진다).
 * - **같은 사람은 묶임** — 사용자당 id 가 하나이므로 여러 테이블에 흩어진 행위가 같은 값으로
 *   남는다. 모두를 하나의 상수로 뭉개면 탈퇴자 간 행위 구분이 사라져 감사 이력의 의미가
 *   절반 없어진다.
 * - **충돌 없음** — uuid 라 다른 탈퇴자·실사용자 값과 겹치지 않고, `@` 가 없어 이메일 모양의
 *   실값과도 구분된다. `reg_id`/`mod_id` 는 VarChar(100), 이 값은 49자다.
 */
export const deletedUserAuditId = (userId: string) => `deleted-user-${userId}`;

/**
 * 사용자와 그에 매달린 행 전부를 지운다 (회원탈퇴·관리자 삭제 공통 경로).
 *
 * `tn_user` 를 참조하는 자식 테이블은 넷이고(`tn_workspace_member`·`ba_session`·`ba_account` 는
 * `tn_user.id`, `tn_author_member` 는 `tn_user.email`) **어느 FK 에도 ON DELETE 절이 없다**
 * (prisma/init/tables.sql) — 하나라도 남기면 `user.delete` 가 FK 위반으로 실패한다.
 * 삭제 경로가 둘(자기 탈퇴 · 관리자 삭제)이라 순서를 두 벌로 두면 새 자식 테이블이 생길 때
 * 한쪽만 갱신돼 그 경로가 통째로 500 이 된다 — 실제로 `tn_workspace_member` 신설 때 그렇게 됐다.
 * 자식 테이블이 늘면 이 함수만 고친다.
 *
 * **소유한 개인 워크스페이스도 하드 삭제한다** (#280 리드 결정 — 탈퇴한 사용자의 자산을 서버가
 * 계속 들고 있는 부담이 더 크다, 보존이 필요하면 탈퇴 전 내보내기가 답). `role: "owner"` 멤버십은
 * `ensurePersonalWorkspace` 뿐 아니라 `seed.sql`·`0005_backfill_workspace_member` 리비전도
 * **공용 워크스페이스에** 만든다 — "owner 멤버십 = 개인 워크스페이스 소유"가 아니다. 그래서
 * `ownedWorkspaceIds` 조회 자체를 `workspace: { is_personal: true }` 로 좁힌다 — 이 술어 하나로
 * "이 사용자가 소유한 **개인** 워크스페이스"만 정확히 잡히므로, 아래 세 삭제(멤버십·메뉴·도메인·
 * 워크스페이스 자신) 전부가 공용 워크스페이스를 건드리지 않는다(가드를 자리마다 복제할 필요가
 * 없다). 위 멤버십 삭제로 먼저 소유 관계를 끊고, `user.delete` 이후에 워크스페이스를 지운다
 * (트랜잭션 배열 순서 = 실행 순서) — `tn_user.workspace_id → tn_workspace` FK 가 `NoAction` 이라
 * 사용자 행이 먼저 없어져야 그 워크스페이스를 지울 수 있다.
 *
 * **지우는 워크스페이스 자신의 자식도 먼저 비운다.** `tn_workspace` 를 참조하는 FK 는 넷이고
 * (`tn_user.workspace_id`·`tn_workspace_member`·`tn_workspace_menu`·`tn_workspace_domain`,
 * schema.prisma 전수 확인) 전부 `NoAction` 이다. 소유자 자신의 `tn_user` 행은 위에서 먼저 지워
 * 스칼라 FK 축이 끊긴다. 타 사용자가 이 개인 워크스페이스의 멤버로 들어오는 경로(사용자 생성·수정
 * 라우트가 `workspace_id` 를 검증 없이 받던 것)는 `assertAssignableWorkspace` 가 막는다 — 그
 * 전제가 깨지면 아래 `workspace.deleteMany` 가 FK 위반(P2003)으로 던져 탈퇴 전체가 실패한다 (#362).
 * 그리고 **관리 UI 는 개인 워크스페이스도 가리지 않고** 보여준다(`app/api/common/system/workspace/route.ts`) —
 * 운영자가 메뉴·도메인을 개인 워크스페이스에 붙일 수 있어 `tn_workspace_menu`·
 * `tn_workspace_domain` 은 소유자와 무관하게 남을 수 있다.
 * 이 함수만 고치면 되는 자리이므로(위 "자식 테이블이 늘면 이 함수만 고친다") 여기서 같이 비운다.
 * 자식 테이블이 더 늘면 이 자리도 함께 늘린다.
 *
 * **FK 가 없어 조용히 남는 축도 여기서 지운다** (#363). 위 자식들은 FK 가 있어 빠뜨리면 P2003 으로
 * 시끄럽게 실패하지만, 사용자 이메일을 그대로 들고 있는 `ai_chat_history` 와 `public` 스키마의
 * 워크스페이스 데이터(`WORKSPACE_SCOPED_PUBLIC_TABLES`)는 FK 가 없어 **아무 신호 없이** 남는다.
 * `public` 은 alembic 소유 스키마라 Prisma 모델이 없어 raw SQL 로 지운다 — 테이블명은 위 상수
 * (사용자 입력 아님)만 오고, 워크스페이스 id 는 파라미터로 바인딩한다.
 *
 * **메일 발송 로그(`th_email_log`)도 사용자 축에서 지운다** — 2026-08-05 리드 결정(#363): `to` 에
 * 남는 탈퇴자 주소를 감사 기록이 아니라 PII 로 본다. 워크스페이스 축이 아니라 사용자 축인 이유는
 * `ai_chat_history` 와 같다(공용 워크스페이스만 쓰던 사용자의 로그가 통째로 살아남는 것을 막는다).
 * 비교는 대소문자 무관이다 — `normalizeEmail` 규칙이 생기기 전에 쓰인 과거 행의 대소문자까지
 * 잡아야 하고, 같은 이유로 `workspaceScopedEmailWhere` 도 `mode: "insensitive"` 를 쓴다.
 *
 * **인증 토큰(`ba_verification`)도 사용자 축에서 지운다** — 2026-08-07 리드 결정(#3): 만료
 * 토큰이라 남길 감사 가치가 없고, 같은 PII 축인 `th_email_log` 결정과 짝을 맞춘다. FK 가 없어
 * 조용히 남는 자리다. 이 테이블은 **세 종류의 행이 섞여 있어 키가 셋**이다
 * (`verificationIdentifier.ts` 가 평문 키 둘의 조립을 정리해 둔다):
 * - 가입 OTP 행 — `identifier` 가 평문 `email-verification-otp-<이메일>` 이다. 발송 라우트와
 *   같은 조립 함수(`emailVerificationOtpIdentifier`)로 키를 만들어 **완전일치**로 지운다.
 *   `LIKE`·접두어 검색을 쓰지 않는 이유는 그 순간 `a@x.com` 이 `a@x.com.attacker.test` 를 함께
 *   끌고 오기 때문이다. 대소문자 무관 비교는 `th_email_log` 와 같은 근거다(정규화 규칙 이전 행) —
 *   대소문자만 다른 별개 계정이 과거에 만들어졌다면 그쪽의 **미사용 OTP 1건**까지 지워질 수
 *   있으나, 15분 만료 토큰이고 재발송으로 복구된다.
 * - OTP 통과 증거 행(#343) — `identifier` 가 평문 `email-verified-grant-<이메일>` 이다.
 *   OTP 행과 같은 이유·같은 방식(완전일치·대소문자 무관)으로 지운다.
 * - 비밀번호 재설정 행 — `identifier` 는 `storeIdentifier: "hashed"` 때문에 SHA-256 해시라
 *   이메일로 못 찾는다. 대신 `value` 가 `tn_user.id` 원문이므로 그 완전일치로 지운다
 *   (uuid 라 남의 행과 겹치지 않는다). 남겨 두면 탈퇴자의 **아직 안 쓴 재설정 토큰**이 만료까지
 *   테이블에 남는다.
 *
 * **감사 컬럼(`reg_id`·`mod_id`)은 지우지 않고 익명화한다** — 2026-08-12 리드 결정(#3 ㉡):
 * 삭제 대상은 「그 사람을 식별하는 데이터」이고, 감사 컬럼은 「그 사람이 한 행위의 기록」이라
 * 연결만 끊고 기록은 보존한다. 남의 행에 남은 탈퇴자 이메일(예: 관리자였던 탈퇴자가 만든
 * 타 사용자 행)이 대상이므로 `AUDIT_ANONYMIZED_TABLES` 전체를 쓸며, 치환값은
 * `deletedUserAuditId(user.id)` 다 (성질 셋은 그 함수 주석에). 규칙:
 * - **NULL 로 만들지 않는다** — 「누가 했는지 모른다」와 「탈퇴한 사람이 했다」는 다르다.
 * - **컬럼 단위로 치환한다** — 같은 행이라도 `reg_id` 만 탈퇴자면 `mod_id` 는 남의 값 그대로다.
 * - **대소문자 무관 비교** — `th_email_log`·OTP 삭제와 같은 근거 (정규화 규칙 이전의 과거 행).
 *   `MGR`·`migration`·`system` 같은 비이메일 액터 값은 이메일과 대소문자 무관으로도 겹칠 수
 *   없어 안전하다 (alembic 0007 전수 조사).
 * - **같은 트랜잭션이다** — 삭제와 익명화가 따로 커밋되면 실패 시 「지워졌는데 이메일은 남은」
 *   반쪽 상태가 된다. 삭제 문들 뒤에 두어 지워질 행은 갱신하지 않는다.
 * 익명화는 되돌릴 수 없다 — 그게 목적이다. 이미 탈퇴한 사용자의 잔존 값은 이 함수가 못 다루므로
 * (tn_user 행이 없어 id 를 모른다) alembic `0013_anonymize_withdrawn_audit` 이 별도로 정리한다.
 */
export async function deleteUserCascade(email: string): Promise<void> {
  const user = await prisma.user.findUnique({ where: { email }, select: { id: true } });
  const ownedWorkspaceIds = user
    ? (
        await prisma.workspaceMember.findMany({
          where: { user_id: user.id, role: "owner", workspace: { is_personal: true } },
          select: { workspace_id: true },
        })
      ).map((m) => m.workspace_id)
    : [];

  const results = await prisma.$transaction([
    prisma.authorMember.deleteMany({ where: { user_id: email } }),
    // 대화 이력은 워크스페이스가 아니라 사용자 이메일에 매달려 있다 — 공용 워크스페이스에만
    // 속했던 사용자(소유 개인 워크스페이스 0개)의 이력도 지워져야 한다.
    prisma.aiChatHistory.deleteMany({ where: { email } }),
    // 메일 발송 로그도 이메일에 매달린 사용자 축이다 (리드 결정 #363 — PII 로 보고 지운다).
    prisma.emailLog.deleteMany({ where: { to: { equals: email, mode: "insensitive" } } }),
    // 가입 인증 OTP — identifier 평문에 이메일이 들어간다 (리드 결정 #3).
    prisma.baVerification.deleteMany({
      where: { identifier: { equals: emailVerificationOtpIdentifier(email), mode: "insensitive" } },
    }),
    // OTP 를 통과했다는 증거도 같은 축이다 — identifier 에 이메일이 평문으로 들어간다 (#343).
    prisma.baVerification.deleteMany({
      where: { identifier: { equals: emailVerifiedGrantIdentifier(email), mode: "insensitive" } },
    }),
    ...(user
      ? [
          // 비밀번호 재설정 토큰 — identifier 는 해시라 못 찾고 value 가 tn_user.id 원문이다.
          prisma.baVerification.deleteMany({ where: { value: user.id } }),
          prisma.workspaceMember.deleteMany({ where: { user_id: user.id } }),
          prisma.baSession.deleteMany({ where: { userId: user.id } }),
          prisma.baAccount.deleteMany({ where: { userId: user.id } }),
          // 주간 활동요약 수신자 등록도 사용자 축이다(`account_id` = `tn_user.id`) — 남겨 두면
          // 탈퇴한 주소로 메일이 계속 나간다. 아래 워크스페이스 축 삭제와 겹쳐도 무해하다.
          prisma.$executeRaw`DELETE FROM public.tn_scheduler_member WHERE account_id = ${user.id}`,
        ]
      : []),
    prisma.user.delete({ where: { email } }),
    ...(ownedWorkspaceIds.length > 0
      ? [
          prisma.workspaceMenu.deleteMany({ where: { workspace_id: { in: ownedWorkspaceIds } } }),
          prisma.workspaceDomain.deleteMany({ where: { workspace_id: { in: ownedWorkspaceIds } } }),
          ...WORKSPACE_SCOPED_PUBLIC_TABLES.map(
            (table) =>
              prisma.$executeRaw`DELETE FROM ${Prisma.raw(`public.${table}`)} WHERE workspace_id IN (${Prisma.join(ownedWorkspaceIds)})`,
          ),
          prisma.workspace.deleteMany({ where: { id: { in: ownedWorkspaceIds }, is_personal: true } }),
        ]
      : []),
    ...(user
      ? AUDIT_ANONYMIZED_TABLES.map(
          (table) =>
            prisma.$executeRaw`UPDATE ${Prisma.raw(table)}
               SET reg_id = CASE WHEN lower(reg_id) = lower(${email}) THEN ${deletedUserAuditId(user.id)} ELSE reg_id END,
                   mod_id = CASE WHEN lower(mod_id) = lower(${email}) THEN ${deletedUserAuditId(user.id)} ELSE mod_id END
             WHERE lower(reg_id) = lower(${email}) OR lower(mod_id) = lower(${email})`,
        )
      : []),
  ]);

  // 무엇을 몇 건 처리했는지 남긴다 — 익명화는 비가역이라 처리 건수가 로그에 있어야 사후 검증이
  // 가능하다. 이메일은 PII 라 남기지 않고 익명화 id 로 적는다.
  if (user) {
    const counts = results.slice(-AUDIT_ANONYMIZED_TABLES.length) as number[];
    const touched = AUDIT_ANONYMIZED_TABLES.map((table, i) => `${table}=${counts[i]}`).filter((_, i) => counts[i] > 0);
    console.info(
      `[deleteUserCascade] 감사 컬럼 익명화(${deletedUserAuditId(user.id)}): ` +
        `${AUDIT_ANONYMIZED_TABLES.length}개 테이블 검사, 행 갱신 ${touched.length > 0 ? touched.join(", ") : "0건"}`,
    );
  }
}

/**
 * 사용자의 기본 워크스페이스 멤버십을 `tn_user.workspace_id` 와 맞춘다.
 *
 * 워크스페이스가 배정된 사용자는 승인·활성 여부와 무관하게 is_default 멤버십을 정확히 1개 가져야
 * 하고, 로그인 세션이 그 행에서 "지금 선택된 워크스페이스"를 읽는다 — 사용자 행만 바꾸고 멤버십을
 * 두면 그 사용자는 다음 로그인부터 엉뚱한 워크스페이스를 보거나 아무 데도 못 들어간다.
 *
 * **떠난 워크스페이스의 기본 멤버십은 남기지 않고 지운다.** `tn_workspace_member` 는 "지금 구성원인가"의
 * 단일 사실 원천이고, 격리 가드(`assertSameWorkspaceOrSysAdmin`)와 P2 의 워크스페이스 전환 UI 가 같은
 * 행을 읽는다 — 떠난 흔적을 `is_default=false` 로 남기면 "전환해 들어갈 수 있는 워크스페이스"와
 * "예전에 있었던 워크스페이스"가 같은 표현을 갖게 되어, 구 워크스페이스 운영자가 그 사용자를 계속
 * 지배하고(격리 회귀) 나중에는 사용자 자신이 떠난 워크스페이스로 되돌아간다.
 * 재배정 이력이 필요하면 이 테이블이 아니라 별도 이력 기록의 몫이다 (설계 M2-AD-13 · m2-전환설계 §7.5).
 *
 * 지우는 대상은 **기본이었다가 내려가는 행뿐**이다 — 이미 비기본으로 존재하는 다른 멤버십(P2 초대로
 * 생길 게스트 소속)은 건드리지 않는다. 다대다(FR-023)는 그대로 살아 있고, 이 함수의 의미는
 * "홈 워크스페이스를 옮긴다"로 좁게 유지된다.
 *
 * workspaceId 가 null 이면 기존 기본 멤버십을 지우기만 한다 (배정 해제 — 어느 워크스페이스에도 안 속함).
 *
 * `tx` 를 받으면 그 트랜잭션 안에서 실행한다 — 가입처럼 더 큰 원자적 단위의 일부일 때 쓴다.
 * 안 받으면 이 함수가 직접 트랜잭션을 연다.
 */
export async function syncDefaultWorkspaceMembership(
  userId: string,
  workspaceId: number | null,
  actorEmail: string,
  role: string = "member",
  tx?: Prisma.TransactionClient,
): Promise<void> {
  const now = new Date();
  const sync = async (db: Prisma.TransactionClient) => {
    await db.workspaceMember.deleteMany({
      where: {
        user_id: userId,
        is_default: true,
        ...(workspaceId != null ? { NOT: { workspace_id: workspaceId } } : {}),
      },
    });
    if (workspaceId == null) return;
    await db.workspaceMember.upsert({
      where: { workspace_id_user_id: { workspace_id: workspaceId, user_id: userId } },
      create: {
        workspace_id: workspaceId,
        user_id: userId,
        role,
        is_default: true,
        reg_id: actorEmail,
        reg_dt: now,
        mod_id: actorEmail,
        mod_dt: now,
      },
      update: { is_default: true, mod_id: actorEmail, mod_dt: now },
    });
  };

  if (tx) return sync(tx);
  await prisma.$transaction(sync);
}

/**
 * OEM 배포의 **공용** 워크스페이스를 찾는다 — 가입·관리자 사용자생성이 배정할 단 하나의 워크스페이스.
 *
 * OEM 은 "활성 공용 워크스페이스가 정확히 1개"인 단일 고객사 배포다. 개인 워크스페이스
 * (`is_personal`)는 사용자 1명이 소유하는 것이라 이 카운트에서 빠진다 — 빼지 않으면 관리자의
 * 개인 워크스페이스 하나만으로 배포 전체의 가입이 막힌다.
 *
 * 0개·2개 이상은 배포 설정 오류이므로 조용히 아무거나 고르지 않고 큰소리로 실패한다 — 잘못 고르면
 * 신규 사용자가 남의 테넌트로 들어간다. 호출부가 에러 봉투를 각자 만들 수 있게 판정만 돌려준다.
 */
export type OemSharedWorkspace = { id: number } | { error: string };

export async function resolveOemSharedWorkspace(): Promise<OemSharedWorkspace> {
  const shared = await prisma.workspace.findMany({
    where: { use_at: "Y", is_personal: false },
    select: { id: true },
  });
  if (shared.length === 0) return { error: "OEM: 활성 공용 워크스페이스가 없습니다." };
  if (shared.length > 1) return { error: "OEM: 활성 공용 워크스페이스가 2개 이상입니다 (설정 오류)." };
  return { id: shared[0].id };
}

/**
 * "이 워크스페이스에 사용자를 배정해도 되는가" — 클라이언트가 보낸 `workspace_id` 의 경계 검증 (#362).
 *
 * 드롭다운(`app/api/common/system/workspace/options/route.ts`)은 활성 **공용** 워크스페이스만 주지만
 * API 는 그 필터를 안 거친다 — 시스템관리자가 요청 본문에 남의 **개인** 워크스페이스 id 를 넣으면
 * 그대로 배정됐다. 그러면 `syncDefaultWorkspaceMembership` 이 그 워크스페이스에 타인 멤버십을 만들고,
 * 소유자가 탈퇴할 때 `deleteUserCascade` 의 `workspace.deleteMany` 가 FK 위반(P2003)으로 던져
 * **탈퇴 전체가 500** 이 된다. 개인 워크스페이스는 소유자 1명의 것이라 애초에 "배정할 곳"이 아니다.
 *
 * 판정 술어는 드롭다운과 같은 것(`use_at: "Y", is_personal: false`)을 쓴다 — 두 벌로 두면 한쪽만
 * 고쳐져 갈린다. null(미배정)은 허용한다: 워크스페이스 없는 계정은 정상 상태다(승인 전 등).
 * 호출부가 에러 봉투를 각자 만들 수 있게 거부 사유 문자열만 돌려준다 (다른 assert* 와 같은 규약).
 *
 * **타입은 계약이지 검증이 아니다** — 호출부가 넘기는 값은 요청 본문에서 온 `any` 다. Prisma 필터
 * 객체(`{gt:0}`)를 넣으면 `where.id` 가 동등 비교에서 범위 필터로 바뀌어, 존재 확인이 "요청한 그
 * 워크스페이스"가 아니라 "조건에 맞는 아무 워크스페이스"를 찾는다 (개발 DB 실측: `{gt:0}`·`{not:-1}`
 * 둘 다 id=1 에 매칭돼 "허용"이 나왔다, #400 코멘트). 지금은 그 뒤 `user.update` 가
 * `PrismaClientValidationError` 로 거부해 종단이 막히지만, 그건 **Prisma 가 우연히 막아 주는 것**이지
 * 이 가드가 막는 게 아니다 — 쓰기 없이 검사만 하는 경로에 재사용되면 그 우연이 사라진다.
 */
export async function assertAssignableWorkspace(workspaceId: number | null | undefined): Promise<string | null> {
  if (workspaceId == null) return null;
  if (typeof workspaceId !== "number" || !Number.isInteger(workspaceId)) {
    return "배정할 수 없는 워크스페이스입니다.";
  }
  const workspace = await prisma.workspace.findFirst({
    where: { id: workspaceId, use_at: "Y", is_personal: false },
    select: { id: true },
  });
  return workspace ? null : "배정할 수 없는 워크스페이스입니다.";
}

/**
 * 개인 워크스페이스의 코드 — `tn_workspace.workspace_code` 가 VARCHAR(30) UNIQUE 라 uuid 를 그대로 못 쓴다.
 * `'ws-' + 하이픈 없는 사용자 id 앞 27자` = 30자.
 */
const personalWorkspaceCode = (userId: string) => `ws-${userId.replace(/-/g, "").slice(0, 27)}`;

/** 개인 워크스페이스의 이름 — 사용자명이 비어 있으면 이메일을 쓴다. */
const personalWorkspaceName = (name: string | null, email: string) =>
  `${name?.trim() || email}의 워크스페이스`.slice(0, 200);

/**
 * 사용자의 개인 워크스페이스를 보장하고 그 id 를 돌려준다 — 없으면 만들고, 있으면 그대로 쓴다.
 *
 * 코드·이름 규약과 `owner` 멤버십, `is_personal` 표시는 백필 리비전
 * `backend-service/alembic/versions/0005_backfill_workspace_member.py` 와 같다. 두 경로가 다른 모양을
 * 만들면 백필된 계정과 가입한 계정이 갈라진다. 이름의 재료도 리비전과 같이 **저장된 `tn_user.name`**
 * 에서 읽는다. `is_personal` 을 빠뜨리면 이 워크스페이스가 공용으로 세어져 OEM 가입이 막힌다
 * (`resolveOemSharedWorkspace`).
 *
 * 워크스페이스·멤버십 모두 없을 때만 만들고 한 트랜잭션에 묶으므로, 같은 사용자로 여러 번 불러도
 * 결과가 같고 멤버십 없는 워크스페이스가 남지 않는다.
 * **기본 업무 메뉴(`PERSONAL_WORKSPACE_DEFAULT_MENU_IDS`)도 여기서 함께 부여한다** — 없으면
 * 사이드바가 빈다(#251). 이 조각은 백필 리비전 `0005` 에는 없다: 그 리비전이 만든 개인
 * 워크스페이스(가입 흐름 이전 계정)는 여전히 메뉴가 비어 있어 별도 백필이 필요하다.
 * 기본 워크스페이스 지정은 이 함수가 하지 않는다 — `syncDefaultWorkspaceMembership` 의 몫이다.
 *
 * `userId` 로 대상을 찾는다(이메일이 아니라) — 가입 흐름에서 Better Auth 가 이미 만든 사용자의
 * id 를 그대로 넘겨받으므로 별도 이메일 조회·정규화 불일치 여지가 없다.
 * `tx` 규약은 `syncDefaultWorkspaceMembership` 과 같다.
 */
export async function ensurePersonalWorkspace(
  userId: string,
  actorEmail: string,
  tx?: Prisma.TransactionClient,
): Promise<number> {
  const code = personalWorkspaceCode(userId);
  const now = new Date();
  const audit = { reg_dt: now, reg_id: actorEmail, mod_dt: now, mod_id: actorEmail };

  const ensure = async (db: Prisma.TransactionClient) => {
    const user = await db.user.findUniqueOrThrow({ where: { id: userId }, select: { name: true } });

    const workspace = await db.workspace.upsert({
      where: { workspace_code: code },
      create: {
        workspace_code: code,
        workspace_nm: personalWorkspaceName(user.name, actorEmail),
        use_at: "Y",
        is_personal: true,
        ...audit,
      },
      update: {},
      select: { id: true },
    });

    await db.workspaceMember.upsert({
      where: { workspace_id_user_id: { workspace_id: workspace.id, user_id: userId } },
      create: { workspace_id: workspace.id, user_id: userId, role: "owner", is_default: false, ...audit },
      update: {},
    });

    // 기본 업무 메뉴 — 이게 없으면 "권한 메뉴 ∩ 워크스페이스 메뉴" 가 공집합이라 로그인해도
    // 사이드바가 빈다(#251). 실재하고 켜져 있는 메뉴만 넣고, 이미 있으면 건너뛴다 —
    // 이 함수는 몇 번을 불려도 결과가 같아야 한다.
    const defaultMenus = await db.menu.findMany({
      where: { menu_id: { in: PERSONAL_WORKSPACE_DEFAULT_MENU_IDS }, use_at: "Y" },
      select: { menu_id: true },
    });
    if (defaultMenus.length > 0) {
      await db.workspaceMenu.createMany({
        data: defaultMenus.map((menu) => ({ workspace_id: workspace.id, menu_id: menu.menu_id, ...audit })),
        skipDuplicates: true,
      });
    }

    return workspace.id;
  };

  if (tx) return ensure(tx);
  return await prisma.$transaction(ensure);
}

/**
 * "이 사용자가 워크스페이스 W 소속인가"의 **단일 술어** — `tn_user` 조회의 where 조각으로 쓴다.
 *
 * 소속을 적는 자리가 둘이라 술어도 둘로 갈릴 수 있다: 홈 워크스페이스인 스칼라 `tn_user.workspace_id`
 * 와 다대다 `tn_workspace_member`. **둘 중 하나라도 W 를 가리키면 소속**으로 본다. 호출부마다 다른
 * 쪽을 읽으면 같은 사용자가 목록에는 보이는데 단건 조회는 "사용자를 찾을 수 없습니다"가 되고,
 * 워크스페이스를 닫아도 세션이 안 끊기는 식으로 갈라진다 — 실제로 갈렸었다:
 * 멤버십 없이 워크스페이스만 배정된 기존 승인대기·비활성 사용자를 운영자가 다룰 수 없었다.
 *
 * 합집합이라 넓지만, 두 축 모두 "지금 소속"만 담는다 — 홈 이동은 스칼라를 덮어쓰고
 * `syncDefaultWorkspaceMembership` 이 구 기본 멤버십을 지우므로 떠난 워크스페이스는 어느 쪽에도
 * 남지 않는다. 멤버십에 이력 행을 남기려는 변경은 이 술어를 함께 봐야 한다.
 *
 * P2 에서 게스트 초대(`is_default=false` 타인 워크스페이스 멤버십)가 생기면 이 술어는 "관리 대상"
 * 으로는 넓어진다 — 게스트 한 명 때문에 그 워크스페이스 운영자가 계정 전체를 지울 수 있게 된다.
 * 초대 도입 시 파괴적 조작(DELETE)만 홈 워크스페이스 기준으로 좁히는 것이 선결 과제다.
 */
export const workspaceScopedUserWhere = (workspaceId: number) => ({
  OR: [{ workspace_id: workspaceId }, { workspace_members: { some: { workspace_id: workspaceId } } }],
});

/**
 * "이 이메일 문자열이 워크스페이스 W 소속인가"의 **단일 술어** — `th_email_log.to` 처럼 사용자
 * 테이블이 아니라 이메일을 그대로 저장하는 컬럼을 스코핑할 때 쓴다.
 * `workspaceScopedUserWhere` 는 `tn_user` 행을 스코핑하지만, 이건 문자열 컬럼 자체를 스코핑한다는
 * 점이 다르다 — 워크스페이스에 등록은 안 됐지만 도메인이 맞는 수신자(예: 등록 전 직원)도 포함한다
 * (등록 사용자 이메일 목록 OR 워크스페이스 등록 도메인).
 *
 * 라우트마다 이 user+domain 조회를 직접 조립하면 한쪽만 고쳐질 때 갈린다(#221) — 이메일 문자열을
 * 테넌트로 거르는 라우트는 전부 이 함수 하나를 통과한다.
 *
 * 비교는 대소문자 무관(`mode: "insensitive"`, PostgreSQL 지원)으로 한다 — 신규 행은 저장 시점에
 * `normalizeEmail`/도메인 등록 라우트가 소문자로 맞추지만, 그 규칙이 생기기 전에 쓰인 과거 행의
 * 대소문자까지 이 술어 하나로 커버하기 위함이다.
 *
 * 매칭 대상(사용자·도메인)이 하나도 없으면 아무 것도 매칭하지 않는 where 를 돌려준다(fail-closed) —
 * 빈 `OR` 배열은 Prisma 에서 조건 없음(항상 참)으로 풀려 전체 노출로 이어지므로 호출부가 실수로
 * 그리 쓰지 못하게 여기서 막는다.
 *
 * 소속 사용자를 고르는 술어는 `workspaceScopedUserWhere` 하나만 쓴다 — 여기만 스칼라 단독 비교로
 * 두면 멤버십으로만 소속된 사용자의 메일 로그가 그 워크스페이스 운영자에게 안 보인다(#380 과 같은 축).
 */
export async function workspaceScopedEmailWhere(workspaceId: number): Promise<{ OR: any[] } | { to: string }> {
  const [users, domains] = await Promise.all([
    prisma.user.findMany({ where: workspaceScopedUserWhere(workspaceId), select: { email: true } }),
    prisma.workspaceDomain.findMany({ where: { workspace_id: workspaceId }, select: { domain: true } }),
  ]);
  const orConds: any[] = [];
  if (users.length > 0) orConds.push({ to: { in: users.map((u) => u.email), mode: "insensitive" } });
  domains.forEach((d) => orConds.push({ to: { endsWith: `@${d.domain}`, mode: "insensitive" } }));
  return orConds.length > 0 ? { OR: orConds } : { to: "__none__" };
}

/**
 * 대상 사용자가 요청자의 **현재 선택된 워크스페이스**에 속하는지 검증 (시스템관리자는 무조건 통과).
 *
 * 워크스페이스 격리가 필요한 라우트의 공통 가드 — null 이면 통과, 문자열이면 거부 메시지.
 * 존재 자체를 숨겨 타 워크스페이스 사용자 enumeration 을 막는다.
 * 소속 판정은 `workspaceScopedUserWhere` 하나만 쓴다 (목록·세션 무효화와 같은 술어).
 */
export async function assertSameWorkspaceOrSysAdmin(session: any, email: string): Promise<string | null> {
  if (session.user.isSysAdmin) return null;
  // 비시스템관리자인데 워크스페이스가 없으면(미매핑 비정상) 아무도 접근 불가 — fail-closed (null==null 매칭 차단)
  if (session.user.workspaceId == null) return "사용자를 찾을 수 없습니다.";
  const target = await prisma.user.findFirst({
    where: { email, ...workspaceScopedUserWhere(session.user.workspaceId) },
    select: { id: true },
  });
  return target ? null : "사용자를 찾을 수 없습니다.";
}

/**
 * 대상 사용자가 시스템관리자 계정이면 거부 메시지 반환 (운영자가 시스템관리자 계정을 수정/삭제 못 하게).
 * 워크스페이스 격리만으론 같은 워크스페이스 시스템관리자를 막지 못하므로 별도 방어. null 이면 통과.
 */
export async function assertTargetNotSysAdmin(email: string): Promise<string | null> {
  const isSysAdmin = await prisma.authorMember.count({
    where: { author_id: SYS_ADMIN_AUTHOR_ID, user_id: email },
  });
  return isSysAdmin ? "시스템관리자 계정은 시스템관리자만 관리할 수 있습니다." : null;
}

/**
 * 대상 사용자가 시스템관리자(admin) 인지 + 시스템관리자 권한 제거/비활성 시 활성 시스템관리자가 0명이 되는지 검증.
 * - 시스템관리자가 아니면 항상 허용 (null 반환)
 * - 시스템관리자인데 활성 시스템관리자가 1명 이하라면 에러 메시지 반환
 */
export async function checkLastActiveSysAdmin(email: string): Promise<string | null> {
  const targetSysAdmin = await prisma.authorMember.findFirst({
    where: { author_id: SYS_ADMIN_AUTHOR_ID, user_id: email },
    include: { user: { select: { use_at: true, appr_at: true } } },
  });
  if (!targetSysAdmin) return null;
  // 대상이 현재 비활성 상태였다면 카운트에 안 포함되어 있으니 굳이 막을 필요 없음
  if (targetSysAdmin.user?.use_at !== "Y" || targetSysAdmin.user?.appr_at !== "Y") return null;

  const activeCount = await prisma.authorMember.count({
    where: { author_id: SYS_ADMIN_AUTHOR_ID, user: { use_at: "Y", appr_at: "Y" } },
  });
  if (activeCount <= 1) {
    return "시스템관리자 권한에는\n승인된 활성 사용자가 최소 1명 있어야 합니다.";
  }
  return null;
}
