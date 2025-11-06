import logging
import os

from typing import Optional

from django.core.files.storage import default_storage
from django.conf import settings
from django.shortcuts import get_object_or_404

from ninja import Query, Form
from ninja import Router
from ninja import File, UploadedFile as NinjaUploadedFile

from dna.models import UploadedFile, DNALocus, Person
from dna.schemas import FileUploadResponse, DNADataListResponse, PersonData, LocusData, DNADataResponse, \
    UpdateLocusRequest, UpdatePersonRequest
from dna.tasks import process_file_upload, match_file_task

logger = logging.getLogger(__name__)

upload_router = Router()


@upload_router.post('file/', response={200: FileUploadResponse, 400: FileUploadResponse})
def upload_files(request, file: File[NinjaUploadedFile]):
    try:
        if not file.content_type == 'application/pdf':
            logger.warning(f"Invalid file type uploaded: {file.content_type}")
            return 400, FileUploadResponse(
                success=False,
                errors=["Only PDF files are allowed"],
            )

        relative_path = default_storage.save(f'uploads/{file.name}', file)
        absolute_path = os.path.join(settings.MEDIA_ROOT, relative_path)

        logger.info(f"Processing upload: {file.name}")

        result = process_file_upload.apply_async(
            args=[absolute_path, file.name]
        ).get()

        # Clean up temp file
        if os.path.exists(absolute_path):
            os.remove(absolute_path)
            logger.info(f"Cleaned up temporary file: {absolute_path}")

        if result.get('success'):
            logger.info(f"Successfully processed: {file.name}")
            return 200, FileUploadResponse(
                success=True,
                errors=None,
            )
        else:
            logger.error(f"Processing failed for {file.name}: {result.get('errors')}")
            return 400, FileUploadResponse(
                success=False,
                errors=result.get('errors', []),
            )

    except Exception as e:
        logger.error(f"upload_files view error for {file.name}: {e}", exc_info=True)
        return 400, FileUploadResponse(
            success=False,
            errors=["Server error occurred"],
        )


@upload_router.post('match/', response={200: FileUploadResponse, 400: FileUploadResponse})
def match_file(request, file: File[NinjaUploadedFile], role: str = Form(...)):
    """
    Extract DNA from PDF and find matches - does NOT save to database
    """
    try:
        if not file.content_type == 'application/pdf':
            logger.warning(f"Invalid file type uploaded: {file.content_type}")
            return 400, FileUploadResponse(
                success=False,
                errors=["Only PDF files are allowed"],
            )

        # Validate role
        if role not in ['father', 'mother', 'child']:
            logger.warning(f"Invalid role: {role}")
            return 400, FileUploadResponse(
                success=False,
                errors=["Invalid role. Must be 'father', 'mother', or 'child'"],
            )

        # Save temporarily
        relative_path = default_storage.save(f'temp/{file.name}', file)
        absolute_path = os.path.join(settings.MEDIA_ROOT, relative_path)

        logger.info(f"Matching file: {file.name} as {role}")

        # Call matching task (NOT upload task)
        result = match_file_task.apply_async(
            args=[absolute_path, file.name, role]
        ).get(timeout=300)

        # Clean up temp file
        if os.path.exists(absolute_path):
            os.remove(absolute_path)
            logger.info(f"Cleaned up temporary file: {absolute_path}")

        if result.get('success'):
            logger.info(f"Successfully matched: {file.name}")
            return 200, FileUploadResponse(
                success=True,
                errors=None,
                top_matches=result.get('top_matches', [])
            )
        else:
            logger.error(f"Matching failed for {file.name}: {result.get('errors')}")
            return 400, FileUploadResponse(
                success=False,
                errors=result.get('errors', []),
            )

    except Exception as e:
        logger.error(f"match_file view error for {file.name}: {e}", exc_info=True)
        return 400, FileUploadResponse(
            success=False,
            errors=["Server error occurred"],
        )


@upload_router.get('list/', response=DNADataListResponse)
def get_all_dna_data(
        request,
        person_id: Optional[int] = Query(None, description="Filter by specific person ID"),
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(50, ge=1, le=100, description="Items per page")
):
    """
    Get DNA data with overall confidence and upload dates from UploadedFile
    """
    try:
        uploads_query = UploadedFile.objects.prefetch_related(
            'persons',
            'persons__loci'
        )

        if person_id:
            uploads_query = uploads_query.filter(
                persons__id=person_id
            ).distinct()

        total_count = uploads_query.count()
        start = (page - 1) * page_size
        end = start + page_size

        uploads = uploads_query[start:end]

        result = []

        for upload in uploads:
            persons = upload.persons.all()

            if person_id:
                matching_person = persons.filter(id=person_id).first()

                if not matching_person:
                    continue

                if matching_person.role in ['father', 'mother']:
                    parent = matching_person
                    child = persons.filter(role='child').first()

                    parent_loci = list(parent.loci.all())
                    parent_data = PersonData(
                        id=parent.id,
                        role=parent.role,
                        name=parent.name,
                        loci_count=parent.loci_count,
                        loci=[
                            LocusData(
                                id=locus.id,
                                locus_name=locus.locus_name,
                                allele_1=locus.allele_1,
                                allele_2=locus.allele_2,
                            ) for locus in parent_loci
                        ]
                    )

                    child_data = None
                    if child:
                        child_loci = list(child.loci.all())
                        child_data = PersonData(
                            id=child.id,
                            role=child.role,
                            name=child.name,
                            loci_count=child.loci_count,
                            loci=[
                                LocusData(
                                    id=locus.id,
                                    locus_name=locus.locus_name,
                                    allele_1=locus.allele_1,
                                    allele_2=locus.allele_2,
                                ) for locus in child_loci
                            ]
                        )

                    result.append(DNADataResponse(
                        id=upload.id,
                        file=upload.file.name if upload.file else '',
                        uploaded_at=upload.uploaded_at.isoformat(),
                        overall_confidence=upload.overall_confidence,
                        parent=parent_data,
                        child=child_data
                    ))

                else:  # child
                    child = matching_person
                    parent = persons.filter(role__in=['father', 'mother']).first()

                    child_loci = list(child.loci.all())
                    child_data = PersonData(
                        id=child.id,
                        role=child.role,
                        name=child.name,
                        loci_count=child.loci_count,
                        loci=[
                            LocusData(
                                id=locus.id,
                                locus_name=locus.locus_name,
                                allele_1=locus.allele_1,
                                allele_2=locus.allele_2,
                            ) for locus in child_loci
                        ]
                    )

                    parent_data = None
                    if parent:
                        parent_loci = list(parent.loci.all())
                        parent_data = PersonData(
                            id=parent.id,
                            role=parent.role,
                            name=parent.name,
                            loci_count=parent.loci_count,
                            loci=[
                                LocusData(
                                    id=locus.id,
                                    locus_name=locus.locus_name,
                                    allele_1=locus.allele_1,
                                    allele_2=locus.allele_2,
                                ) for locus in parent_loci
                            ]
                        )

                    result.append(DNADataResponse(
                        id=upload.id,
                        file=upload.file.name if upload.file else '',
                        uploaded_at=upload.uploaded_at.isoformat(),
                        overall_confidence=upload.overall_confidence,
                        parent=parent_data,
                        child=child_data
                    ))

            else:
                # No filter
                parent = persons.filter(role__in=['father', 'mother']).first()
                child = persons.filter(role='child').first()

                parent_data = None
                if parent:
                    parent_loci = list(parent.loci.all())
                    parent_data = PersonData(
                        id=parent.id,
                        role=parent.role,
                        name=parent.name,
                        loci_count=parent.loci_count,
                        loci=[
                            LocusData(
                                id=locus.id,
                                locus_name=locus.locus_name,
                                allele_1=locus.allele_1,
                                allele_2=locus.allele_2,
                            ) for locus in parent_loci
                        ]
                    )

                child_data = None
                if child:
                    child_loci = list(child.loci.all())
                    child_data = PersonData(
                        id=child.id,
                        role=child.role,
                        name=child.name,
                        loci_count=child.loci_count,
                        loci=[
                            LocusData(
                                id=locus.id,
                                locus_name=locus.locus_name,
                                allele_1=locus.allele_1,
                                allele_2=locus.allele_2,
                            ) for locus in child_loci
                        ]
                    )

                result.append(DNADataResponse(
                    id=upload.id,
                    file=upload.file.name if upload.file else '',
                    uploaded_at=upload.uploaded_at.isoformat(),
                    overall_confidence=upload.overall_confidence,
                    parent=parent_data,
                    child=child_data
                ))

        return DNADataListResponse(
            data=result,
            total=total_count,
            page=page,
            page_size=page_size
        )

    except Exception as e:
        logger.error(f"get_all_dna_data error: {e}")
        return DNADataListResponse(data=[], total=0, page=1, page_size=page_size)


@upload_router.patch('/persons/{person_id}/')
def update_person(request, person_id: int, data: UpdatePersonRequest):
    """Update person name"""
    try:
        person = get_object_or_404(Person, id=person_id)
        person.name = data.name
        person.save()

        logger.info(f"Updated person {person_id} name to: {data.name}")

        return {
            'success': True,
            'message': f'Updated name to {data.name}',
            'data': {'id': person.id, 'name': person.name}
        }
    except Exception as e:
        logger.error(f"Failed to update person {person_id}: {e}")
        return {'success': False, 'message': str(e)}


@upload_router.patch('/loci/{locus_id}/')
def update_locus(request, locus_id: int, data: UpdateLocusRequest):
    """Update locus alleles"""
    try:
        locus = get_object_or_404(DNALocus, id=locus_id)
        locus.allele_1 = data.allele_1
        locus.allele_2 = data.allele_2
        locus.save()

        logger.info(f"Updated locus {locus_id}: {data.allele_1}, {data.allele_2}")

        return {
            'success': True,
            'message': f'Updated {locus.locus_name}',
            'data': {
                'id': locus.id,
                'locus_name': locus.locus_name,
                'allele_1': locus.allele_1,
                'allele_2': locus.allele_2
            }
        }
    except Exception as e:
        logger.error(f"Failed to update locus {locus_id}: {e}")
        return {'success': False, 'message': str(e)}


@upload_router.delete('/file/{upload_id}/', response={200: dict, 404: dict})
def delete_upload(request, upload_id: int):
    """
    Delete an uploaded file and all related data (persons + loci)

    Args:
        upload_id: ID of UploadedFile to delete

    Returns:
        Success message or error
    """
    try:
        # Get the upload record
        upload = get_object_or_404(UploadedFile, id=upload_id)

        # Get file path before deletion
        file_path = upload.file.path if upload.file else None

        upload.delete()

        # Delete physical file from disk
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted file: {file_path}")

        logger.info(f"Successfully deleted upload ID {upload_id}")

        return 200, {
            'success': True,
            'message': f'Record deleted successfully'
        }

    except Exception as e:
        logger.error(f"Failed to delete upload {upload_id}: {e}", exc_info=True)
        return 404, {
            'success': False,
            'message': 'Failed to delete record'
        }