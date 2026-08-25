// components/features/Common/System/AdminUser/userCascadeLines.ts
import type { UserDeleteCascadeOut } from "@/schemas/common/adminUser";

/** `WORKSPACE_SCOPED_PUBLIC_TABLES` 의 화면 이름 — 이름이 없는 테이블은 테이블명 그대로 내 숨기지 않는다. */
const WORKSPACE_TABLE_LABELS: Record<string, string> = {
  tn_portfolio: "포트폴리오",
  tn_holding: "보유종목",
  tn_bot: "봇",
  tn_backtest_run: "백테스트 실행",
  tn_watchlist: "관심종목",
  tn_research_document: "리서치 문서",
  tn_scheduler: "스케줄러",
  tn_scheduler_member: "스케줄러 구성원 배정",
  tn_nav: "자산 시계열",
};

const countParts = (entries: [string, number][]): string[] =>
  entries.filter(([, count]) => count > 0).map(([label, count]) => `${label} ${count}건`);

/** 다른 화면과 같은 규약 — 「X N건, Y N건이 함께 삭제됩니다.」 0건인 항목은 적지 않는다. */
export const buildUserCascadeLines = (cascade: UserDeleteCascadeOut): string[] | undefined => {
  const lines: string[] = [];

  const userParts = countParts([
    ["권한 배정", cascade.author_member_count],
    ["워크스페이스 소속", cascade.workspace_member_count],
    ["세션", cascade.session_count],
    ["대화 이력", cascade.chat_history_count],
    ["메일 발송 로그", cascade.email_log_count],
    ["주간 활동요약 수신 등록", cascade.scheduler_member_count],
  ]);
  if (userParts.length > 0) lines.push(`${userParts.join(", ")}이 함께 삭제됩니다.`);

  const workspaces = cascade.owned_personal_workspaces;
  if (workspaces.length > 0) {
    const names = workspaces.map((w) => w.workspace_nm).join(", ");
    const head = `소유한 개인 워크스페이스 ${workspaces.length}개(${names})`;
    // 이름이 있는 테이블은 라벨 순서(사람이 읽는 순)로, 이름 없는 새 테이블은 그 뒤에 테이블명 그대로.
    const counts = cascade.owned_workspace_counts;
    const tables = [
      ...Object.keys(WORKSPACE_TABLE_LABELS).filter((table) => table in counts),
      ...Object.keys(counts).filter((table) => !(table in WORKSPACE_TABLE_LABELS)),
    ];
    const assetParts = countParts(tables.map((table) => [WORKSPACE_TABLE_LABELS[table] ?? table, counts[table]]));
    lines.push(
      assetParts.length > 0
        ? `${head}와 그 안의 ${assetParts.join(", ")}이 함께 삭제됩니다.`
        : `${head}가 함께 삭제됩니다.`,
    );
  }

  return lines.length > 0 ? lines : undefined;
};
