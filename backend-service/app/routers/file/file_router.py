import asyncio
import io
from urllib.parse import quote

from core.auth_context import get_email
from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from schemas.common_schema import CreateOut, DeleteOut
from schemas.file.file_schema import (
    FileDetailOut,
    FileDetailsOut,
    FileOut,
    FilesOut,
)
from services.file.file_service import FileService
from utils.common.devextreme_utils import parse_filter_sort
from utils.common.file_utils import SAFE_INLINE_MEDIA_TYPES

router = APIRouter(prefix="/file", tags=["file"])


@router.get(
    "",
    response_model=FilesOut,
    dependencies=[Depends(verify_access_token)],
)
@inject
async def select_file_list(
    request: Request,
    skip: int = Query(0),
    take: int | None = None,
    filter: str | None = None,
    sort: str | None = None,
    file_service: FileService = Depends(Provide[Container.file_service]),
):
    """파일 목록 조회 API"""
    if await request.is_disconnected():
        raise HTTPException(status_code=status.HTTP_499_CLIENT_CLOSED_REQUEST, detail="Client disconnected")

    filter_obj, sort_obj = parse_filter_sort(filter, sort)
    args = {"skip": skip, "take": take, "filter": filter_obj, "sort": sort_obj}

    try:
        items, total_count = file_service.select_file_list(args)
        return FilesOut(items=items, total_count=total_count)
    except asyncio.CancelledError as e:
        raise HTTPException(status_code=status.HTTP_499_CLIENT_CLOSED_REQUEST, detail="Request cancelled") from e


@router.post(
    "",
    response_model=CreateOut,
    dependencies=[Depends(verify_access_token)],
)
@inject
async def upload_files(
    request: Request,
    files: list[UploadFile] = File(...),
    atch_file_id: str | None = Form(None),
    base_path: str | None = Form(None),
    file_service: FileService = Depends(Provide[Container.file_service]),
):
    """파일 업로드 API"""
    if await request.is_disconnected():
        raise HTTPException(status_code=status.HTTP_499_CLIENT_CLOSED_REQUEST, detail="Client disconnected")

    args = {
        "files": files,
        "atch_file_id": atch_file_id,
        "user_id": get_email(),
        "base_path": base_path,
    }

    try:
        result = await file_service.upload_files(args)
        return CreateOut(data=result)
    except asyncio.CancelledError as e:
        raise HTTPException(status_code=status.HTTP_499_CLIENT_CLOSED_REQUEST, detail="Request cancelled") from e


@router.get(
    "/{atch_file_id}",
    response_model=FileOut,
    dependencies=[Depends(verify_access_token)],
)
@inject
async def select_file(
    request: Request,
    atch_file_id: str,
    file_service: FileService = Depends(Provide[Container.file_service]),
):
    """첨부파일 기본 정보 조회"""
    if await request.is_disconnected():
        raise HTTPException(status_code=status.HTTP_499_CLIENT_CLOSED_REQUEST, detail="Client disconnected")

    args = {"atch_file_id": atch_file_id}

    try:
        return file_service.select_file(args)
    except asyncio.CancelledError as e:
        raise HTTPException(status_code=status.HTTP_499_CLIENT_CLOSED_REQUEST, detail="Request cancelled") from e


@router.delete(
    "/{atch_file_id}",
    response_model=DeleteOut,
    dependencies=[Depends(verify_access_token)],
)
@inject
async def delete_file(
    request: Request,
    atch_file_id: str,
    file_service: FileService = Depends(Provide[Container.file_service]),
):
    """첨부파일 전체 삭제"""
    if await request.is_disconnected():
        raise HTTPException(status_code=status.HTTP_499_CLIENT_CLOSED_REQUEST, detail="Client disconnected")

    args = {"atch_file_id": atch_file_id}

    try:
        await file_service.delete_file(args)
    except asyncio.CancelledError as e:
        raise HTTPException(status_code=status.HTTP_499_CLIENT_CLOSED_REQUEST, detail="Request cancelled") from e

    return DeleteOut()


@router.get(
    "/{atch_file_id}/detail",
    response_model=FileDetailsOut,
    dependencies=[Depends(verify_access_token)],
)
@inject
async def select_file_detail_list(
    request: Request,
    atch_file_id: str,
    file_service: FileService = Depends(Provide[Container.file_service]),
):
    """첨부파일 상세 목록 조회"""
    if await request.is_disconnected():
        raise HTTPException(status_code=status.HTTP_499_CLIENT_CLOSED_REQUEST, detail="Client disconnected")

    args = {"atch_file_id": atch_file_id}

    try:
        items, total_count = file_service.select_file_detail_list(args)
        return FileDetailsOut(items=items, total_count=total_count)
    except asyncio.CancelledError as e:
        raise HTTPException(status_code=status.HTTP_499_CLIENT_CLOSED_REQUEST, detail="Request cancelled") from e


@router.get(
    "/{atch_file_id}/detail/{file_sn}",
    response_model=FileDetailOut,
    dependencies=[Depends(verify_access_token)],
)
@inject
async def select_file_detail(
    request: Request,
    atch_file_id: str,
    file_sn: int,
    file_service: FileService = Depends(Provide[Container.file_service]),
):
    """첨부파일 단건 상세 조회"""
    if await request.is_disconnected():
        raise HTTPException(status_code=status.HTTP_499_CLIENT_CLOSED_REQUEST, detail="Client disconnected")

    args = {"atch_file_id": atch_file_id, "file_sn": file_sn}

    try:
        return file_service.select_file_detail(args)
    except asyncio.CancelledError as e:
        raise HTTPException(status_code=status.HTTP_499_CLIENT_CLOSED_REQUEST, detail="Request cancelled") from e


@router.get(
    "/{atch_file_id}/detail/{file_sn}/download",
    response_class=StreamingResponse,
    dependencies=[Depends(verify_access_token)],
)
@inject
async def stream_file_download(
    request: Request,
    atch_file_id: str,
    file_sn: int,
    file_service: FileService = Depends(Provide[Container.file_service]),
):
    """파일 다운로드"""
    if await request.is_disconnected():
        raise HTTPException(status_code=status.HTTP_499_CLIENT_CLOSED_REQUEST, detail="Client disconnected")

    args = {"atch_file_id": atch_file_id, "file_sn": file_sn}

    try:
        # 파일 상세정보 조회
        file_detail = file_service.select_file_detail(args)

        # 파일명 인코딩 (한글 깨짐 방지)
        original_name = file_detail["orignl_file_nm"]
        encoded_filename = quote(original_name)

        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        }

        # 파일 스트리밍 응답 반환
        return StreamingResponse(
            file_service.stream_file_download(args), headers=headers, media_type="application/octet-stream"
        )
    except asyncio.CancelledError as e:
        raise HTTPException(status_code=status.HTTP_499_CLIENT_CLOSED_REQUEST, detail="Request cancelled") from e


@router.get(
    "/{atch_file_id}/detail/{file_sn}/preview",
    response_class=StreamingResponse,
    dependencies=[Depends(verify_access_token)],
)
@inject
async def select_file_detail_for_image_preview(
    request: Request,
    atch_file_id: str,
    file_sn: int,
    size: int | None = Query(default=None, ge=1, le=4096),
    x1: int | None = Query(default=None, ge=0),
    y1: int | None = Query(default=None, ge=0),
    x2: int | None = Query(default=None, ge=0),
    y2: int | None = Query(default=None, ge=0),
    file_service: FileService = Depends(Provide[Container.file_service]),
):
    """이미지 미리보기 API (크롭 및 리사이즈 옵션 지원)"""
    if await request.is_disconnected():
        raise HTTPException(status_code=status.HTTP_499_CLIENT_CLOSED_REQUEST, detail="Client disconnected")

    args = {
        "atch_file_id": atch_file_id,
        "file_sn": file_sn,
        "transform": {
            "size": size,
            "crop": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
        },
    }

    try:
        content, media_type = await file_service.select_file_detail_for_image_preview(args)
        # 안전 래스터만 인라인 렌더, 그 외(레거시 SVG 등)는 강제 다운로드.
        # nosniff + CSP sandbox 로 인라인으로 새더라도 스크립트 실행/스니핑 차단 (저장형 XSS 방어).
        disposition = "inline" if media_type in SAFE_INLINE_MEDIA_TYPES else "attachment"
        headers = {
            "Content-Disposition": disposition,
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        }
        return StreamingResponse(io.BytesIO(content), media_type=media_type, headers=headers)
    except asyncio.CancelledError as e:
        raise HTTPException(status_code=status.HTTP_499_CLIENT_CLOSED_REQUEST, detail="Request cancelled") from e


@router.delete(
    "/{atch_file_id}/detail/{file_sn}",
    response_model=DeleteOut,
    dependencies=[Depends(verify_access_token)],
)
@inject
async def delete_file_detail(
    request: Request,
    atch_file_id: str,
    file_sn: int,
    file_service: FileService = Depends(Provide[Container.file_service]),
):
    """첨부파일 단건 삭제 API"""
    if await request.is_disconnected():
        raise HTTPException(status_code=status.HTTP_499_CLIENT_CLOSED_REQUEST, detail="Client disconnected")

    args = {"atch_file_id": atch_file_id, "file_sn": file_sn}

    try:
        await file_service.delete_file_detail(args)
        return DeleteOut()
    except asyncio.CancelledError as e:
        raise HTTPException(status_code=status.HTTP_499_CLIENT_CLOSED_REQUEST, detail="Request cancelled") from e
