"use client";

import { FC, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

// 배럴이 아니라 직접 경로로 가져온다 — `@/components/shared/ui` 배럴은 FileListDisplay 를 거쳐
// services/common/fileService → env.ts 까지 끌고 온다(#341 ② 배럴 fan-out).
import { Button } from "@/components/shared/ui/Button";
import { TextBox } from "@/components/shared/ui/TextBox";

import PolicyPopup from "@/components/features/Common/Policy/PolicyPopup";
import { showMessage } from "@/stores/shared/messageStore";
import { sendEmail, verifySignupOTP, checkEmail } from "@/services/common/authService";
import { SIGNUP_VERIFICATION_TOKEN_KEY } from "@/constants/signup";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";

interface Props {}

export const Signup: FC<Props> = () => {
  const [email, setEmail] = useState<string>("");
  const [otp, setOtp] = useState<string>("");
  // 모달은 「확인」을 누르면 사라진다 — 무엇을 해야 하는지는 폼 옆에 남아 있어야 한다 (#342).
  const [sendError, setSendError] = useState<string>("");
  const [result, setResult] = useState<boolean>(false);
  const [emailToggle, setEmailToggle] = useState<string>("hidden");
  const [verifyToggle, setVerifyToggle] = useState<string>("hidden");
  const router = useRouter();

  const handleSubmit = async (e: any) => {
    e.preventDefault();

    if (result) {
      router.push(`/signup/${encodeURIComponent(email)}`);
    } else {
      showMessage("알림", <div>인증 코드를 확인해주세요.</div>);
    }
  };

  // 이메일 발송 처리 API
  const emailSendApi = async (email: string) => {
    try {
      const data = await sendEmail(email);

      setSendError("");
      // 코드가 어디로 갔는지는 **서버가 말해 준다** — SMTP 미설정 개발 설치에서 메일을 보냈다고
      // 말하면 처음 쓰는 사람이 오지 않는 메일을 기다린다 (#424).
      showMessage(
        "알림",
        data?.delivery === "console" ? (
          <div>
            메일 서버가 설정되지 않아(EMAIL_HOST 없음) 메일이 나가지 않았습니다.
            <br />
            인증 코드는 이 앱을 띄운 서버 콘솔에 찍혀 있습니다.
          </div>
        ) : (
          <div>
            [{email}] 로
            <br />
            인증 코드를 발송 하였습니다.
          </div>
        ),
      );
      setEmailToggle("");
    } catch (error: any) {
      const message = getApiErrorMessage(error);
      setSendError(message);
      showMessage("오류", message);
    }
  };

  // 이메일 존재 여부 확인 API
  const emailchkApi = async (email: string) => {
    try {
      const data = await checkEmail(email);

      if (data?.result) {
        if (data.name === "email") {
          showMessage("알림", <div>잘못된 이메일 주소 입니다.</div>);
        } else {
          showMessage(
            "알림",
            <p>
              [{email}] 은<br />
              이미 사용중인 이메일 입니다.
            </p>,
          );
        }
      } else {
        // 회원가입 이메일 발송
        emailSendApi(email);
      }
    } catch (error) {
      console.error("Error checking email:", error);
      showMessage("오류", <div>이메일 확인 중 오류가 발생했습니다.</div>);
    }
  };

  const emailchk = async () => {
    if (!result) {
      if (email) {
        setSendError("");
        emailchkApi(email);
      } else {
        showMessage("알림", <div>이메일 주소를 입력해주세요.</div>);
      }
    }
  };

  const otpChk = async () => {
    try {
      const data = await verifySignupOTP(email, otp);

      if (data?.result && data.verificationToken && otp !== "") {
        showMessage("알림", <div>인증 완료 하였습니다.</div>);
        setResult(true);
        setVerifyToggle("");
        sessionStorage.setItem("verifiedSignupEmail", email);
        // 다음 단계(비밀번호 만들기)가 가입 요청에 실어 보낼 서버 발급 증거 (#343).
        sessionStorage.setItem(SIGNUP_VERIFICATION_TOKEN_KEY, data.verificationToken);
      } else {
        showMessage(
          "알림",
          <p>
            인증 코드가 일치하지 않습니다.
            <br />
            이메일을 확인해주세요.
          </p>,
        );
        setResult(false);
        setOtp("");
        sessionStorage.removeItem(SIGNUP_VERIFICATION_TOKEN_KEY);
      }
    } catch (error) {
      console.error("Error verifying code:", error);
      showMessage("오류", <div>인증 코드 확인 중 오류가 발생했습니다.</div>);
    }
  };

  return (
    <div className="relative h-[100dvh] w-screen bg-bg-base">
      <div className="auth-backdrop absolute z-10 m-auto w-full px-4 py-8 h-full min-h-[667px]">
        <PolicyPopup additionalClassName="pointer-events-none" />

        {/* **이 카드는 라이트다** — 그 사실을 선언한다. 바깥 `.auth-backdrop` 은 모드와 무관한
            어두운 섬이라 다크 토큰을 깔고, 그 안의 이 카드만 밝다. 선언이 없으면 카드 안의 공용
            입력이 `:root`(다크) 토큰으로 풀려 밝은 카드 위에 검은 상자가 놓인다. */}
        <div
          data-theme="light"
          className="card lg:card-side rounded-3xl bg-[#F0F1F2] w-full h-full sm:max-h-[700px] sm:max-w-[800px] m-auto"
        >
          <div className="card-body">
            <div className="w-full lg:max-w-3xl sm:mx-auto sm:w-full sm:max-w-sm sm:pt-10">
              <h2 className="font-bold text-2xl sm:text-4xl mt-10 text-center tracking-tight text-[#303F67]">
                회원가입
              </h2>
              <div className="text-center mt-3 text-[#303F67] text-sm font-semibold">
                가입을 위해 이메일 인증을 진행해주세요.
              </div>
            </div>

            <div className="border-t-[1px] mt-10 mb-8 border-t-[#DDE2EC] w-full "></div>

            <div className="sm:mx-auto sm:w-full sm:max-w-sm">
              <form action="#" method="POST" className="space-y-4" onSubmit={handleSubmit}>
                <div className="items-center max-w-sm mx-auto">
                  <label htmlFor="email" className="block text-sm font-medium text-gray-900">
                    이메일 주소
                  </label>
                  <div className="flex mt-1 gap-2">
                    <TextBox
                      id="email"
                      name="email"
                      mode="email"
                      placeholder="이메일을 입력해주세요."
                      width="100%"
                      height={48}
                      value={email}
                      onValueChanged={(_field, v) => {
                        setEmail(String(v));
                        setSendError("");
                      }}
                      className="rounded-2xl"
                      readOnly={emailToggle !== "hidden"}
                    />
                    <Button
                      text={emailToggle === "hidden" ? "인증요청" : "요청됨"}
                      type={emailToggle === "hidden" ? "default" : "normal"}
                      stylingMode="contained"
                      width={88}
                      height={48}
                      disabled={emailToggle !== "hidden"}
                      onClick={emailchk}
                      elementAttr={{
                        class:
                          emailToggle === "hidden"
                            ? "rounded-2xl bg-[#20324E] text-sm font-semibold text-white shrink-0"
                            : "rounded-2xl bg-[#DFE2EB] text-sm font-semibold text-[#7582A5] shrink-0",
                      }}
                    />
                  </div>
                </div>

                {sendError && (
                  <p role="alert" className="max-w-sm mx-auto whitespace-pre-line text-sm font-medium text-danger">
                    {sendError}
                  </p>
                )}

                <div className={`items-center max-w-sm mx-auto ${emailToggle}`}>
                  <label htmlFor="otp" className="font-medium block text-sm text-gray-900">
                    인증 코드
                  </label>
                  <div className="flex mt-1 gap-2">
                    {/* 인증 완료 시각 신호는 readOnly 스타일(회색 배경)과 「확인됨」 버튼이 맡는다 —
                        종전의 `bg-gray-500` 덮어쓰기는 본문색과 대비 3:1 대 미달이라 옮기지 않았다. */}
                    <TextBox
                      id="otp"
                      name="otp"
                      mode="password"
                      placeholder="인증 코드를 입력해주세요."
                      value={otp}
                      width="100%"
                      height={48}
                      onValueChanged={(_field, v) => setOtp(String(v))}
                      className="rounded-2xl"
                      readOnly={verifyToggle !== "hidden"}
                    />
                    <Button
                      text={verifyToggle === "hidden" ? "확인" : "확인됨"}
                      type={verifyToggle === "hidden" ? "default" : "normal"}
                      stylingMode="contained"
                      width={88}
                      height={48}
                      disabled={verifyToggle !== "hidden"}
                      onClick={otpChk}
                      elementAttr={{
                        class:
                          verifyToggle === "hidden"
                            ? "rounded-2xl bg-[#20324E] text-sm font-semibold text-white shrink-0"
                            : "rounded-2xl bg-[#DFE2EB] text-sm font-semibold text-[#7582A5] shrink-0",
                      }}
                    />
                  </div>
                </div>

                <div>
                  <Button
                    useSubmitBehavior={true}
                    text="계속 (1/2)"
                    width="100%"
                    height={48}
                    stylingMode="contained"
                    type="default"
                    className="rounded-2xl bg-gradient-to-r from-[#2E3BD0] to-[#2C64F8] text-sm font-bold text-white"
                  />
                </div>
              </form>

              <p className="mt-5 text-center text-sm text-gray-500">
                <Link href="/" className="font-medium text-[#192850] hover:text-blue-500">
                  다른 계정으로 로그인
                </Link>
              </p>
            </div>

            <ul className="mt-5 sm:mt-10 max-w-md w-full hidden sm:flex m-auto list-none justify-between p-0 transition-[height] duration-200 ease-in-out">
              <li className="flex-auto">
                <div
                  className="flex items-center pl-2 leading-[1.3rem] no-underline after:ml-2 after:h-px after:w-full after:flex-1
                  after:bg-[#e0e0e0] dark:after:bg-neutral-600 dark:hover:bg-[#3b3b3b] pointer-events-none select-none"
                >
                  <span className="my-6 mr-2 flex h-[1.938rem] w-[1.938rem] items-center justify-center rounded-full bg-[#DCE4FF] text-sm font-medium text-[#40464f]">
                    1
                  </span>
                  <span className="font-semibold text-xs sm:text-base text-[#192850] after:flex after:text-[0.8rem] after:content-[data-content] dark:text-neutral-700">
                    이메일 인증
                  </span>
                </div>
              </li>
              <li className="flex-auto">
                <div className="flex items-center pr-2 leading-[1.3rem] no-underline before:mr-2 before:h-px before:w-full before:flex-1 before:bg-[#e0e0e0] before:content-[''] focus:outline-none dark:before:bg-neutral-600 dark:after:bg-neutral-600 dark:hover:bg-[#3b3b3b] pointer-events-none select-none">
                  <span className="text-[#192850] my-6 mr-2 flex h-[1.938rem] w-[1.938rem] items-center justify-center rounded-full bg-[#DFE1E8] text-sm font-medium ">
                    2
                  </span>
                  <span className="font-semibold text-xs sm:text-base text-[#192850] after:flex after:text-[0.8rem] after:content-[data-content] dark:text-neutral-300">
                    비밀번호만들기
                  </span>
                </div>
              </li>
              <li className="flex-auto">
                <div className="flex items-center pr-2 leading-[1.3rem] no-underline before:mr-2 before:h-px before:w-full before:flex-1 before:bg-[#e0e0e0] before:content-[''] focus:outline-none dark:before:bg-neutral-600 dark:after:bg-neutral-600 dark:hover:bg-[#3b3b3b] pointer-events-none select-none">
                  <span className="text-[#192850] my-6 mr-2 flex h-[1.938rem] w-[1.938rem] items-center justify-center rounded-full bg-[#DFE1E8] text-sm font-medium ">
                    3
                  </span>
                  <span className="font-semibold text-xs sm:text-base text-[#192850] after:flex after:text-[0.8rem] after:content-[data-content] dark:text-neutral-300">
                    완료
                  </span>
                </div>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
