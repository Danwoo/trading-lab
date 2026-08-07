import { CreateOut, UpdateOut, DeleteOut, MessageOut } from "@/schemas/common/types";
import {
  SchedulerCreateInSchema,
  SchedulerUpdateInSchema,
  SchedulersOut,
  SchedulerOut,
  SchedulerMembersOut,
} from "@/schemas/scheduler/scheduler";
import { apiCall } from "@/utils/common/api/client";
import { handleZodValidationError, validateWithZod } from "@/lib/zod/validation";

const BASE_URL = "/api/external/devactivity/scheduler";

/**
 * 스케줄러 목록 조회
 */
export const selectSchedulerList = async (params: any): Promise<SchedulersOut | null> => {
  const queryParams: Record<string, any> = { ...params };

  if (queryParams.filter) queryParams.filter = JSON.stringify(queryParams.filter);
  if (queryParams.sort) queryParams.sort = JSON.stringify(queryParams.sort);

  return apiCall<SchedulersOut>(BASE_URL, {
    method: "GET",
    params: queryParams,
  });
};

/**
 * 스케줄러 단일 조회
 */
export const selectScheduler = async (data: any): Promise<SchedulerOut | null> => {
  const { scheduler_id } = data;

  return apiCall<SchedulerOut>(`${BASE_URL}/${scheduler_id}`, {
    method: "GET",
  });
};

/**
 * 스케줄러 등록
 */
export const createScheduler = async (data: any): Promise<CreateOut | null> => {
  try {
    const validatedData = validateWithZod(SchedulerCreateInSchema, data);

    return apiCall<CreateOut>(BASE_URL, {
      method: "POST",
      data: validatedData,
    });
  } catch (error) {
    handleZodValidationError(error);
  }
};

/**
 * 스케줄러 수정
 */
export const updateScheduler = async (data: any): Promise<UpdateOut | null> => {
  try {
    const { scheduler_id, ...baseData } = data;
    const validatedData = validateWithZod(SchedulerUpdateInSchema, baseData);

    return apiCall<UpdateOut>(`${BASE_URL}/${scheduler_id}`, {
      method: "PUT",
      data: validatedData,
    });
  } catch (error) {
    handleZodValidationError(error);
  }
};

/**
 * 스케줄러 삭제
 */
export const deleteScheduler = async (data: any): Promise<DeleteOut | null> => {
  const { scheduler_id } = data;

  return apiCall<DeleteOut>(`${BASE_URL}/${scheduler_id}`, {
    method: "DELETE",
  });
};

/**
 * 스케줄러 참여 멤버 목록 조회
 */
export const selectSchedulerMembers = async (scheduler_id: string): Promise<SchedulerMembersOut | null> => {
  return apiCall<SchedulerMembersOut>(`${BASE_URL}/${scheduler_id}/member`, {
    method: "GET",
  });
};

/**
 * 스케줄러 참여 멤버 추가
 */
export const addSchedulerMember = async (
  scheduler_id: string,
  data: { git_id: string; email?: string; name?: string },
): Promise<CreateOut | null> => {
  return apiCall<CreateOut>(`${BASE_URL}/${scheduler_id}/member`, {
    method: "POST",
    data,
  });
};

/**
 * 스케줄러 참여 멤버 제거
 */
export const removeSchedulerMember = async (scheduler_id: string, git_id: string): Promise<DeleteOut | null> => {
  return apiCall<DeleteOut>(`${BASE_URL}/${scheduler_id}/member/${git_id}`, {
    method: "DELETE",
  });
};

/**
 * 스케줄러 즉시 실행 — 선택 스케줄러 발송 테스트
 */
export const runScheduler = async (scheduler_id: string): Promise<MessageOut | null> => {
  return apiCall<MessageOut>(`${BASE_URL}/${scheduler_id}/run`, {
    method: "POST",
  });
};
