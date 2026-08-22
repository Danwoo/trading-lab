// utils/common/api/client.ts
import axios, { AxiosRequestConfig } from "axios";

/**
 * Better Auth 클라이언트에서 JWT 토큰 반환
 * - 클라이언트: authClient.$fetch로 토큰 요청
 * - 서버사이드: null
 */
export const getClientToken = async (): Promise<string | null> => {
  if (typeof window === "undefined") return null;

  try {
    const { authClient } = await import("@/lib/auth/auth-client");
    const response = await authClient.$fetch("/token", { method: "GET" });
    return (response.data as any)?.token ?? null;
  } catch (error) {
    console.warn("Better Auth token load failed:", error);
    return null;
  }
};

/**
 * 공통 API 호출 헬퍼
 * Route Handler: token 생략
 * 외부 API: token 전달
 */
interface ApiCallConfig extends Omit<AxiosRequestConfig, "headers"> {
  token?: string | null;
  headers?: Record<string, any>;
  onUploadProgress?: (progressEvent: any) => void;
  /**
   * 기본값 false — 백엔드가 `{success:false}` 를 응답하면 `null` 을 돌려준다(호출부 137곳의
   * 기존 계약). `true` 로 넘기면 그 대신 `ApiCallFailure` 를 던진다 — 호출부가 "서버 실패"와
   * "정상 응답인데 0건"을 구분해야 할 때 쓴다. 기존 계약을 깨지 않는 opt-in.
   *
   * **격자를 타는 목록은 이 옵션이 필요 없다** — `useServerTable` 이 `null` 응답을 실패로 읽어
   * `error` 상태로 세운다([#332](https://github.com/Danwoo/trading-lab/issues/332)).
   */
  throwOnFailure?: boolean;
}

/** `apiCall(..., { throwOnFailure: true })` 가 `{success:false}` 응답에서 던지는 예외. */
export class ApiCallFailure extends Error {
  constructor(message = "서버 요청이 실패했습니다.") {
    super(message);
    this.name = "ApiCallFailure";
  }
}

export async function apiCall<T>(url: string, options: ApiCallConfig = {}): Promise<T | null> {
  const { throwOnFailure, ...requestOptions } = options;
  const isFormData = requestOptions.data instanceof FormData;

  const response = await axios({
    url,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(requestOptions.token && { Authorization: `Bearer ${requestOptions.token}` }),
      ...requestOptions.headers,
    },
    onUploadProgress: requestOptions.onUploadProgress,
    ...requestOptions,
  });

  // 백엔드 응답 형식: { success: boolean, data: T }
  if (typeof response.data === "object" && "success" in response.data) {
    if (response.data.success) return response.data.data;
    if (throwOnFailure) throw new ApiCallFailure();
    return null;
  }

  return response.data;
}

/**
 * 외부 서비스 Base URL 생성
 * serviceUrl이 있으면 그대로 사용, 없으면 현재 접속 도메인 + servicePath로 생성
 */
export function getExternalBaseUrl(serviceUrl: string | undefined, servicePath: string): string {
  if (serviceUrl) return serviceUrl;
  return `${window.location.protocol}//${window.location.host}${servicePath}`;
}

export function getWebSocketBaseUrl(serviceUrl: string | undefined, servicePath: string): string {
  if (serviceUrl) return serviceUrl;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${servicePath}`;
}

/**
 * 쿼리 파라미터 정제
 * null/undefined 제거 + 문자열 변환
 */
export function sanitizeParams(params: Record<string, any>): Record<string, string> {
  const sanitized: Record<string, string> = {};
  Object.entries(params)
    .filter(([, value]) => value != null)
    .forEach(([key, value]) => {
      sanitized[key] = String(value);
    });
  return sanitized;
}
