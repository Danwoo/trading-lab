// components/features/Scheduler/SchedulerDetailForm.tsx
"use client";

import { useEffect, useState } from "react";
import type { LegacyGridColumn } from "@/types/grid";
import { useFormState } from "@/hooks/shared/useFormState";
import { Button, TextBox, SelectBox, NumberBox, TabPanel, TabContent } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { DualSelectGrid } from "@/components/shared/DataGrid";
import { showToast, showMessage } from "@/components/shared/Feedback";
import { getApiErrorMessage } from "@/utils/common/errors";
import { Scheduler, SchedulerMember } from "@/schemas/scheduler/scheduler";
import { HolderInfo } from "@/schemas/devActivity/devActivity";
import {
  selectSchedulerMembers,
  addSchedulerMember,
  removeSchedulerMember,
} from "@/services/scheduler/schedulerService";

interface Props {
  isNew: boolean;
  initialData: Partial<Scheduler>;
  onSubmit: (data: Scheduler) => Promise<boolean>;
  onCancel?: () => void;
  holders?: HolderInfo[];
  dayOfWeekItems?: { code: string; code_nm: string }[];
  useAtItems?: { code: string; code_nm: string }[];
  periodItems?: { code: number; code_nm: string }[];
}

// 후보 목록의 식별자는 계좌 식별자다 — 등록·조회·삭제 모두 `account_id` 다
// (`SchedulerMemberIn`·`SchedulerMemberOut`). backend 가 그 값을 portfolio-mcp 소유 계좌
// 목록과 대조한다 (#115). 종전에는 프론트만 `git_id` 라 불러 **추가·조회·삭제가 전부**
// 어긋나 있었다 (#439 F21).
interface UserOption {
  account_id: string;
  name: string;
  email: string;
}

const userColumns: LegacyGridColumn[] = [
  { dataField: "account_id", caption: "계좌 ID" },
  { dataField: "name", caption: "이름" },
  { dataField: "email", caption: "이메일" },
];

const memberColumns: LegacyGridColumn[] = [
  { dataField: "account_id", caption: "계좌주 ID" },
  { dataField: "name", caption: "이름" },
  { dataField: "email", caption: "이메일" },
];

export default function SchedulerDetailForm({
  initialData,
  isNew,
  holders = [],
  dayOfWeekItems = [],
  useAtItems = [],
  periodItems = [],
  onSubmit,
  onCancel,
}: Props) {
  const { formData, handleFieldChange, getFieldProps, handleSubmit } = useFormState<Scheduler>(initialData);

  const [members, setMembers] = useState<SchedulerMember[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedUserIds, setSelectedUserIds] = useState<string[]>([]);
  const [selectedMemberIds, setSelectedMemberIds] = useState<string[]>([]);
  const canAccessMembers = !isNew && !!formData.scheduler_id?.trim();

  const tabs = [
    { id: "basic", text: "기본 정보", icon: "edit" },
    { id: "members", text: "참여 멤버", icon: "group", disabled: !canAccessMembers },
  ];

  const fetchMembers = async () => {
    if (!formData.scheduler_id) return;
    const result = await selectSchedulerMembers(formData.scheduler_id);
    if (result) setMembers(result.items);
  };

  useEffect(() => {
    if (isNew || !formData.scheduler_id) return;
    const load = async () => {
      setLoading(true);
      await fetchMembers();
      setLoading(false);
    };
    load();
  }, [formData.scheduler_id]);

  const allUsers: UserOption[] = holders.map((u) => ({ account_id: u.account_id, name: u.name, email: u.email }));

  const handleAddMember = async () => {
    if (selectedUserIds.length === 0) {
      showToast("추가할 멤버를 선택해주세요.", "warning");
      return;
    }
    const newIds = selectedUserIds.filter((id) => !members.map((m) => m.account_id).includes(id));
    if (newIds.length === 0) {
      showToast("이미 추가된 멤버입니다.", "warning");
      return;
    }
    for (const accountId of newIds) {
      const user = holders.find((u) => u.account_id === accountId);
      // 이메일은 백엔드가 **필수**로 받는다 — 없는 채로 보내면 422 다. 보낼 곳이 없는 사람을
      // 조용히 건너뛰지 않고 그 사실을 말한다(이 자리가 하는 일이 「메일 받을 사람 추가」다).
      if (!user?.email) {
        showMessage("알림", <div>{`${accountId} 는 이메일이 없어 추가할 수 없습니다.`}</div>);
        continue;
      }
      try {
        await addSchedulerMember(formData.scheduler_id!, {
          account_id: accountId,
          email: user.email,
          name: user.name,
        });
      } catch (error) {
        showToast(getApiErrorMessage(error), "error");
      }
    }
    setSelectedUserIds([]);
    await fetchMembers();
  };

  const handleRemoveMember = async () => {
    if (selectedMemberIds.length === 0) {
      showToast("제거할 멤버를 선택해주세요.", "warning");
      return;
    }
    for (const account_id of selectedMemberIds) {
      try {
        await removeSchedulerMember(formData.scheduler_id!, account_id);
      } catch (error) {
        showMessage("오류", <div>{getApiErrorMessage(error)}</div>);
        break;
      }
    }
    setSelectedMemberIds([]);
    await fetchMembers();
  };

  return (
    <div className="h-full">
      <TabPanel items={tabs} defaultTab="basic">
        <TabContent tabId="basic">
          <div className="h-full flex flex-col">
            <div className="flex-shrink-0 mb-2">
              <div className="flex gap-2 justify-end">
                <Button text="저장" onClick={() => handleSubmit(onSubmit)} />
                {onCancel && !isNew && <Button text="취소" onClick={onCancel} stylingMode="outlined" type="normal" />}
              </div>
            </div>
            <div className="flex-1 min-h-0 overflow-auto">
              <TableGroup title="기본 정보">
                <TableRow>
                  <TableCell label="스케줄러ID" required>
                    <TextBox
                      fieldName="scheduler_id"
                      value={formData.scheduler_id}
                      readOnly={!isNew}
                      onValueChanged={(_field, value) =>
                        handleFieldChange("scheduler_id", String(value ?? "").replace(/\s/g, ""))
                      }
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                  <TableCell label="스케줄러명" required>
                    <TextBox
                      fieldName="scheduler_nm"
                      value={formData.scheduler_nm}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell label="요일" required>
                    <SelectBox
                      fieldName="day_of_week"
                      value={formData.day_of_week}
                      items={dayOfWeekItems}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                  <TableCell label="주기" required>
                    <SelectBox
                      fieldName="period_weeks"
                      value={formData.period_weeks}
                      items={periodItems}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell label="시" required>
                    <NumberBox
                      fieldName="hour"
                      value={formData.hour}
                      min={0}
                      max={23}
                      showSpinButtons
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                  <TableCell label="분" required>
                    <NumberBox
                      fieldName="minute"
                      value={formData.minute}
                      min={0}
                      max={59}
                      showSpinButtons
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell label="사용여부" required>
                    <SelectBox
                      fieldName="use_at"
                      value={formData.use_at}
                      items={useAtItems}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                  <TableCell label="설명">
                    <TextBox
                      fieldName="description"
                      value={formData.description}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                </TableRow>
              </TableGroup>
            </div>
          </div>
        </TabContent>

        <TabContent tabId="members">
          <div className="h-full flex flex-col">
            <div className="flex-shrink-0 mb-2">
              <div className="flex gap-2 justify-end">
                {onCancel && <Button text="취소" onClick={onCancel} stylingMode="outlined" type="normal" />}
              </div>
            </div>
            <div className="flex-1 min-h-0">
              <DualSelectGrid
                title="참여 멤버 관리"
                leftTitle="전체 계좌"
                rightTitle="참여 멤버"
                leftData={allUsers.filter((u) => !members.some((m) => m.account_id === u.account_id))}
                rightData={members}
                leftColumns={userColumns}
                rightColumns={memberColumns}
                leftKeyExpr="account_id"
                rightKeyExpr="account_id"
                loading={loading}
                fillHeight
                onAdd={handleAddMember}
                onRemove={handleRemoveMember}
                onLeftSelectionChanged={setSelectedUserIds}
                onRightSelectionChanged={setSelectedMemberIds}
              />
            </div>
          </div>
        </TabContent>
      </TabPanel>
    </div>
  );
}
