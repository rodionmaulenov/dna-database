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
    files: Optional[List[FileInfo]] = None  # ✅ NEW: All files for this person


class MatchResult(BaseModel):
    person_id: int
    name: str
    role: str
    match_percentage: float
    matching_loci: int
    total_loci: int


class FileUploadResponse(BaseModel):
    success: bool
    errors: Optional[List[str]] = Field(default=None)
    top_matches: Optional[List[MatchResult]] = Field(default=None)

    class Config:
        from_attributes = True


class DNADataResponse(BaseModel):
    id: int
    overall_confidence: float = 1.0
    parent: Optional[PersonData] = None
    child: Optional[PersonData] = None  # Single child (backward compatibility)
    children: Optional[List[PersonData]] = None  # Multiple children

    class Config:
        from_attributes = True


class DNADataListResponse(BaseModel):
    data: List[DNADataResponse]
    total: int = 0  # Total number of records
    page: int = 1  # Current page
    page_size: int = 20  # Items per page


class UpdatePersonRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None


class UpdateLocusRequest(BaseModel):
    allele_1: str
    allele_2: str


class CreateLocusRequest(BaseModel):
    locus_name: str
    allele_1: str
    allele_2: str