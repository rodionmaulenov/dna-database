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
    """
    Build DNADataResponse for a parent with all their children

    Args:
        parent: Parent Person object (father or mother)

    Returns:
        DNADataResponse with parent and all related children, or None if error
    """
    try:
        # Build parent data
        parent_data = _build_person_data(parent)

        # Find all children linked through any shared file
        children_ids = set()
        for upload_file in parent.uploaded_files.all():
            file_children = upload_file.persons.filter(role='child')
            children_ids.update(child.id for child in file_children)

        # Get all unique children with prefetch
        children = Person.objects.filter(
            id__in=children_ids
        ).prefetch_related('loci', 'uploaded_files')

        # Build children data
        children_data = [_build_person_data(child) for child in children]

        # Return response with appropriate child structure
        return DNADataResponse(
            id=parent.pk,  # Use parent ID as record ID
            parent=parent_data,
            child=children_data[0] if len(children_data) == 1 else None,
            children=children_data if len(children_data) > 1 else None,
        )

    except Exception as e:
        logger.error(f"❌ build_parent_with_children_response error: {e}", exc_info=True)
        return None


# ✅ Keep old function for backward compatibility (filtering by upload)
def build_person_response(upload, all_persons_in_file) -> Optional[DNADataResponse]:
    """
    Build DNADataResponse for a single upload (legacy)

    Args:
        upload: UploadedFile object
        all_persons_in_file: QuerySet of Person objects in this file

    Returns:
        DNADataResponse or None if error
    """
    try:
        # Get parent
        parent = all_persons_in_file.filter(role__in=['father', 'mother']).first()
        parent_data = _build_person_data(parent) if parent else None

        # Get children
        children = all_persons_in_file.filter(role='child')
        children_data = [_build_person_data(child) for child in children]

        # Return response with appropriate child structure
        return DNADataResponse(
            id=upload.pk,
            parent=parent_data,
            child=children_data[0] if len(children_data) == 1 else None,
            children=children_data if len(children_data) > 1 else None,
        )

    except Exception as e:
        logger.error(f"❌ build_person_response error: {e}", exc_info=True)
        return None