import logging
import os
import re

from typing import Optional

from django.core.files.storage import default_storage
from django.conf import settings
from django.shortcuts import get_object_or_404

from ninja import Query, Form
from ninja import Router
from ninja import File, UploadedFile as NinjaUploadedFile

from dna.models import UploadedFile, DNALocus, Person
from dna.schemas import FileUploadResponse, DNADataListResponse, PersonData, LocusData, DNADataResponse, \
    UpdateLocusRequest, UpdatePersonRequest, CreateLocusRequest
from dna.tasks import process_file_upload, match_file_task

logger = logging.getLogger(__name__)

upload_router = Router()


def _generate_file_url(file_path: str) -> str:
    """
    Generate download URL for file (S3 presigned or local)

    Args:
        file_path: File path in storage (e.g., 'uploads/file.pdf')

    Returns:
        Full download URL
    """
    if not file_path:
        return ''

    try:
        if settings.USE_S3:
            import boto3
            from botocore.client import Config

            # Create S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
                config=Config(signature_version='s3v4')
            )

            # Generate presigned URL (valid for 1 hour)
            url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                    'Key': file_path
                },
                ExpiresIn=3600  # 1 hour
            )

            logger.debug(f"Generated signed URL for {file_path}")
            return url
        else:
            # Local storage
            return default_storage.url(file_path)

    except Exception as e:
        logger.error(f"Failed to generate URL for {file_path}: {e}")
        return file_path  # Fallback to path


@upload_router.post('file/', response={200: FileUploadResponse, 400: FileUploadResponse})
def upload_files(request, file: File[NinjaUploadedFile]):
    try:
        if not file.content_type == 'application/pdf':
            logger.warning(f"Invalid file type uploaded: {file.content_type}")
            return 400, FileUploadResponse(
                success=False,
                errors=["Only PDF files are allowed"],
            )

        # ✅ Save to LOCAL temp directory first
        temp_dir = os.path.join(settings.BASE_DIR, 'media/uploads')
        os.makedirs(temp_dir, exist_ok=True)

        local_file_path = os.path.join(temp_dir, file.name)

        # Write file to local disk
        with open(local_file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        logger.info(f"✅ Saved locally for processing: {local_file_path}")

        result = process_file_upload.apply_async(
            args=[local_file_path, file.name]
        ).get()

        # # Clean up temp file
        if os.path.exists(local_file_path):
            os.remove(local_file_path)
            logger.info(f"Cleaned up temporary file: {local_file_path}")

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

        # ✅ Save to LOCAL temp directory first
        temp_dir = os.path.join(settings.BASE_DIR, 'media/uploads')
        os.makedirs(temp_dir, exist_ok=True)

        local_file_path = os.path.join(temp_dir, file.name)

        # Write file to local disk
        with open(local_file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        logger.info(f"Matching file: {file.name} as {role}")

        # Call matching task (NOT upload task)
        result = match_file_task.apply_async(
            args=[local_file_path, file.name, role]
        ).get(timeout=300)

        # Clean up temp file
        if os.path.exists(local_file_path):
            os.remove(local_file_path)
            logger.info(f"Cleaned up temporary file: {local_file_path}")

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
    Get DNA data with signed download URLs
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

            # ✅ Generate signed URL
            file_url = _generate_file_url(upload.file.name if upload.file else '')

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
                        file=file_url,
                        uploaded_at=upload.uploaded_at.isoformat(),
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
                        file=file_url,
                        uploaded_at=upload.uploaded_at.isoformat(),
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
                    file=file_url,
                    uploaded_at=upload.uploaded_at.isoformat(),
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
    """Update person name and/or role"""
    try:
        person = get_object_or_404(Person, id=person_id)

        updated_fields = []

        # Update name if provided
        if data.name is not None:
            person.name = data.name
            updated_fields.append('name')

        # ✅ Update role if provided
        if data.role is not None:
            # Validate role
            if data.role not in ['father', 'mother', 'child']:
                logger.error(f"Invalid role: {data.role}")
                return 422, {
                    'success': False,
                    'message': f"Invalid role: {data.role}. Must be 'father', 'mother', or 'child'"
                }

            person.role = data.role
            updated_fields.append('role')

        # Check if anything to update
        if not updated_fields:
            return 400, {
                'success': False,
                'message': 'No fields to update'
            }

        person.save()

        logger.info(f"✅ Updated person {person_id}: {', '.join(updated_fields)}")

        return 200, {
            'success': True,
            'message': f'Updated {", ".join(updated_fields)}',
            'data': {
                'id': person.id,
                'name': person.name,
                'role': person.role
            }
        }

    except Exception as e:
        logger.error(f"❌ Failed to update person {person_id}: {e}", exc_info=True)
        return 500, {
            'success': False,
            'message': str(e)
        }


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

        # Log file name (works with both S3 and local)
        file_name = upload.file.name if upload.file else "No file"
        logger.info(f"Deleting upload ID {upload_id}: {file_name}")

        # Delete the file first (works with both S3 and local)
        if upload.file:
            upload.file.delete(save=False)
            logger.info(f"Deleted file: {file_name}")

        # Delete the database record
        upload.delete()

        logger.info(f"Successfully deleted upload ID {upload_id}")

        return 200, {
            'success': True,
            'message': 'Record deleted successfully'
        }

    except UploadedFile.DoesNotExist:
        logger.warning(f"Upload {upload_id} not found")
        return 404, {
            'success': False,
            'message': 'Record not found'
        }
    except Exception as e:
        logger.error(f"Failed to delete upload {upload_id}: {e}", exc_info=True)
        return 404, {
            'success': False,
            'message': 'Failed to delete record'
        }


def validate_allele_format(allele: str) -> tuple[bool, str]:
    """
    Validate allele format

    Valid formats:
    - Integer: "12", "11"
    - Decimal: "12.1", "12.11", "11.2"

    Returns:
        (is_valid, error_message)
    """
    if not allele or not allele.strip():
        return False, "Allele cannot be empty"

    allele = allele.strip()

    # Pattern: digits, optional decimal point with digits
    # Examples: 12, 12.1, 12.11, 8
    pattern = r'^\d+(\.\d+)?$'

    if not re.match(pattern, allele):
        return False, f"Invalid allele format: '{allele}'. Must be numeric (e.g., 12, 12.1, 12.11)"

    return True, ""


@upload_router.post('/persons/{person_id}/loci/', response={201: dict, 400: dict})
def create_locus(request, person_id: int, data: CreateLocusRequest):
    """Create a new locus for a person"""
    try:
        person = get_object_or_404(Person, id=person_id)

        # ✅ Validate allele_1 format
        is_valid, error = validate_allele_format(data.allele_1)
        if not is_valid:
            return 400, {
                'success': False,
                'message': f'Allele 1: {error}'
            }

        # ✅ Validate allele_2 format
        is_valid, error = validate_allele_format(data.allele_2)
        if not is_valid:
            return 400, {
                'success': False,
                'message': f'Allele 2: {error}'
            }

        # Create new locus
        locus = DNALocus.objects.create(
            person=person,
            locus_name=data.locus_name,
            allele_1=data.allele_1,
            allele_2=data.allele_2
        )

        # Update loci_count
        person.loci_count = person.loci.count()
        person.save()

        logger.info(f"✅ Created locus {data.locus_name} for person {person_id}")

        return 201, {
            'success': True,
            'message': f'Created locus {data.locus_name}',
            'data': {
                'id': locus.id,
                'locus_name': locus.locus_name,
                'allele_1': locus.allele_1,
                'allele_2': locus.allele_2
            }
        }

    except Exception as e:
        logger.error(f"❌ Failed to create locus for person {person_id}: {e}")
        return 400, {
            'success': False,
            'message': str(e)
        }


@upload_router.delete('/loci/{locus_id}/', response={200: dict, 404: dict})
def delete_locus(request, locus_id: int):
    """Delete a locus"""
    try:
        locus = get_object_or_404(DNALocus, id=locus_id)
        person = locus.person
        locus_name = locus.locus_name

        locus.delete()

        # Update loci_count
        person.loci_count = person.loci.count()
        person.save()

        logger.info(f"✅ Deleted locus {locus_name} (ID: {locus_id})")

        return 200, {
            'success': True,
            'message': f'Deleted locus {locus_name}'
        }

    except Exception as e:
        logger.error(f"❌ Failed to delete locus {locus_id}: {e}")
        return 404, {
            'success': False,
            'message': str(e)
        }
