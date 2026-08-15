// components/shared/ui/primitives/icons.tsx
//
// 아이콘 이름 → 컴포넌트 매핑 (#341 — DevExtreme 아이콘 폰트 대체).
//
// 이관 전에는 `dx-icon-<name>` 클래스 하나로 아이콘을 그렸고, 그 글리프는
// `devextreme/dist/css/dx.light.css` 가 싣는 **DevExpress 아이콘 폰트**에서 나왔다. 그 CSS 를
// 걷어내면 클래스만 남고 글리프가 사라지므로(빈 사각형이 아니라 아무것도 안 그려진다) 아이콘을
// 우리 자산으로 옮겨야 한다. `react-icons`(package.json 기존 의존성, MIT)의 Material Design
// 세트로 옮긴다 — 새 의존성이 아니다.
//
// **이름은 DevExtreme 것을 그대로 유지한다.** 메뉴 아이콘은 **DB 에 이름 문자열로 저장**되어
// 있어서(`schemas/common/menu.ts` 의 목록, 관리자 화면에서 고른 값) 이름을 바꾸면 기존 데이터가
// 전부 깨진다. 그래서 매핑 테이블의 키가 곧 저장값이다.
//
// 목록에 없는 이름(옛 DB 값 등)은 `fallback` 을 그린다 — 빈 자리로 두면 "아이콘이 없는 메뉴"와
// "이름이 틀린 메뉴"를 화면에서 구분할 수 없다.
"use client";

import {
  MdAccountBox,
  MdAdd,
  MdArrowBack,
  MdArrowDownward,
  MdArrowDropDown,
  MdArrowUpward,
  MdAttachFile,
  MdBookmark,
  MdBusiness,
  MdCalendarToday,
  MdCheck,
  MdCheckCircle,
  MdChevronLeft,
  MdChevronRight,
  MdClose,
  MdCloudUpload,
  MdContentCopy,
  MdContentCut,
  MdContentPaste,
  MdCreate,
  MdDelete,
  MdDescription,
  MdDownload,
  MdEmail,
  MdError,
  MdExpandLess,
  MdExpandMore,
  MdFilterAlt,
  MdFolder,
  MdFolderOpen,
  MdFullscreen,
  MdGroup,
  MdHelp,
  MdHome,
  MdImage,
  MdInfo,
  MdInsertChart,
  MdInsertDriveFile,
  MdInventory2,
  MdKey,
  MdLanguage,
  MdLink,
  MdList,
  MdLock,
  MdLockOpen,
  MdLogin,
  MdMenu,
  MdMoreHoriz,
  MdNotifications,
  MdPerson,
  MdPictureAsPdf,
  MdPrint,
  MdPushPin,
  MdRefresh,
  MdRemove,
  MdSave,
  MdSearch,
  MdSend,
  MdSettings,
  MdShare,
  MdShoppingCart,
  MdSmartToy,
  MdTableChart,
  MdUndo,
  MdVisibility,
  MdVisibilityOff,
  MdWarning,
} from "react-icons/md";
import type { IconType } from "react-icons";

/**
 * 이관 전 `dx-icon-*` 이름 → react-icons 컴포넌트.
 *
 * 코드에서 쓰는 이름은 전부(전수 grep, #341) 여기 있다. 그 밖의 항목은 메뉴 아이콘 선택기가
 * 제공하던 목록 중 실제로 메뉴에 쓸 만한 것들이다.
 *
 * 메뉴 편집 폼의 아이콘 선택기(`MenuDetailForm` 의 `ICON_NAMES`)가 이 테이블의 키에서
 * 생성되므로 목록과 실물이 어긋날 수 없다. (#341 이전에는 `schemas/common/menu.ts` 의
 * `DX_ICONS` 가 그 자리였고, 같은 PR 이 그 상수를 지웠다.)
 */
export const ICON_COMPONENTS: Record<string, IconType> = {
  accountbox: MdAccountBox,
  activefolder: MdFolderOpen,
  add: MdAdd,
  arrowback: MdArrowBack,
  arrowdown: MdArrowDownward,
  arrowleft: MdChevronLeft,
  arrowright: MdChevronRight,
  arrowup: MdArrowUpward,
  attach: MdAttachFile,
  back: MdArrowBack,
  bell: MdNotifications,
  bookmark: MdBookmark,
  // 기본 시드(`prisma/init/seed.sql` 의 포트폴리오 메뉴)가 쓰는 값 — 매핑에 없으면
  // 클린 설치부터 fallback 아이콘이 뜬다.
  box: MdInventory2,
  bulletlist: MdList,
  cart: MdShoppingCart,
  chart: MdInsertChart,
  check: MdCheck,
  chevrondown: MdExpandMore,
  chevronleft: MdChevronLeft,
  chevronnext: MdChevronRight,
  chevronprev: MdChevronLeft,
  chevronright: MdChevronRight,
  chevronup: MdExpandLess,
  clear: MdClose,
  clearcircle: MdClose,
  clock: MdCalendarToday,
  close: MdClose,
  copy: MdContentCopy,
  cut: MdContentCut,
  description: MdDescription,
  doc: MdDescription,
  docfile: MdDescription,
  docxfile: MdDescription,
  download: MdDownload,
  edit: MdCreate,
  email: MdEmail,
  errorcircle: MdError,
  event: MdCalendarToday,
  expand: MdExpandMore,
  export: MdDownload,
  exportpdf: MdPictureAsPdf,
  exportxlsx: MdTableChart,
  eyeclose: MdVisibilityOff,
  eyeopen: MdVisibility,
  favorites: MdBookmark,
  file: MdInsertDriveFile,
  filter: MdFilterAlt,
  find: MdSearch,
  floppy: MdSave,
  folder: MdFolder,
  fullscreen: MdFullscreen,
  globe: MdLanguage,
  group: MdGroup,
  help: MdHelp,
  hierarchy: MdAccountBox,
  home: MdHome,
  image: MdImage,
  import: MdCloudUpload,
  inactivefolder: MdFolder,
  info: MdInfo,
  key: MdKey,
  link: MdLink,
  lock: MdLock,
  login: MdLogin,
  menu: MdMenu,
  message: MdEmail,
  minus: MdRemove,
  money: MdBusiness,
  more: MdMoreHoriz,
  optionsgear: MdSettings,
  paste: MdContentPaste,
  pdffile: MdPictureAsPdf,
  photo: MdImage,
  pin: MdPushPin,
  plus: MdAdd,
  preferences: MdSettings,
  print: MdPrint,
  product: MdBusiness,
  pulldown: MdArrowDropDown,
  refresh: MdRefresh,
  remove: MdClose,
  revert: MdUndo,
  robot: MdSmartToy,
  runner: MdPerson,
  save: MdSave,
  search: MdSearch,
  send: MdSend,
  share: MdShare,
  taskcomplete: MdCheckCircle,
  textdocument: MdDescription,
  trash: MdDelete,
  txtfile: MdDescription,
  undo: MdUndo,
  unlock: MdLockOpen,
  upload: MdCloudUpload,
  user: MdPerson,
  warning: MdWarning,
  xlsfile: MdTableChart,
  xlsxfile: MdTableChart,
};

/** 선택기·검증에서 쓰는 이름 목록 (정렬 고정 — 화면 순서가 렌더마다 흔들리지 않게). */
export const ICON_NAMES = Object.keys(ICON_COMPONENTS).sort();

interface Props {
  /** `ICON_COMPONENTS` 의 키. 모르는 이름이면 fallback 을 그린다. */
  name?: string | null;
  className?: string;
  /** px. 미지정이면 현재 글꼴 크기(`1em`)를 따른다 — 이관 전 아이콘 폰트와 같은 성질. */
  size?: number;
  /**
   * 아이콘만으로 의미를 전달할 때 붙일 접근명. 옆에 글자가 있어 장식일 뿐이면 생략한다
   * (`aria-hidden` 이 붙는다).
   */
  label?: string;
}

/**
 * 이름으로 아이콘을 그린다.
 *
 * ```tsx
 * <Icon name="refresh" label="새로고침" />   // 아이콘만 있는 버튼
 * <Icon name="folder" /> 문서함              // 옆에 글자가 있으면 장식
 * ```
 */
/**
 * 이름이 이 테이블에 **자기 속성으로** 있는지 본다.
 *
 * `ICON_COMPONENTS[name]` 만 쓰면 객체 리터럴이 상속한 `Object.prototype` 멤버가 잡힌다 —
 * `"constructor"`·`"valueOf"`·`"__proto__"` 는 undefined 가 아닌 값을 돌려주므로 `|| fallback`
 * 이 발동하지 않고, 그 값이 컴포넌트로 호출돼 렌더가 예외로 죽는다. 메뉴 `icon` 은
 * `schemas/common/menu.ts` 에서 열거가 아니라 자유 문자열이고(`str().max(50)`), 사이드바가
 * 모든 라우트에서 그 값을 렌더하므로 DB 값 하나로 내비게이션 전체가 죽을 수 있었다.
 * 이관 전에는 `dx-icon-<name>` 클래스 문자열이라 어떤 값이든 무해했다 — #341 이 새로 만든 표면이다.
 */
export function resolveIconComponent(name: string | null | undefined): IconType {
  if (!name || !Object.hasOwn(ICON_COMPONENTS, name)) return MdInsertDriveFile;
  return ICON_COMPONENTS[name];
}

export function Icon({ name, className, size, label }: Props) {
  const Component = resolveIconComponent(name);
  return (
    <Component
      className={className}
      size={size}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    />
  );
}
