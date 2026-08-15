"use client";

import { FC } from "react";
import { Button } from "@/components/shared/ui/Button";

interface Props {
  onClose?: () => void;
}

// 종전엔 devextreme-react/scroll-view 였다(#341 ⑤). 이 화면이 ScrollView 에서 쓰던 기능은
// "넘치면 세로 스크롤" 하나뿐이고, 유일한 호출부인 PolicyPopup 은 이 본문을 팝업 본문
// (`min-h-0 flex-1 overflow-auto`)에 넣는다 — 이미 스크롤 컨테이너다. 그래서 자체 스크롤 박스를
// 다시 만들지 않고 본문만 돌려준다(실측: 팝업 본문 clientHeight 653 / scrollHeight 2024 로 스크롤됨).
export const Terms: FC<Props> = ({ onClose }) => {
  return (
    <div data-theme="light" className="p-4 text-ink bg-bg-panel whitespace-pre-wrap">
      <h1 className="font-extrabold text-xl my-3">제1조 목적</h1>
      {`약관의 목적은 본 약관에 동의하는 고객(이하 "회원")이 ACME(이하 "회사")가 제공하는 서비스를 이용함에 있어 회사와 회원 간의 권리, 의무 및 책임사항을 규정함을 목적으로 합니다.`}
      <h1 className="font-extrabold text-xl my-3">제2조 약관의 효력</h1>
      {`본 약관은 회사가 제공하는 서비스 화면에 게시하거나 기타의 방법으로 회원에게 공지함으로써 효력을 발생합니다. 회원은 본 약관에 동의함으로써 회사와 계약을 체결한 것으로 간주됩니다.`}
      <h1 className="font-extrabold text-xl my-3">제3조 약관의 변경</h1>
      {`회사는 본 약관을 변경할 수 있으며, 변경된 약관은 제2조와 같은 방법으로 공지합니다. 회원은 변경된 약관에 동의하지 않을 경우 서비스 이용을 중단할 수 있습니다.`}
      <h1 className="font-extrabold text-xl my-3">제4조 서비스의 제공</h1>
      {`회사는 회원에게 다음과 같은 서비스를 제공합니다.`}
      <ul className="list-disc ml-5">
        <li>1. 금융·공시 관련 정보 제공</li>
        <li>2. 투자 리서치 분석 서비스</li>
        <li>3. 기타 회사가 정하는 서비스</li>
      </ul>
      <h1 className="font-extrabold text-xl my-3">제5조 서비스 이용</h1>
      {`회원은 회사가 제공하는 서비스를 이용함에 있어 본 약관 및 관련 법령을 준수하여야 하며, 회사는 회원의 서비스 이용을 제한할 수 있습니다.`}
      <h1 className="font-extrabold text-xl my-3">제6조 회원의 의무</h1>
      {`회원은 다음 각 호의 행위를 하여서는 안 됩니다.`}

      <ul className="list-disc ml-5">
        <li>1. 타인의 개인정보를 도용하는 행위</li>
        <li>2. 서비스의 안정적인 운영을 방해하는 행위</li>
        <li>3. 기타 불법적인 행위</li>
      </ul>
      <h1 className="font-extrabold text-xl my-3">제7조 면책 조항</h1>
      {`회사는 다음 각 호의 사유로 인하여 회원에게 발생한 손해에 대하여 책임을 지지 않습니다.`}
      <ul className="list-disc ml-5">
        <li>1. 천재지변 또는 불가항력적인 사유로 인한 손해</li>
        <li>2. 회원의 고의 또는 과실로 인한 손해</li>
        <li>3. 기타 회사의 귀책사유가 없는 사유로 인한 손해</li>
      </ul>
      <h1 className="font-extrabold text-xl my-3">제8조 분쟁 해결</h1>
      {`본 약관과 관련하여 발생한 분쟁에 대하여는 회사의 본사 소재지를 관할하는 법원을 제1심 법원으로 합니다.`}
      <h1 className="font-extrabold text-xl my-3">제9조 기타</h1>
      {`본 약관에 명시되지 않은 사항에 대하여는 관련 법령 및 상관습에 따릅니다.`}
      <h1 className="font-extrabold text-xl my-3">제10조 약관의 해석</h1>
      {`본 약관의 해석에 관하여는 대한민국 법을 적용합니다.`}
      <h1 className="font-extrabold text-xl my-3">제11조 시행일</h1>
      {`본 약관은 2023년 10월 1일부터 시행합니다.`}
      <h1 className="font-extrabold text-xl my-3">제12조 개인정보처리방침</h1>
      {`회사는 회원의 개인정보를 보호하기 위하여 최선을 다하며, 개인정보처리방침에 따라 회원의 개인정보를 안전하게 관리합니다.`}

      <h1 className="font-extrabold text-xl my-3">제13조 서비스 이용 요금</h1>
      {`회사는 서비스 이용에 대한 요금을 부과할 수 있으며, 요금의 부과 및 납부에 관한 사항은 별도의 약정에 따릅니다.`}
      <h1 className="font-extrabold text-xl my-3">제14조 서비스 이용 제한</h1>
      {`회사는 회원이 본 약관을 위반한 경우 서비스 이용을 제한할 수 있으며, 이 경우 회원에게 사전 통지합니다.`}
      <h1 className="font-extrabold text-xl my-3">제15조 서비스 중단</h1>
      {`회사는 다음 각 호의 사유로 인하여 서비스 제공을 중단할 수 있습니다.`}
      <ul className="list-disc ml-5">
        <li>1. 시스템 점검 및 유지보수</li>
        <li>2. 전기통신사업법에 의한 서비스 중단</li>
        <li>3. 기타 회사의 귀책사유가 없는 사유로 인한 서비스 중단</li>
      </ul>
      <h1 className="font-extrabold text-xl my-3">제16조 서비스 이용 계약의 해지</h1>
      {`회원은 언제든지 서비스 이용 계약을 해지할 수 있으며, 이 경우 회사는 회원의 요청에 따라 서비스 이용 계약을 해지합니다.`}
      <h1 className="font-extrabold text-xl my-3">제17조 서비스 이용 계약의 양도</h1>
      {`회원은 회사의 사전 동의 없이 서비스 이용 계약을 양도할 수 없습니다.`}
      <h1 className="font-extrabold text-xl my-3">제18조 서비스 이용 계약의 변경</h1>
      {`회원은 서비스 이용 계약의 내용을 변경할 수 있으며, 이 경우 회사는 회원의 요청에 따라 서비스 이용 계약을 변경합니다.`}
      <h1 className="font-extrabold text-xl my-3">제19조 서비스 이용 계약의 해지</h1>
      {`회사는 회원이 본 약관을 위반한 경우 서비스 이용 계약을 해지할 수 있으며, 이 경우 회원에게 사전 통지합니다.`}
      <h1 className="font-extrabold text-xl my-3">제20조 서비스 이용 계약의 종료</h1>
      {`서비스 이용 계약은 회원이 서비스 이용을 중단하거나 회사가 서비스 이용 계약을 해지한 경우 종료됩니다.`}

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
