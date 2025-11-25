import logging

from django.shortcuts import get_object_or_404

from ninja import Router

from dna.models import UploadedFile, PersonFile
from dna.services.storage_service import get_storage_service

logger = logging.getLogger(__name__)
file_router = Router()


@file_router.delete('/delete/{file_id}/', response={200: dict, 404: dict})
def delete_file(request, file_id: int):
    """Smart file deletion with storage cleanup"""

    file = get_object_or_404(UploadedFile, id=file_id)
    storage = get_storage_service()

    linked_persons = file.persons.all()

    deleted_person_ids = []
    unlinked_person_ids = []

    for person in linked_persons:
        other_files_count = person.uploaded_files.exclude(id=file_id).count()

        if other_files_count == 0:
            deleted_person_ids.append(person.id)
            person.delete()
        else:
            unlinked_person_ids.append(person.id)

    PersonFile.objects.filter(
        uploaded_file=file,
        person_id__in=unlinked_person_ids
    ).delete()

    # ✅ Delete from S3 or local using your service
    storage.delete_file(file.file.name)

    file.delete()

    logger.info(f"Deleted file {file_id}: removed {deleted_person_ids}, unlinked {unlinked_person_ids}")

    return 200, {
        'success': True,
        'deleted_person_ids': deleted_person_ids,
        'unlinked_person_ids': unlinked_person_ids
    }