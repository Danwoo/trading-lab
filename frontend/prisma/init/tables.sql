-- ============================================================================
-- Prisma Complete Database Generator (PostgreSQL)
-- ============================================================================

-- ============================================================================
-- 0. 스키마 (frontend — Prisma 소유. public 은 파이썬 서비스 소유라 건드리지 않는다)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS "frontend";
SET search_path TO "frontend";

-- ============================================================================
-- 1. 기존 테이블 삭제 (CASCADE — 의존 FK 함께 정리)
-- ============================================================================

DROP TABLE IF EXISTS "tn_user" CASCADE;
DROP TABLE IF EXISTS "tn_workspace" CASCADE;
DROP TABLE IF EXISTS "tn_workspace_member" CASCADE;
DROP TABLE IF EXISTS "tn_workspace_menu" CASCADE;
DROP TABLE IF EXISTS "tn_workspace_domain" CASCADE;
DROP TABLE IF EXISTS "ba_session" CASCADE;
DROP TABLE IF EXISTS "ba_account" CASCADE;
DROP TABLE IF EXISTS "ba_verification" CASCADE;
DROP TABLE IF EXISTS "tn_author" CASCADE;
DROP TABLE IF EXISTS "tn_author_member" CASCADE;
DROP TABLE IF EXISTS "tn_menu" CASCADE;
DROP TABLE IF EXISTS "tn_author_menu" CASCADE;
DROP TABLE IF EXISTS "tc_group_code" CASCADE;
DROP TABLE IF EXISTS "tc_code" CASCADE;
DROP TABLE IF EXISTS "ai_chat_history" CASCADE;
DROP TABLE IF EXISTS "th_email_log" CASCADE;

-- ============================================================================
-- 2. 테이블 생성
-- ============================================================================

-- Create table tn_user
CREATE TABLE "tn_user" (
    "id" VARCHAR(36) NOT NULL,
    "email" VARCHAR(100) NOT NULL UNIQUE,
    "name" VARCHAR(100) NULL,
    "dept" VARCHAR(50) NULL,
    "workspace_id" INTEGER NULL,
    "use_at" VARCHAR(5) NOT NULL DEFAULT 'Y',
    "appr_at" VARCHAR(5) NOT NULL DEFAULT 'N',
    "emailVerified" BOOLEAN NOT NULL DEFAULT FALSE,
    "image" VARCHAR(500) NULL,
    "reg_id" VARCHAR(100) NULL,
    "reg_dt" TIMESTAMP(3) NULL,
    "reg_ip" VARCHAR(45) NULL,
    "reg_pid" VARCHAR(30) NULL,
    "mod_id" VARCHAR(100) NULL,
    "mod_dt" TIMESTAMP(3) NULL,
    "mod_ip" VARCHAR(45) NULL,
    "mod_pid" VARCHAR(30) NULL,
    CONSTRAINT "pk_tn_user" PRIMARY KEY ("id")
);

-- Create table tn_workspace
CREATE TABLE "tn_workspace" (
    "id" SERIAL NOT NULL,
    "workspace_code" VARCHAR(30) NOT NULL UNIQUE,
    "workspace_nm" VARCHAR(200) NOT NULL,
    "use_at" VARCHAR(5) NOT NULL DEFAULT 'Y',
    "is_personal" BOOLEAN NOT NULL DEFAULT FALSE,
    "reg_dt" TIMESTAMP(3) NULL,
    "reg_id" VARCHAR(100) NULL,
    "mod_dt" TIMESTAMP(3) NULL,
    "mod_id" VARCHAR(100) NULL,
    CONSTRAINT "pk_tn_workspace" PRIMARY KEY ("id")
);

-- Create table tn_workspace_member
CREATE TABLE "tn_workspace_member" (
    "workspace_id" INTEGER NOT NULL,
    "user_id" VARCHAR(36) NOT NULL,
    "role" VARCHAR(20) NOT NULL DEFAULT 'member',
    "is_default" BOOLEAN NOT NULL DEFAULT FALSE,
    "reg_dt" TIMESTAMP(3) NULL,
    "reg_id" VARCHAR(100) NULL,
    "mod_dt" TIMESTAMP(3) NULL,
    "mod_id" VARCHAR(100) NULL,
    CONSTRAINT "pk_tn_workspace_member" PRIMARY KEY ("workspace_id", "user_id")
);

-- Create table tn_workspace_menu
CREATE TABLE "tn_workspace_menu" (
    "workspace_id" INTEGER NOT NULL,
    "menu_id" VARCHAR(20) NOT NULL,
    "reg_dt" TIMESTAMP(3) NULL,
    "reg_id" VARCHAR(100) NULL,
    "mod_dt" TIMESTAMP(3) NULL,
    "mod_id" VARCHAR(100) NULL,
    CONSTRAINT "pk_tn_workspace_menu" PRIMARY KEY ("workspace_id", "menu_id")
);

-- Create table tn_workspace_domain
CREATE TABLE "tn_workspace_domain" (
    "domain" VARCHAR(100) NOT NULL,
    "workspace_id" INTEGER NOT NULL,
    "reg_dt" TIMESTAMP(3) NULL,
    "reg_id" VARCHAR(100) NULL,
    "mod_dt" TIMESTAMP(3) NULL,
    "mod_id" VARCHAR(100) NULL,
    CONSTRAINT "pk_tn_workspace_domain" PRIMARY KEY ("domain")
);

-- Create table ba_session
CREATE TABLE "ba_session" (
    "id" VARCHAR(36) NOT NULL,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "token" VARCHAR(500) NOT NULL UNIQUE,
    "createdAt" TIMESTAMP(3) NOT NULL,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "ipAddress" VARCHAR(45) NULL,
    "userAgent" VARCHAR(500) NULL,
    "userId" VARCHAR(36) NOT NULL,
    "authorId" VARCHAR(20) NULL,
    "workspaceId" INTEGER NULL,
    CONSTRAINT "pk_ba_session" PRIMARY KEY ("id")
);

-- Create table ba_account
CREATE TABLE "ba_account" (
    "id" VARCHAR(36) NOT NULL,
    "accountId" VARCHAR(100) NOT NULL,
    "providerId" VARCHAR(100) NOT NULL,
    "userId" VARCHAR(36) NOT NULL,
    "accessToken" VARCHAR(500) NULL,
    "refreshToken" VARCHAR(500) NULL,
    "idToken" TEXT NULL,
    "accessTokenExpiresAt" TIMESTAMP(3) NULL,
    "refreshTokenExpiresAt" TIMESTAMP(3) NULL,
    "scope" VARCHAR(500) NULL,
    "password" VARCHAR(255) NULL,
    "createdAt" TIMESTAMP(3) NOT NULL,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "pk_ba_account" PRIMARY KEY ("id")
);

-- Create table ba_verification
CREATE TABLE "ba_verification" (
    "id" VARCHAR(36) NOT NULL,
    "identifier" VARCHAR(200) NOT NULL,
    "value" TEXT NOT NULL,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "createdAt" TIMESTAMP(3) NULL,
    "updatedAt" TIMESTAMP(3) NULL,
    CONSTRAINT "pk_ba_verification" PRIMARY KEY ("id")
);

-- Create table tn_author
CREATE TABLE "tn_author" (
    "author_id" VARCHAR(20) NOT NULL,
    "author_nm" VARCHAR(200) NOT NULL,
    "reg_dt" TIMESTAMP(3) NULL,
    "reg_id" VARCHAR(100) NULL,
    "mod_dt" TIMESTAMP(3) NULL,
    "mod_id" VARCHAR(100) NULL,
    CONSTRAINT "pk_tn_author" PRIMARY KEY ("author_id")
);

-- Create table tn_author_member
CREATE TABLE "tn_author_member" (
    "author_id" VARCHAR(20) NOT NULL,
    "user_id" VARCHAR(100) NOT NULL,
    "reg_dt" TIMESTAMP(3) NULL,
    "reg_id" VARCHAR(100) NULL,
    "mod_dt" TIMESTAMP(3) NULL,
    "mod_id" VARCHAR(100) NULL,
    CONSTRAINT "pk_tn_author_member" PRIMARY KEY ("author_id", "user_id")
);

-- Create table tn_menu
CREATE TABLE "tn_menu" (
    "menu_id" VARCHAR(20) NOT NULL,
    "menu_nm" VARCHAR(200) NOT NULL,
    "upper_menu_id" VARCHAR(20) NULL,
    "menu_level" INTEGER NULL DEFAULT 1,
    "sort_ordr" INTEGER NULL DEFAULT 1,
    "url" VARCHAR(400) NULL,
    "use_at" VARCHAR(5) NULL DEFAULT 'Y',
    "icon" VARCHAR(50) NULL,
    "reg_dt" TIMESTAMP(3) NULL,
    "reg_id" VARCHAR(100) NULL,
    "mod_dt" TIMESTAMP(3) NULL,
    "mod_id" VARCHAR(100) NULL,
    CONSTRAINT "pk_tn_menu" PRIMARY KEY ("menu_id")
);

-- Create table tn_author_menu
CREATE TABLE "tn_author_menu" (
    "author_id" VARCHAR(20) NOT NULL,
    "menu_id" VARCHAR(20) NOT NULL,
    "reg_dt" TIMESTAMP(3) NULL,
    "reg_id" VARCHAR(100) NULL,
    "mod_dt" TIMESTAMP(3) NULL,
    "mod_id" VARCHAR(100) NULL,
    CONSTRAINT "pk_tn_author_menu" PRIMARY KEY ("author_id", "menu_id")
);

-- Create table tc_group_code
CREATE TABLE "tc_group_code" (
    "group_code" VARCHAR(5) NOT NULL,
    "group_code_nm" VARCHAR(200) NOT NULL,
    "group_code_dc" VARCHAR(200) NULL,
    "use_at" VARCHAR(5) NOT NULL DEFAULT 'Y',
    "reg_dt" TIMESTAMP(3) NULL,
    "reg_id" VARCHAR(100) NULL,
    "mod_dt" TIMESTAMP(3) NULL,
    "mod_id" VARCHAR(100) NULL,
    CONSTRAINT "pk_tc_group_code" PRIMARY KEY ("group_code")
);

-- Create table tc_code
CREATE TABLE "tc_code" (
    "group_code" VARCHAR(5) NOT NULL,
    "code" VARCHAR(20) NOT NULL,
    "code_nm" VARCHAR(200) NOT NULL,
    "code_nm_eng" VARCHAR(200) NULL,
    "code_dc" VARCHAR(200) NULL,
    "sort_ordr" INTEGER NULL DEFAULT 1,
    "use_at" VARCHAR(5) NOT NULL DEFAULT 'Y',
    "reg_dt" TIMESTAMP(3) NULL,
    "reg_id" VARCHAR(100) NULL,
    "mod_dt" TIMESTAMP(3) NULL,
    "mod_id" VARCHAR(100) NULL,
    CONSTRAINT "pk_tc_code" PRIMARY KEY ("group_code", "code")
);

-- Create table ai_chat_history
CREATE TABLE "ai_chat_history" (
    "id" SERIAL NOT NULL,
    "email" VARCHAR(100) NOT NULL,
    "gid" BIGINT NOT NULL,
    "sort" INTEGER NOT NULL,
    "question" TEXT NOT NULL,
    "answer" TEXT NULL,
    "flag" INTEGER NOT NULL DEFAULT 1,
    "reg_dt" TIMESTAMP(3) NULL,
    "reg_id" VARCHAR(100) NULL,
    "mod_dt" TIMESTAMP(3) NULL,
    "mod_id" VARCHAR(100) NULL,
    CONSTRAINT "pk_ai_chat_history" PRIMARY KEY ("id")
);

-- Create table th_email_log
CREATE TABLE "th_email_log" (
    "id" SERIAL NOT NULL,
    "to" VARCHAR(100) NOT NULL,
    "subject" VARCHAR(200) NOT NULL,
    "status" VARCHAR(10) NOT NULL,
    "error_msg" VARCHAR(500) NULL,
    "reg_dt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "pk_th_email_log" PRIMARY KEY ("id")
);


-- ============================================================================
-- 3. 외래키 생성
-- ============================================================================

-- Add foreign key for tn_user.workspace_id
ALTER TABLE "tn_user" ADD CONSTRAINT "fk_tn_user_workspace_id" FOREIGN KEY ("workspace_id") REFERENCES "tn_workspace" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- Add foreign key for tn_workspace_member.workspace_id
ALTER TABLE "tn_workspace_member" ADD CONSTRAINT "fk_tn_workspace_member_workspace_id" FOREIGN KEY ("workspace_id") REFERENCES "tn_workspace" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Add foreign key for tn_workspace_member.user_id
ALTER TABLE "tn_workspace_member" ADD CONSTRAINT "fk_tn_workspace_member_user_id" FOREIGN KEY ("user_id") REFERENCES "tn_user" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Add foreign key for tn_workspace_menu.workspace_id
ALTER TABLE "tn_workspace_menu" ADD CONSTRAINT "fk_tn_workspace_menu_workspace_id" FOREIGN KEY ("workspace_id") REFERENCES "tn_workspace" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Add foreign key for tn_workspace_domain.workspace_id
ALTER TABLE "tn_workspace_domain" ADD CONSTRAINT "fk_tn_workspace_domain_workspace_id" FOREIGN KEY ("workspace_id") REFERENCES "tn_workspace" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Add foreign key for ba_session.userId
ALTER TABLE "ba_session" ADD CONSTRAINT "fk_ba_session_userId" FOREIGN KEY ("userId") REFERENCES "tn_user" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Add foreign key for ba_account.userId
ALTER TABLE "ba_account" ADD CONSTRAINT "fk_ba_account_userId" FOREIGN KEY ("userId") REFERENCES "tn_user" ("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Add foreign key for tn_author_member.author_id
ALTER TABLE "tn_author_member" ADD CONSTRAINT "fk_tn_author_member_author_id" FOREIGN KEY ("author_id") REFERENCES "tn_author" ("author_id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Add foreign key for tn_author_member.user_id
ALTER TABLE "tn_author_member" ADD CONSTRAINT "fk_tn_author_member_user_id" FOREIGN KEY ("user_id") REFERENCES "tn_user" ("email") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Add foreign key for tn_menu.upper_menu_id
ALTER TABLE "tn_menu" ADD CONSTRAINT "fk_tn_menu_upper_menu_id" FOREIGN KEY ("upper_menu_id") REFERENCES "tn_menu" ("menu_id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- Add foreign key for tn_author_menu.author_id
ALTER TABLE "tn_author_menu" ADD CONSTRAINT "fk_tn_author_menu_author_id" FOREIGN KEY ("author_id") REFERENCES "tn_author" ("author_id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Add foreign key for tn_author_menu.menu_id
ALTER TABLE "tn_author_menu" ADD CONSTRAINT "fk_tn_author_menu_menu_id" FOREIGN KEY ("menu_id") REFERENCES "tn_menu" ("menu_id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Add foreign key for tc_code.group_code
ALTER TABLE "tc_code" ADD CONSTRAINT "fk_tc_code_group_code" FOREIGN KEY ("group_code") REFERENCES "tc_group_code" ("group_code") ON DELETE RESTRICT ON UPDATE CASCADE;


-- ============================================================================
-- 4. 인덱스 생성
-- ============================================================================

-- Add index for tn_workspace_member.user_id
CREATE INDEX "ix_tn_workspace_member_user_id" ON "tn_workspace_member" ("user_id");

-- Add index for tn_workspace_domain.workspace_id
CREATE INDEX "ix_tn_workspace_domain_workspace_id" ON "tn_workspace_domain" ("workspace_id");

-- Add index for ba_session.userId
CREATE INDEX "ix_ba_session_userId" ON "ba_session" ("userId");

-- Add index for ba_account.userId
CREATE INDEX "ix_ba_account_userId" ON "ba_account" ("userId");

-- Add index for ba_account.providerId, accountId
CREATE UNIQUE INDEX "ix_ba_account_providerId_accountId" ON "ba_account" ("providerId", "accountId");

-- Add index for tn_menu.upper_menu_id, sort_ordr
CREATE INDEX "ix_tn_menu_upper_menu_id_sort_ordr" ON "tn_menu" ("upper_menu_id", "sort_ordr");

-- Add index for ai_chat_history.email, gid, flag, sort
CREATE INDEX "ix_ai_chat_history_email_gid_flag_sort" ON "ai_chat_history" ("email", "gid", "flag", "sort");


-- ============================================================================
-- 5. 주석 (COMMENT ON)
-- ============================================================================

-- Add comments for tn_user
COMMENT ON TABLE "tn_user" IS '사용자';
COMMENT ON COLUMN "tn_user"."id" IS '사용자 ID';
COMMENT ON COLUMN "tn_user"."email" IS '이메일';
COMMENT ON COLUMN "tn_user"."name" IS '사용자명';
COMMENT ON COLUMN "tn_user"."dept" IS '부서';
COMMENT ON COLUMN "tn_user"."workspace_id" IS '워크스페이스 ID';
COMMENT ON COLUMN "tn_user"."use_at" IS '사용여부';
COMMENT ON COLUMN "tn_user"."appr_at" IS '승인여부';
COMMENT ON COLUMN "tn_user"."emailVerified" IS '이메일 인증 여부';
COMMENT ON COLUMN "tn_user"."image" IS '프로필 이미지';
COMMENT ON COLUMN "tn_user"."reg_id" IS '생성자 ID';
COMMENT ON COLUMN "tn_user"."reg_dt" IS '생성일시';
COMMENT ON COLUMN "tn_user"."reg_ip" IS '생성 IP';
COMMENT ON COLUMN "tn_user"."reg_pid" IS '생성 프로그램 ID';
COMMENT ON COLUMN "tn_user"."mod_id" IS '수정자 ID';
COMMENT ON COLUMN "tn_user"."mod_dt" IS '수정일시';
COMMENT ON COLUMN "tn_user"."mod_ip" IS '수정 IP';
COMMENT ON COLUMN "tn_user"."mod_pid" IS '수정 프로그램 ID';

-- Add comments for tn_workspace
COMMENT ON TABLE "tn_workspace" IS '워크스페이스';
COMMENT ON COLUMN "tn_workspace"."id" IS '워크스페이스 ID';
COMMENT ON COLUMN "tn_workspace"."workspace_code" IS '워크스페이스 코드';
COMMENT ON COLUMN "tn_workspace"."workspace_nm" IS '워크스페이스명';
COMMENT ON COLUMN "tn_workspace"."use_at" IS '사용여부';
COMMENT ON COLUMN "tn_workspace"."is_personal" IS '개인 워크스페이스 여부 (사용자 1명 소유 — 공용 워크스페이스 수를 세는 곳에서 제외된다)';
COMMENT ON COLUMN "tn_workspace"."reg_dt" IS '생성일시';
COMMENT ON COLUMN "tn_workspace"."reg_id" IS '생성자 ID';
COMMENT ON COLUMN "tn_workspace"."mod_dt" IS '수정일시';
COMMENT ON COLUMN "tn_workspace"."mod_id" IS '수정자 ID';

-- Add comments for tn_workspace_member
COMMENT ON TABLE "tn_workspace_member" IS '워크스페이스 구성원 (사용자↔워크스페이스 다대다)';
COMMENT ON COLUMN "tn_workspace_member"."workspace_id" IS '워크스페이스 ID';
COMMENT ON COLUMN "tn_workspace_member"."user_id" IS '사용자 ID';
COMMENT ON COLUMN "tn_workspace_member"."role" IS '구성원 역할 (owner|member|viewer)';
COMMENT ON COLUMN "tn_workspace_member"."is_default" IS '로그인 시 선택되는 기본 워크스페이스 여부';
COMMENT ON COLUMN "tn_workspace_member"."reg_dt" IS '생성일시';
COMMENT ON COLUMN "tn_workspace_member"."reg_id" IS '생성자 ID';
COMMENT ON COLUMN "tn_workspace_member"."mod_dt" IS '수정일시';
COMMENT ON COLUMN "tn_workspace_member"."mod_id" IS '수정자 ID';

-- Add comments for tn_workspace_menu
COMMENT ON TABLE "tn_workspace_menu" IS '워크스페이스별 메뉴';
COMMENT ON COLUMN "tn_workspace_menu"."workspace_id" IS '워크스페이스 ID';
COMMENT ON COLUMN "tn_workspace_menu"."menu_id" IS '메뉴 ID';
COMMENT ON COLUMN "tn_workspace_menu"."reg_dt" IS '생성일시';
COMMENT ON COLUMN "tn_workspace_menu"."reg_id" IS '생성자 ID';
COMMENT ON COLUMN "tn_workspace_menu"."mod_dt" IS '수정일시';
COMMENT ON COLUMN "tn_workspace_menu"."mod_id" IS '수정자 ID';

-- Add comments for tn_workspace_domain
COMMENT ON TABLE "tn_workspace_domain" IS '워크스페이스 이메일 도메인 매핑';
COMMENT ON COLUMN "tn_workspace_domain"."domain" IS '이메일 도메인';
COMMENT ON COLUMN "tn_workspace_domain"."workspace_id" IS '워크스페이스 ID';
COMMENT ON COLUMN "tn_workspace_domain"."reg_dt" IS '생성일시';
COMMENT ON COLUMN "tn_workspace_domain"."reg_id" IS '생성자 ID';
COMMENT ON COLUMN "tn_workspace_domain"."mod_dt" IS '수정일시';
COMMENT ON COLUMN "tn_workspace_domain"."mod_id" IS '수정자 ID';

-- Add comments for ba_session
COMMENT ON TABLE "ba_session" IS '인증 세션';
COMMENT ON COLUMN "ba_session"."workspaceId" IS '지금 선택된 워크스페이스 (소속이 아니라 선택 — 다대다에서 하나를 가리킨다)';

-- Add comments for ba_account
COMMENT ON TABLE "ba_account" IS '인증 계정';

-- Add comments for ba_verification
COMMENT ON TABLE "ba_verification" IS '인증 토큰';

-- Add comments for tn_author
COMMENT ON TABLE "tn_author" IS '권한';
COMMENT ON COLUMN "tn_author"."author_id" IS '권한 ID';
COMMENT ON COLUMN "tn_author"."author_nm" IS '권한명';
COMMENT ON COLUMN "tn_author"."reg_dt" IS '생성일시';
COMMENT ON COLUMN "tn_author"."reg_id" IS '생성자 ID';
COMMENT ON COLUMN "tn_author"."mod_dt" IS '수정일시';
COMMENT ON COLUMN "tn_author"."mod_id" IS '수정자 ID';

-- Add comments for tn_author_member
COMMENT ON TABLE "tn_author_member" IS '권한별 사용자';
COMMENT ON COLUMN "tn_author_member"."author_id" IS '권한 ID';
COMMENT ON COLUMN "tn_author_member"."user_id" IS '사용자 ID';
COMMENT ON COLUMN "tn_author_member"."reg_dt" IS '생성일시';
COMMENT ON COLUMN "tn_author_member"."reg_id" IS '생성자 ID';
COMMENT ON COLUMN "tn_author_member"."mod_dt" IS '수정일시';
COMMENT ON COLUMN "tn_author_member"."mod_id" IS '수정자 ID';

-- Add comments for tn_menu
COMMENT ON TABLE "tn_menu" IS '메뉴';
COMMENT ON COLUMN "tn_menu"."menu_id" IS '메뉴 ID';
COMMENT ON COLUMN "tn_menu"."menu_nm" IS '메뉴명';
COMMENT ON COLUMN "tn_menu"."upper_menu_id" IS '상위 메뉴 ID';
COMMENT ON COLUMN "tn_menu"."menu_level" IS '메뉴 레벨';
COMMENT ON COLUMN "tn_menu"."sort_ordr" IS '정렬순서';
COMMENT ON COLUMN "tn_menu"."url" IS 'URL';
COMMENT ON COLUMN "tn_menu"."use_at" IS '사용여부';
COMMENT ON COLUMN "tn_menu"."icon" IS '아이콘';
COMMENT ON COLUMN "tn_menu"."reg_dt" IS '생성일시';
COMMENT ON COLUMN "tn_menu"."reg_id" IS '생성자 ID';
COMMENT ON COLUMN "tn_menu"."mod_dt" IS '수정일시';
COMMENT ON COLUMN "tn_menu"."mod_id" IS '수정자 ID';

-- Add comments for tn_author_menu
COMMENT ON TABLE "tn_author_menu" IS '권한별 메뉴';
COMMENT ON COLUMN "tn_author_menu"."author_id" IS '권한 ID';
COMMENT ON COLUMN "tn_author_menu"."menu_id" IS '메뉴 ID';
COMMENT ON COLUMN "tn_author_menu"."reg_dt" IS '생성일시';
COMMENT ON COLUMN "tn_author_menu"."reg_id" IS '생성자 ID';
COMMENT ON COLUMN "tn_author_menu"."mod_dt" IS '수정일시';
COMMENT ON COLUMN "tn_author_menu"."mod_id" IS '수정자 ID';

-- Add comments for tc_group_code
COMMENT ON TABLE "tc_group_code" IS '그룹코드';
COMMENT ON COLUMN "tc_group_code"."group_code" IS '그룹코드';
COMMENT ON COLUMN "tc_group_code"."group_code_nm" IS '그룹코드명';
COMMENT ON COLUMN "tc_group_code"."group_code_dc" IS '그룹코드 설명';
COMMENT ON COLUMN "tc_group_code"."use_at" IS '사용여부';
COMMENT ON COLUMN "tc_group_code"."reg_dt" IS '생성일시';
COMMENT ON COLUMN "tc_group_code"."reg_id" IS '생성자 ID';
COMMENT ON COLUMN "tc_group_code"."mod_dt" IS '수정일시';
COMMENT ON COLUMN "tc_group_code"."mod_id" IS '수정자 ID';

-- Add comments for tc_code
COMMENT ON TABLE "tc_code" IS '상세코드';
COMMENT ON COLUMN "tc_code"."group_code" IS '그룹코드';
COMMENT ON COLUMN "tc_code"."code" IS '코드';
COMMENT ON COLUMN "tc_code"."code_nm" IS '코드명';
COMMENT ON COLUMN "tc_code"."code_nm_eng" IS '영문 코드명';
COMMENT ON COLUMN "tc_code"."code_dc" IS '코드 설명';
COMMENT ON COLUMN "tc_code"."sort_ordr" IS '정렬순서';
COMMENT ON COLUMN "tc_code"."use_at" IS '사용여부';
COMMENT ON COLUMN "tc_code"."reg_dt" IS '생성일시';
COMMENT ON COLUMN "tc_code"."reg_id" IS '생성자 ID';
COMMENT ON COLUMN "tc_code"."mod_dt" IS '수정일시';
COMMENT ON COLUMN "tc_code"."mod_id" IS '수정자 ID';

-- Add comments for ai_chat_history
COMMENT ON TABLE "ai_chat_history" IS 'AI 챗 대화 이력 (멀티턴)';
COMMENT ON COLUMN "ai_chat_history"."id" IS '이력 ID';
COMMENT ON COLUMN "ai_chat_history"."email" IS '사용자 이메일 (tn_user.email)';
COMMENT ON COLUMN "ai_chat_history"."gid" IS '대화 세션 ID (프론트가 Date.now() 로 생성 — int4 범위를 넘어 BigInt)';
COMMENT ON COLUMN "ai_chat_history"."sort" IS '대화 내 순서 (오름차순 = 시간순)';
COMMENT ON COLUMN "ai_chat_history"."question" IS '사용자 질문';
COMMENT ON COLUMN "ai_chat_history"."answer" IS 'AI 답변 (스트리밍 중·중단 시 비어 있을 수 있음)';
COMMENT ON COLUMN "ai_chat_history"."flag" IS '유효 플래그 (1=유효, 그 외=조회 제외)';
COMMENT ON COLUMN "ai_chat_history"."reg_dt" IS '생성일시';
COMMENT ON COLUMN "ai_chat_history"."reg_id" IS '생성자 ID';
COMMENT ON COLUMN "ai_chat_history"."mod_dt" IS '수정일시';
COMMENT ON COLUMN "ai_chat_history"."mod_id" IS '수정자 ID';

-- Add comments for th_email_log
COMMENT ON TABLE "th_email_log" IS '이메일 발송 로그';
COMMENT ON COLUMN "th_email_log"."id" IS '로그 ID';
COMMENT ON COLUMN "th_email_log"."to" IS '수신자 이메일';
COMMENT ON COLUMN "th_email_log"."subject" IS '제목';
COMMENT ON COLUMN "th_email_log"."status" IS '발송 상태';
COMMENT ON COLUMN "th_email_log"."error_msg" IS '에러 메시지';
COMMENT ON COLUMN "th_email_log"."reg_dt" IS '발송일시';
