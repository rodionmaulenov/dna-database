from typing import List, Optional
from pydantic import BaseModel, Field


class LocusData(BaseModel):
    id: int
    locus_name: str
    allele_1: str
    allele_2: str


class FileInfo(BaseModel):
    """Information about a single uploaded file"""
    id: int
    file: str
    uploaded_at: str


class PersonData(BaseModel):
    id: int
    role: str
    name: str
    loci_count: int
    loci: List[LocusData]
    files: Optional[List[FileInfo]] = None


class MatchResult(BaseModel):
    person_id: int
    name: str
    role: str
    match_percentage: float
    matching_loci: int
    total_loci: int


class LinkInfo(BaseModel):
    person_id: int
    name: str
    role: str


class FileUploadResponse(BaseModel):
    success: bool
    errors: Optional[List[str]] = Field(default=None)
    links: Optional[List[LinkInfo]] = Field(default=None)
    top_matches: Optional[List[MatchResult]] = Field(default=None)

    class Config:
        from_attributes = True


class DNADataResponse(BaseModel):
    id: int
    parent: Optional[PersonData] = None
    child: Optional[PersonData] = None
    children: Optional[List[PersonData]] = None

    class Config:
        from_attributes = True


class DNADataListResponse(BaseModel):
    data: List[DNADataResponse]
    total: int = 0
    page: int = 1
    page_size: int = 20


class UpdateLocusData(BaseModel):
    id: int
    locus_name: str
    allele_1: str
    allele_2: str


class CreateLocusData(BaseModel):
    locus_name: str
    allele_1: str
    allele_2: str


class UpdatePersonRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    loci: Optional[List[UpdateLocusData]] = None
    new_loci: Optional[List[CreateLocusData]] = None
    deleted_loci_ids: Optional[List[int]] = None


class UpdatePersonData(BaseModel):
    id: int
    name: str
    role: str
    loci_count: int
    loci: List[LocusData]


class UpdatePersonResponse(BaseModel):
    success: bool
    message: str
    data: Optional[UpdatePersonData] = None
    errors: Optional[List[str]] = None
