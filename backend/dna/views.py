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
    UpdateLocusRequest, UpdatePersonRequest, CreateLocusRequest, FileInfo
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
        ).get(timeout=360)

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
        page_size: int = Query(20, ge=1, le=100, description="Items per page")
):
    """
    Get DNA data with signed download URLs
    Shows unique parents ordered by most recent file upload
    """
    try:
        if person_id:
            # Get specific person
            person = Person.objects.get(id=person_id)

            # Get all files for this person
            person_files = person.uploaded_files.all().order_by('-uploaded_at')

            # Get the most recent file
            if person_files.exists():
                upload = person_files.first()

                # Get all persons in this file
                all_persons_in_file = upload.persons.all()

                result = _build_response_for_upload(upload, all_persons_in_file)

                return DNADataListResponse(
                    data=[result] if result else [],
                    total=1,
                    page=1,
                    page_size=page_size
                )
            else:
                return DNADataListResponse(data=[], total=0, page=1, page_size=page_size)

        else:
            # ✅ NEW: Get all uploads ordered by newest first
            all_uploads = UploadedFile.objects.all().order_by('-uploaded_at')

            total_count = all_uploads.count()
            start = (page - 1) * page_size
            end = start + page_size

            uploads = all_uploads[start:end]

            # Build responses
            result = []
            seen_parents = set()  # ✅ Track which parents we've already shown

            for upload in uploads:
                all_persons_in_file = upload.persons.all()

                # ✅ Check if this upload has a parent
                parent = all_persons_in_file.filter(role__in=['father', 'mother']).first()

                if parent:
                    # ✅ Only show parent once (their most recent upload)
                    if parent.id not in seen_parents:
                        seen_parents.add(parent.id)
                        response = _build_response_for_upload(upload, all_persons_in_file)
                        if response:
                            result.append(response)
                else:
                    # ✅ No parent (orphan children) - always show
                    response = _build_response_for_upload(upload, all_persons_in_file)
                    if response:
                        result.append(response)

            return DNADataListResponse(
                data=result,
                total=len(result),  # ✅ Actual count after deduplication
                page=page,
                page_size=page_size
            )

    except Exception as e:
        logger.error(f"get_all_dna_data error: {e}", exc_info=True)
        return DNADataListResponse(data=[], total=0, page=1, page_size=page_size)


def _build_response_for_upload(upload, all_persons_in_file):
    """
    Helper function to build DNADataResponse for a single upload
    """
    try:
        parent = all_persons_in_file.filter(role__in=['father', 'mother']).first()
        children = all_persons_in_file.filter(role='child')

        # Build parent data
        parent_data = None
        if parent:
            parent_loci = list(parent.loci.all())

            # ✅ Get ALL files for this parent (not just current upload)
            parent_files = parent.uploaded_files.all().order_by('-uploaded_at')

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
                ],
                files=[  # ✅ ALL parent files
                    FileInfo(
                        id=f.id,
                        file=_generate_file_url(f.file.name if f.file else ''),
                        uploaded_at=f.uploaded_at.isoformat()
                    ) for f in parent_files
                ]
            )

        # Build children data
        children_data = []
        for child in children:
            child_loci = list(child.loci.all())

            # ✅ Get ALL files for THIS specific child
            child_files = child.uploaded_files.all().order_by('-uploaded_at')

            children_data.append(PersonData(
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
                ],
                files=[  # ✅ ALL files for this child
                    FileInfo(
                        id=f.id,
                        file=_generate_file_url(f.file.name if f.file else ''),
                        uploaded_at=f.uploaded_at.isoformat()
                    ) for f in child_files
                ]
            ))

        return DNADataResponse(
            id=upload.pk,
            parent=parent_data,
            child=children_data[0] if len(children_data) == 1 else None,
            children=children_data if len(children_data) > 1 else None,
        )

    except Exception as e:
        logger.error(f"_build_response_for_upload error: {e}", exc_info=True)
        return None


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
                'id': person.pk,
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
                'id': locus.pk,
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


@upload_router.delete('/person/{person_id}/', response={200: dict, 404: dict})
def delete_person(request, person_id: int):
    """
    Delete a person and all related data

    If parent: deletes parent + all children + all files from S3
    If child: deletes only that child + their file from S3

    Args:
        person_id: ID of Person to delete

    Returns:
        Success message or error
    """
    try:
        # Get the person
        person = get_object_or_404(Person, id=person_id)
        person_name = person.name
        person_role = person.role

        logger.info(f"Deleting person ID {person_id}: {person_name} ({person_role})")

        if person_role in ['father', 'mother']:
            # ✅ PARENT DELETION

            # Get all files associated with this parent
            parent_files = person.uploaded_files.all()
            file_count = parent_files.count()

            # Get all children in those files
            children_in_files = Person.objects.filter(
                uploaded_files__in=parent_files,
                role='child'
            ).distinct()

            children_count = children_in_files.count()

            # Delete all children first
            for child in children_in_files:
                logger.info(f"  Deleting child: {child.name}")
                child.delete()

            # Delete all files from S3 and database
            for file_obj in parent_files:
                if file_obj.file:
                    file_obj.file.delete(save=False)  # Delete from S3
                    logger.info(f"  Deleted file from S3: {file_obj.file.name}")
                file_obj.delete()  # Delete from database

            # Delete parent
            person.delete()

            logger.info(
                f"✅ Successfully deleted parent {person_name} + "
                f"{children_count} children + {file_count} files"
            )

            return 200, {
                'success': True,
                'message': f'Deleted {person_name}, {children_count} children, and {file_count} files'
            }

        else:
            # ✅ CHILD DELETION

            # Get files for this child
            child_files = person.uploaded_files.all()
            file_count = child_files.count()

            # Delete files from S3 and database
            for file_obj in child_files:
                if file_obj.file:
                    file_obj.file.delete(save=False)  # Delete from S3
                    logger.info(f"  Deleted file from S3: {file_obj.file.name}")
                file_obj.delete()  # Delete from database

            # Delete child
            person.delete()

            logger.info(f"✅ Successfully deleted child {person_name} + {file_count} files")

            return 200, {
                'success': True,
                'message': f'Deleted {person_name} and {file_count} files'
            }

    except Person.DoesNotExist:
        logger.warning(f"Person {person_id} not found")
        return 404, {
            'success': False,
            'message': 'Person not found'
        }
    except Exception as e:
        logger.error(f"Failed to delete person {person_id}: {e}", exc_info=True)
        return 500, {
            'success': False,
            'message': 'Failed to delete person'
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
                'id': locus.pk,
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
