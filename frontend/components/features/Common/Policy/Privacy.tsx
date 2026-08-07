"use client";

import { FC } from "react";
import { Button } from "@/components/shared/ui/Button";

interface Props {
  onClose?: () => void;
}

// 종전엔 devextreme-react/scroll-view 였다(#341 ⑤) — Terms.tsx 와 같은 이유로 자체 스크롤 박스 없이 본문만.
export const Privacy: FC<Props> = ({ onClose }) => {
  return (
    <div className="p-4 text-[#455172] bg-[#F5F7FC] whitespace-pre-wrap">
      <h1 className="font-extrabold text-xl my-3">1. 개인정보의 수집 항목 및 이용 목적</h1>

      {`수집 항목: 이름, 이메일 주소, IP 주소 등 서비스 이용에 필요한 최소한의 개인정보를 수집합니다.
이용 목적:
회원 관리 및 본인 인증
서비스 제공 및 기능 개선
맞춤형 광고 제공 및 마케팅 활동
서비스 이용 기록 분석
불법적인 사용 방지 및 시스템 보안 유지`}
      <h1 className="font-extrabold text-xl my-3">2. 개인정보의 보유 및 이용 기간</h1>

      {`수집된 개인정보는 원칙적으로 회원 탈퇴 시 지체 없이 파기합니다. 다만, 다음의 경우에는 예외적으로 기간 동안 보존합니다.

관련 법령에 의한 정보 보존
분쟁 해결을 위한 자료 보존`}
      <h1 className="font-extrabold text-xl my-3">3. 개인정보의 제3자 제공</h1>

      {`원칙적으로, 이용자의 개인정보를 제3자에게 제공하지 않습니다. 다만, 다음의 경우에는 예외적으로 제공할 수 있습니다.

이용자의 동의를 얻은 경우
법령의 특별한 규정에 의한 경우`}
      <h1 className="font-extrabold text-xl my-3">4. 개인정보의 파기</h1>

      {`이용자가 회원 탈퇴를 요청하거나 개인정보의 수집 및 이용에 대한 동의를 철회한 경우, 회사는 지체 없이 이를 파기합니다. 단, 관계 법령의 규정에 의하여 보존하여야 할 경우에는 예외로 합니다.`}

      <h1 className="font-extrabold text-xl my-3">5. 정보주체의 권리와 그 행사 방법</h1>

      {`이용자는 언제든지 자신의 개인정보를 조회하거나 수정할 수 있으며, 개인정보의 처리에 동의하지 않는 경우 동의를 철회할 수 있습니다.

개인정보 조회 및 수정: [로그인후 마이페이지]
개인정보 처리 동의 철회: [02-0000-0000]`}
      <h1 className="font-extrabold text-xl my-3">6. 개인정보 자동수집 장치의 설치/운영 및 거부에 관한 사항</h1>

      {`본 서비스는 이용자에게 맞춤형 서비스 제공을 위해 쿠키를 사용합니다. 쿠키는 이용자의 컴퓨터를 식별하고 추적하기 위한 작은 텍스트 파일로, 이용자의 브라우저 설정을 통해 쿠키 설치를 거부할 수 있습니다. 다만, 쿠키 설치를 거부할 경우 일부 서비스 이용이 제한될 수 있습니다.`}

      <h1 className="font-extrabold text-xl my-3">7. 개인정보의 안전성 확보 조치</h1>

      {`회사는 이용자의 개인정보를 보호하기 위해 다음과 같은 기술적/관리적 보호 조치를 하고 있습니다.

개인정보 취급 시스템에 대한 접근권한 관리
해킹 및 외부침입에 대한 보안 시스템 구축
개인정보 취급 직원의 최소화 및 교육
정기적인 자체 점검 및 개선`}
      <h1 className="font-extrabold text-xl my-3">8. 개인정보 보호 책임자</h1>

      {`연락처: [02-0000-0000], [sa@example.com]`}
      <h1 className="font-extrabold text-xl my-3">9. 개인정보처리방침 변경</h1>

      {`본 개인정보처리방침은 관련 법령의 변경 또는 회사의 내부 방침 변경에 따라 변경될 수 있으며, 변경된 내용은 변경 사유와 함께 지체 없이 이 페이지를 통해 공지합니다.`}

      <h1 className="font-extrabold text-xl my-3">10. 기타</h1>

      {`본 개인정보처리방침에 대한 문의는 [02-0000-0000]로 연락주시기 바랍니다.`}

      {onClose && (
        <div className="w-full flex items-end justify-end mt-20">
          <Button
            text="닫기"
            onClick={onClose}
            width={100}
            height={36}
            stylingMode="contained"
            type="normal"
            className="rounded-md"
          />
        </div>
      )}
    </div>
  );
};
