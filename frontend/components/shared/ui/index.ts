// components/shared/ui/index.ts

// 아래 「N% 사용」 구분은 실측이 아니라 최초 스캐폴딩 시점의 임의 표기였다(#341 O8-3 전수
// 조사 확인 — git blame 상 최초 커밋 이후 갱신 이력 없음). 대신 실제 소비자 유무로만 나눈다.
// 소비자 0으로 확인된 13개 중 11개(Autocomplete·Lookup·Slider·RangeSlider·ColorBox·
// DropDownBox·Calendar·HtmlEditor·ProgressBar·Switch·RadioGroup)는 삭제했다(#341).
// 남은 2개는 각각 사유가 있어 유지한다:
//   - DateBox: 앱 코드 소비자는 0이지만 .claude/docs/design-patterns-frontend.md 의
//     스캐폴드 템플릿(신규 엔티티 date 필드 표준 매핑)이 이 이름을 가리킨다 — 지우면
//     다음 스캐폴딩 산출물이 깨진다.
//     정적 스캔(JSX 출현 기준)이 놓친 실사용 사례.

// ========================================
// 폼 입력 컴포넌트
// ========================================
export { Button } from "./Button";
export type { Props as ButtonProps, ActionButton } from "./Button";
export { TextBox } from "./TextBox"; // 텍스트 입력 (마스크 기능 포함)
export { NumberBox } from "./NumberBox"; // 숫자 입력
export { SelectBox } from "./SelectBox"; // 드롭다운 선택
export { DateBox } from "./DateBox"; // 날짜 선택 — 앱 소비자 0, 스캐폴드 템플릿 의존으로 유지(위 주석 참조)
export { TextArea } from "./TextArea"; // 긴 텍스트 입력
export { CheckBox } from "./CheckBox"; // 체크박스
export { CheckBoxGroup } from "./CheckBoxGroup"; // 체크박스그룹
export { TagBox } from "./TagBox"; // 다중 선택 태그
export { TabPanel, TabContent } from "./TabPanel"; // 탭 네비게이션
export { Popup } from "./Popup"; // 팝업/모달 다이얼로그
export { FileUploader, type FileUploaderRef } from "./FileUploader"; // 파일 업로드

// ========================================
// 📋 표시 컴포넌트들
// ========================================
export { FileListDisplay } from "./FileListDisplay"; // 파일 목록 표시
export { MarkdownRenderer } from "./MarkdownRenderer"; // 별점 입력
export { ExpandableCard } from "./ExpandableCard"; // 펼침/접힘 가능한 카드 (청크/이미지 등)
