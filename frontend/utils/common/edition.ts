// utils/common/edition.ts
import { env } from "@/env";

/**
 * 제품 에디션 헬퍼 — NEXT_PUBLIC_APP_EDITION 단일 소스.
 *
 * - SAAS: 멀티테넌트. 가입자마다 개인 워크스페이스가 생기고 즉시 활성. 이메일 도메인이 매핑되면
 *         그 공용 워크스페이스 멤버십도 함께 갖고 그쪽이 기본이 된다.
 * - OEM: 단일 워크스페이스 배포. 셀프 가입은 DB 의 유일 활성 **공용** 워크스페이스로 배정되며 항상
 *        승인 대기. 구성원 전원이 그 하나를 함께 쓰는 형태라 개인 워크스페이스를 만들지 않는다
 *        (개인 워크스페이스는 `is_personal` 로 표시돼 공용 카운트에서는 빠진다 — 관리자 개인
 *        워크스페이스가 있어도 가입은 막히지 않는다).
 *
 * 원칙: 이 헬퍼는 "경계" (가입 진입점, 폼 노출) 에서만 호출한다.
 *       공유 훅/컴포넌트/nav 로직 안에는 넣지 않는다 (에디션 비의존 유지).
 */
export const isOEM = () => env.NEXT_PUBLIC_APP_EDITION === "OEM";
export const isSaaS = () => !isOEM();
