// @vitest-environment jsdom
//
// #440 회귀 그물 — **「없다」와 「못 읽었다」를 가른다.**
//
// Cycle 7 발굴(B-10): 파일 조회가 실패했을 뿐인데 화면이 「첨부된 파일이 없습니다」라고 단언했다.
// 파일은 있는데 사용자는 첨부가 유실됐다고 믿고 다시 올리려 든다.
//
// 원인은 `useFileGroups` 의 catch 가 실패를 `files: []` 로 접은 것이다 — 빈 배열이 「없다」와
// 「모른다」 둘 다를 뜻하게 됐다. 이 레포는 종목 검색에서 같은 구분을 이미 한다
// (`InstrumentsOut.unavailable_reason` — 「그런 종목이 없다」와 「아직 안 받았다」).
//
// 증명하는 것: 조회 실패 시 화면이 「없습니다」라고 말하지 않고, 그것이 부재가 아님을 말한다.
// 증명하지 못하는 것: 실제 네트워크 실패에서 훅이 그 상태를 만드는지 — 여기서는 훅을 대역으로 세운다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

vi.mock("@/env", () => ({ env: { APP_KEY: "fstpl", NODE_ENV: "development" } }));

const useFileGroups = vi.fn();
vi.mock("@/hooks/shared/useFileGroups", () => ({ useFileGroups }));
const showToast = vi.fn();
vi.mock("@/components/shared/Feedback", () => ({ showToast }));

const selectFileDownloadUrl = vi.fn();
vi.mock("@/services/common/fileService", () => ({
  selectFileDownloadUrl,
  selectFilePreviewUrl: vi.fn(),
}));

const { FileListDisplay } = await import("@/components/shared/ui/FileListDisplay");

afterEach(() => {
  cleanup();
  useFileGroups.mockReset();
  showToast.mockReset();
  selectFileDownloadUrl.mockReset();
});

describe("파일 목록이 「없다」와 「못 읽었다」를 가른다 (#440)", () => {
  it("조회에 실패하면 「없습니다」라고 말하지 않는다", () => {
    useFileGroups.mockReturnValue({ files: { files: [], isLoading: false, error: true } });

    render(<FileListDisplay atchFileId="C7B000" />);

    expect(screen.queryByText(/첨부된 파일이 없습니다/)).toBeNull();
    expect(screen.getByText(/불러오지 못했습니다/)).toBeTruthy();
    // 부재가 아님을 명시한다 — 사용자가 다시 올리려 드는 것을 막는 문장이다.
    expect(screen.getByText(/파일이 없다는 뜻은 아닙니다/)).toBeTruthy();
  });

  it("정말 없으면 종전대로 「없습니다」다", () => {
    useFileGroups.mockReturnValue({ files: { files: [], isLoading: false, error: false } });

    render(<FileListDisplay atchFileId="C7B000" />);

    expect(screen.getByText(/첨부된 파일이 없습니다/)).toBeTruthy();
  });
});

describe("단일 다운로드 실패도 화면에 남는다 (#440·B-8)", () => {
  it("한 파일 다운로드가 실패하면 토스트가 뜬다 — 형제 함수와 같은 정책", async () => {
    useFileGroups.mockReturnValue({
      files: {
        files: [{ file_sn: 1, orignl_file_nm: "보고서.pdf", file_ty: "DOC", file_extsn: ".pdf", file_size: 100 }],
        isLoading: false,
        error: false,
      },
    });
    selectFileDownloadUrl.mockRejectedValue(new Error("boom"));

    render(<FileListDisplay atchFileId="C7B000" />);
    const button = screen.getAllByRole("button").find((b) => /다운로드/.test(b.textContent ?? ""));
    expect(button).toBeTruthy();
    button!.click();

    await vi.waitFor(() => expect(showToast).toHaveBeenCalled());
    expect(showToast.mock.calls[0]?.[1]).toBe("error");
  });
});
