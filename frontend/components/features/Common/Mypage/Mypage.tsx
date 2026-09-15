"use client";

import { FC, useState, useCallback, useEffect } from "react";
import { signOut } from "@/lib/auth/auth-client";

import { fetchMyInfo, updateMyInfo, deleteMyAccount } from "@/services/common/mypageService";
import { getApiErrorMessage } from "@/utils/common/errors";

// 배럴이 아니라 직접 경로로 가져온다 — `@/components/shared/ui` 배럴은 FileListDisplay 를 거쳐
// services/common/fileService → env.ts 까지 끌고 온다(#341 ② 배럴 fan-out).
import { Button } from "@/components/shared/ui/Button";
import { TextBox } from "@/components/shared/ui/TextBox";
import { showMessage } from "@/stores/shared/messageStore";

interface Props {}

export const Mypage: FC<Props> = () => {
  const [data, setData] = useState<any>(null);
  const [passwordError, setPasswordError] = useState<string>("");
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    confirmPassword: "",
    name: "",
    dept: "",
  });

  // 비밀번호 일치 여부 확인
  const validatePassword = (password: string, confirmPassword: string) => {
    if (password || confirmPassword) {
      if (password !== confirmPassword) {
        setPasswordError("비밀번호가 일치하지 않습니다.");
        return false;
      } else if (password && password.length < 8) {
        setPasswordError("비밀번호는 8자리 이상이어야 합니다.");
        return false;
      } else {
        setPasswordError("");
        return true;
      }
    }
    return true;
  };

  // 비밀번호 변경 핸들러
  const handlePasswordChange = (_field: unknown, value: any) => {
    const newPassword = String(value ?? "");
    setFormData((prev) => ({
      ...prev,
      password: newPassword,
    }));
    validatePassword(newPassword, formData.confirmPassword);
  };

  // 비밀번호 확인 변경 핸들러
  const handleConfirmPasswordChange = (_field: unknown, value: any) => {
    const newConfirmPassword = String(value ?? "");
    setFormData((prev) => ({
      ...prev,
      confirmPassword: newConfirmPassword,
    }));
    validatePassword(formData.password, newConfirmPassword);
  };

  // 회원정보 수정
  const handleSubmit = async (e: any) => {
    e.preventDefault();

    // **`form.elements` 로 읽는다.** `form.name` 은 폼 자신의 name 속성(문자열)이라 같은 이름의
    // 입력을 가린다 — `e.target.name.value` 는 입력값이 아니라 `undefined` 였다. 칸이 조건부로
    // 안 그려질 수 있으므로 없는 칸도 빈 문자열로 받는다(읽다 죽으면 저장이 통째로 멈춘다).
    const fields = (e.target as HTMLFormElement)?.elements as HTMLFormControlsCollection | undefined;
    const valueOf = (field: string) => ((fields?.namedItem(field) as HTMLInputElement | null)?.value ?? "") as string;
    const userEmail = valueOf("email");
    const userPass = valueOf("password");
    const userConfirmPass = valueOf("confirmPassword");
    const userName = valueOf("name");
    const userDept = valueOf("dept");

    // **바뀐 것이 없으면 「변경되었습니다」라고 하지 않는다** (#446 F33). 그 문장은 무언가
    // 달라졌다는 말이고, 안 달라졌을 때 같은 말을 하면 진짜 변경의 신호가 값을 잃는다.
    // 비밀번호는 값이 있으면 그 자체가 변경이다(현재 값과 비교할 방법이 없다).
    const unchanged = !userPass && userName === (data?.name ?? "") && userDept === (data?.dept ?? "");
    if (unchanged) {
      showMessage("알림", <div>바뀐 것이 없습니다.</div>);
      return;
    }

    // 비밀번호 확인 로직
    if (userPass && !validatePassword(userPass, userConfirmPass)) {
      showMessage("알림", <div>{passwordError}</div>);
      return;
    }

    const isValid = await memberMyInfoChangeApi(userEmail, userPass, userName, userDept);

    if (isValid) {
      showMessage("알림", <div>마이페이지 정보가 변경되었습니다.</div>);
    }
  };

  const memberMyInfoChangeApi = async (userEmail: string, userPass: string, userName: string, userDept: string) => {
    try {
      const result = await updateMyInfo({
        email: userEmail,
        password: userPass || undefined,
        name: userName,
        dept: userDept,
      });
      if (result?.name === "password") {
        showMessage("알림", <div>비밀번호 8자리 이상 입력해주세요.</div>);
        return false;
      }
      if (result?.name === "name") {
        showMessage("알림", <div>이름을 2자리 이상 다시 입력해주세요.</div>);
        return false;
      }
      return result?.result ?? false;
    } catch (error) {
      showMessage("오류", <div>{getApiErrorMessage(error)}</div>);
      return false;
    }
  };

  // 회원탈퇴
  const AccountDeletion = async () => {
    showMessage(
      "회원탈퇴 안내",
      <div className="whitespace-pre-line max-w-[800px] p-4 mx-auto">
        <p>안녕하세요, ACME 입니다.</p>
        <p className="mt-4 mb-3"> 회원 탈퇴를 진행하시려면 아래 안내 사항을 확인해 주세요 : </p>
        <div className="mt-2">
          1. <b>탈퇴 후 데이터 삭제:</b> 회원 탈퇴가 완료되면, 회원님의 계정 및 관련 데이터는 영구적으로 삭제됩니다.
          복구할 수 없으니 신중히 결정해 주세요.
        </div>
        <div className="mt-4">
          2. <b>서비스 이용 불가:</b> 탈퇴 후에는 사이트의 모든 기능과 서비스에 접근할 수 없습니다. 탈퇴를 원하신다면
          현재 사용 중인 서비스 및 데이터가 더 이상 필요 없는지 확인해 주세요.
        </div>
        <p className="mt-4">
          <b>문의:</b> 탈퇴 과정에서 문제가 발생하거나 추가적인 도움이 필요하시면 02-0000-0000 로 문의해 주세요.
        </p>
        <p className="mt-4 font-semibold">탈퇴를 진행하시겠습니까?</p>
        <p className="mt-2 text-red-500">탈퇴 후에는 복구할 수 없으니 신중히 결정해 주세요.</p>
      </div>,
      {
        type: "confirm",
        width: 800,
        height: "auto",
        confirmText: "탈퇴하기",
        cancelText: "취소",
        confirmButtonType: "danger",
        callback: {
          onCancel: () => {
            return;
          },
          onConfirm: async () => {
            try {
              await deleteMyAccount();

              showMessage("알림", <div>회원탈퇴가 완료되었습니다.</div>, {
                callback: {
                  onConfirm: async () => {
                    sessionStorage.clear();
                    await signOut({
                      fetchOptions: {
                        onSuccess: () => {
                          window.location.href = "/";
                        },
                      },
                    });
                  },
                },
              });
            } catch (error) {
              showMessage("오류", <div style={{ whiteSpace: "pre-line" }}>{getApiErrorMessage(error)}</div>);
            }
          },
        },
      },
    );
  };

  const fetchData = useCallback(async () => {
    try {
      const result = await fetchMyInfo();
      if (result) setData(result);
    } catch (error) {
      console.error("Error:", error);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <>
      {data && (
        <div className="w-full">
          <h1 className="flex items-center text-[#192850] font-semibold text-xl w-full border-b-[1px] border-[#E5E9F2] p-5 sm:p-7">
            마이페이지
          </h1>
          <div className="p-5">
            <div className="text-[#192850] font-semibold text-xl pt-5">내 정보 설정</div>
            <div className="text-[#979FB1] font-medium text-sm py-5">내 정보 및 비밀번호를 변경하실 수 있습니다.</div>

            <form action="#" method="POST" className="space-y-4" onSubmit={handleSubmit}>
              <div className="sm:flex w-full sm:gap-5 sm:max-w-3xl">
                <div className="w-full items-center">
                  <label htmlFor="email" className="block text-sm font-medium leading-9 text-[#192850]">
                    이메일 주소
                  </label>
                  <TextBox
                    id="email"
                    name="email"
                    mode="email"
                    width="100%"
                    height={48}
                    readOnly={true}
                    defaultValue={data.email}
                    className="rounded-xl"
                  />
                </div>
                <div className="w-full items-center">
                  <label htmlFor="name" className="block text-sm font-medium leading-9 text-[#192850]">
                    이름
                  </label>
                  <TextBox
                    id="name"
                    name="name"
                    width="100%"
                    height={48}
                    defaultValue={data.name}
                    className="rounded-xl"
                  />
                </div>
              </div>

              <div className="sm:flex w-full sm:gap-5 sm:max-w-3xl">
                <div className="w-full items-center">
                  <label htmlFor="dept" className="block text-sm font-medium leading-9 text-[#192850]">
                    소속
                  </label>
                  <TextBox
                    id="dept"
                    name="dept"
                    width="100%"
                    height={48}
                    defaultValue={data.dept}
                    className="rounded-xl"
                  />
                </div>
                <div className="w-full items-center">
                  <label htmlFor="workspace" className="block text-sm font-medium leading-9 text-[#192850]">
                    워크스페이스
                  </label>
                  <TextBox
                    id="workspace"
                    name="workspace"
                    width="100%"
                    height={48}
                    readOnly={true}
                    defaultValue={data.workspace_nm ?? "미배정"}
                    className="rounded-xl"
                  />
                </div>
              </div>

              <div className="sm:flex w-full sm:gap-5 sm:max-w-3xl">
                <div className="w-full items-center">
                  <label htmlFor="password" className="block text-sm font-medium leading-9 text-[#192850]">
                    비밀번호
                  </label>
                  <TextBox
                    id="password"
                    name="password"
                    showPasswordToggle
                    width="100%"
                    height={48}
                    maxLength={16}
                    defaultValue=""
                    onValueChanged={handlePasswordChange}
                    className="rounded-xl"
                  />
                </div>
                <div className="w-full items-center">
                  <label htmlFor="confirmPassword" className="block text-sm font-medium leading-9 text-[#192850]">
                    비밀번호 확인
                  </label>
                  <TextBox
                    id="confirmPassword"
                    name="confirmPassword"
                    showPasswordToggle
                    width="100%"
                    height={48}
                    maxLength={16}
                    defaultValue=""
                    onValueChanged={handleConfirmPasswordChange}
                    className="rounded-xl"
                  />
                  {passwordError && (
                    <div role="alert" className="text-red-500 text-sm mt-1">
                      {passwordError}
                    </div>
                  )}
                </div>
              </div>

              <div className="block items-center max-w-sm pt-5">
                <Button
                  useSubmitBehavior={true}
                  text="변경하기"
                  width={100}
                  height={48}
                  stylingMode="contained"
                  type="default"
                  className="rounded-md bg-[#2C64F8] text-sm font-semibold text-white"
                />
              </div>

              <div className="text-[#192850] font-semibold text-xl pt-5 border-t-[1px] border-[#E5E9F2]">회원탈퇴</div>

              <div className="mt-10 text-sm text-[#979FB1] font-medium">
                회원탈퇴를 하시겠습니까? <br />
                <Button
                  text="회원탈퇴"
                  onClick={AccountDeletion}
                  width={100}
                  height={48}
                  stylingMode="outlined"
                  type="normal"
                  className="rounded-xl mt-5 text-[#7E8293]"
                />
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
};
