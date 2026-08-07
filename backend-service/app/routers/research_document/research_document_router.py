from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, Request
from schemas.common_schema import CreateOut, DeleteOut
from schemas.research_document.research_document_schema import (
    ResearchDocumentCreateIn,
    ResearchDocumentOut,
    ResearchDocumentsOut,
)
from services.research_document.research_document_service import ResearchDocumentService
from utils.common.devextreme_utils import parse_filter_sort

router = APIRouter(
    prefix="/research-document",
    tags=["research-document"],
    dependencies=[Depends(verify_access_token)],
)


@router.get("", response_model=ResearchDocumentsOut)
@inject
def select_research_document_list(
    request: Request,
    skip: int = Query(0),
    take: int | None = None,
    filter: str | None = None,
    sort: str | None = None,
    research_document_service: ResearchDocumentService = Depends(Provide[Container.research_document_service]),
):
    filter_obj, sort_obj = parse_filter_sort(filter, sort)
    args = {"skip": skip, "take": take, "filter": filter_obj, "sort": sort_obj}

    items, total_count = research_document_service.select_research_document_list(args)
    return ResearchDocumentsOut(items=items, total_count=total_count)


@router.post("", response_model=CreateOut)
@inject
async def insert_research_document(
    request: Request,
    body: ResearchDocumentCreateIn,
    research_document_service: ResearchDocumentService = Depends(Provide[Container.research_document_service]),
):
    research_doc_id = await research_document_service.create_research_document(body.model_dump())
    return CreateOut(data={"research_doc_id": research_doc_id})


@router.get("/{research_doc_id}", response_model=ResearchDocumentOut)
@inject
def select_research_document(
    request: Request,
    research_doc_id: int,
    research_document_service: ResearchDocumentService = Depends(Provide[Container.research_document_service]),
):
    return research_document_service.select_research_document({"research_doc_id": research_doc_id})


@router.delete("/{research_doc_id}", response_model=DeleteOut)
@inject
async def delete_research_document(
    request: Request,
    research_doc_id: int,
    research_document_service: ResearchDocumentService = Depends(Provide[Container.research_document_service]),
):
    await research_document_service.delete_research_document({"research_doc_id": research_doc_id})
    return DeleteOut()
