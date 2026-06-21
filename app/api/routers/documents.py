from fastapi import APIRouter, Depends, UploadFile, status

from app.api.dependencies import get_current_employee, get_document_service
from app.models.employee import Employee
from app.schemas.document import DocumentRead, UploadResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF document for RAG indexing",
)
async def upload_document(
    file: UploadFile,
    service: DocumentService = Depends(get_document_service),
    _current_employee: Employee = Depends(get_current_employee),
) -> UploadResponse:
    return await service.upload(file)


@router.get(
    "/",
    response_model=list[DocumentRead],
    summary="List all uploaded documents",
)
async def list_documents(
    service: DocumentService = Depends(get_document_service),
    _current_employee: Employee = Depends(get_current_employee),
) -> list[DocumentRead]:
    return await service.list_documents()
