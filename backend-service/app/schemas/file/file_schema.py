from pydantic import BaseModel, Field
from schemas.common_schema import CommonEntity, TrimmedBaseModel


class File(TrimmedBaseModel):
    pass


class FileOut(File, CommonEntity):
    atch_file_id: str


class FilesOut(BaseModel):
    items: list[FileOut]
    total_count: int


class FileDetail(TrimmedBaseModel):
    file_stre_cours: str | None = Field(None, max_length=1300)
    stre_file_nm: str | None = Field(None, max_length=200)
    orignl_file_nm: str | None = Field(None, max_length=200)
    file_extsn: str | None = Field(None, max_length=20)
    file_mg: int | None = None
    file_ty: str | None = Field(None, max_length=10)


class FileDetailOut(FileDetail, CommonEntity):
    atch_file_id: str
    file_sn: int


class FileDetailsOut(BaseModel):
    items: list[FileDetailOut]
    total_count: int
