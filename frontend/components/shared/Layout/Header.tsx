"use client";

import { useRouter } from "next/navigation";
import { signOut } from "@/lib/auth/auth-client";
import { showMessage } from "@/components/shared/Feedback";
import { Button } from "@/components/shared/ui/Button";

interface Props {
  isDrawerOpen: boolean;
  setIsDrawerOpen: (isOpen: boolean) => void;
}

/**
 * 관리자 화면 상단 바 (#341 — DevExtreme `Toolbar` 이관).
 *
 * `Toolbar` 는 before/center/after 세 구역에 위젯을 배치해 주는 것이 전부였다 — flex 세 칸으로
 * 그대로 옮겼다. 좌우 구역에 같은 기본 폭(`basis-1/4`)을 줘야 가운데 제목이 화면 중앙에 온다.
 *
 * `<header>` 로 감싸 랜드마크를 남긴다(DevExtreme 은 `<div>` 였다) — 스크린리더 사용자가
 * 상단 바로 바로 건너뛸 수 있다.
 */
export function Header({ isDrawerOpen, setIsDrawerOpen }: Props) {
  const router = useRouter();

  const handleSignOut = () => {
    showMessage("알림", <div>로그아웃 하시겠습니까?</div>, {
      type: "confirm",
      callback: {
        onCancel: () => {
          return;
        },
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
  };

  return (
    <header className="flex flex-none items-center gap-2 border-b bg-white px-2 py-1">
      <div className="flex basis-1/4 items-center">
        <Button
          icon={isDrawerOpen ? "close" : "menu"}
          stylingMode="text"
          type="normal"
          hint={isDrawerOpen ? "메뉴 닫기" : "메뉴 열기"}
          onClick={() => setIsDrawerOpen(!isDrawerOpen)}
        />
      </div>

      <div className="flex flex-1 justify-center truncate text-sm font-medium text-gray-900">관리자 페이지</div>

      <div className="flex basis-1/4 items-center justify-end gap-1">
        <Button
          icon="user"
          text="마이페이지"
          stylingMode="text"
          type="normal"
          onClick={() => router.push("/admin/common/mypage")}
        />
        <Button icon="runner" text="로그아웃" stylingMode="text" type="normal" onClick={handleSignOut} />
      </div>
    </header>
  );
}
