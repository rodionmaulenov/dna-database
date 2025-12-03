import logging
from typing import List, Optional

from dna.schemas import PersonData, LocusData, FileInfo, DNADataResponse
from dna.services import get_storage_service
from dna.models import Person

logger = logging.getLogger(__name__)
storage_service = get_storage_service()


def _build_loci_data(person: Person) -> List[LocusData]:
    """Build loci data list for a person"""
    return [
        LocusData(
            id=locus.pk,
            locus_name=locus.locus_name,
            allele_1=locus.allele_1,
            allele_2=locus.allele_2,
        )
        for locus in person.loci.all()
    ]


def _build_files_data(person: Person) -> List[FileInfo]:
    """Build files data list for a person"""
    files = person.uploaded_files.all().order_by('-uploaded_at')

    return [
        FileInfo(
            id=f.pk,
            file=storage_service.generate_url(f.file.name if f.file else ''),
            uploaded_at=f.uploaded_at.isoformat()
        )
        for f in files
    ]


def _build_person_data(person: Person) -> PersonData:
    """Build complete PersonData for a single person"""
    return PersonData(
        id=person.pk,
        role=person.role,
        name=person.name,
        loci_count=person.loci_count,
        loci=_build_loci_data(person),
        files=_build_files_data(person)
    )


def build_parent_with_children_response(parent: Person) -> Optional[DNADataResponse]:
    """Build DNADataResponse for a parent with all their children (optimized)"""
    try:
        parent_data = _build_person_data(parent)

        # ✅ Use pre-loaded data (no new queries)
        children_dict = {}
        for upload_file in parent.uploaded_files.all():  # Already prefetched
            for child in upload_file.file_children:  # Already prefetched via Prefetch
                if child.id not in children_dict:
                    children_dict[child.id] = child

        # Build children data from dictionary
        children_data = [_build_person_data(child) for child in children_dict.values()]

        return DNADataResponse(
            id=parent.pk,
            parent=parent_data,
            child=children_data[0] if len(children_data) == 1 else None,
            children=children_data if len(children_data) > 1 else None,
        )

    except Exception as e:
        logger.error(f"❌ build_parent_with_children_response error: {e}", exc_info=True)
        return None


def build_orphan_child_response(child: Person) -> Optional[DNADataResponse]:
    """
    Build DNADataResponse for orphan child (no parent).

    Args:
        child: Person object with role='child'

    Returns:
        DNADataResponse with parent=None
    """
    try:
        child_data = _build_person_data(child)

        return DNADataResponse(
            id=child.pk,
            parent=None,
            child=child_data,
            children=None,
        )

    except Exception as e:
        logger.error(f"❌ build_orphan_child_response error: {e}", exc_info=True)
        return None