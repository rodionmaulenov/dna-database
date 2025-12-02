import logging

from django.db import transaction
from django.shortcuts import get_object_or_404
from ninja import Router, Query
from dna.models import Person, DNALocus
from dna.schemas import UpdatePersonRequest
from dna.services import get_storage_service
from dna.utils.file_helpers import delete_uploaded_files_with_storage

logger = logging.getLogger(__name__)
person_router = Router()


@person_router.patch(
    'update/{person_id}/',
    response={200: dict, 400: dict, 404: dict, 422: dict, 500: dict}
)
def update_person(request, person_id: int, data: UpdatePersonRequest):
    """Update person name, role, and loci"""
    logger.info(f"📝 Updating person {person_id}")
    logger.info(f"   Name: {data.name}")
    logger.info(f"   Role: {data.role}")
    logger.info(f"   Loci: {len(data.loci) if data.loci else 0}")

    try:
        person = get_object_or_404(Person, id=person_id)
        updated_fields = []

        # Update name
        if data.name is not None:
            person.name = data.name
            updated_fields.append('name')

        # Update role
        if data.role is not None:
            if data.role not in ['father', 'mother', 'child']:
                return 422, {'success': False, 'errors': [f"Invalid role: {data.role}"]}
            person.role = data.role
            updated_fields.append('role')

        # ✅ Update/Create loci by locus_name
        if data.loci is not None:
            for locus_data in data.loci:
                # Skip empty loci
                if not locus_data.allele_1 and not locus_data.allele_2:
                    # ✅ Optionally delete existing empty locus
                    DNALocus.objects.filter(
                        person=person,
                        locus_name=locus_data.locus_name
                    ).delete()
                    continue

                # ✅ Update or create by locus_name
                DNALocus.objects.update_or_create(
                    person=person,
                    locus_name=locus_data.locus_name,
                    defaults={
                        'allele_1': locus_data.allele_1,
                        'allele_2': locus_data.allele_2
                    }
                )

                if 'loci' not in updated_fields:
                    updated_fields.append('loci')

            # Update loci count
            person.loci_count = person.loci.count()

        if not updated_fields:
            return 400, {'success': False, 'errors': ['No fields to update']}

        person.save()

        return 200, {'success': True}

    except Exception as e:
        logger.error(f"Update person error: {e}", exc_info=True)
        return 500, {'success': False, 'errors': ['Failed to update person']}


@person_router.delete('delete-multiple/', response={200: dict, 400: dict, 500: dict})
@transaction.atomic
def delete_persons(request, person_ids_param: str = Query(..., alias='person_ids')):
    """
    Delete one or multiple PARENTS and all related data (children, files)
    Only parent (father/mother) IDs allowed.
    """

    try:
        if not person_ids_param:
            return 400, {'error': 'No person_ids provided'}

        try:
            person_ids = [int(id.strip()) for id in person_ids_param.split(',') if id.strip()]
        except ValueError:
            return 400, {'error': 'Invalid person_ids format'}

        if not person_ids:
            return 400, {'error': 'No valid person_ids provided'}

        # ========== CHECK FOR CHILDREN (REJECT) ==========
        has_children = Person.objects.filter(
            id__in=person_ids,
            role='child'
        ).exists()

        if has_children:
            return 400, {'error': 'Child deletion not allowed. Select only parents.'}

        # ========== CHECK ALL EXIST ==========
        existing_persons = Person.objects.filter(id__in=person_ids)
        if existing_persons.count() != len(person_ids):
            return 400, {'error': 'One or more persons not found'}

        # ========== DELETE ==========
        storage_service = get_storage_service()

        for person in existing_persons:
            # Get parent's files
            parent_files = person.uploaded_files.all()

            # Find and delete children
            children = Person.objects.filter(
                uploaded_files__in=parent_files,
                role='child'
            ).distinct()

            for child in children:
                child_files = child.uploaded_files.all()
                delete_uploaded_files_with_storage(child_files, storage_service)
                child.delete()

            # Delete parent's files
            delete_uploaded_files_with_storage(parent_files, storage_service)

            # Delete parent
            person.delete()

        return 200, {'success': True}

    except Exception as e:
        logger.error(f"Failed to delete persons: {e}", exc_info=True)
        return 500, {'error': 'Failed to delete persons'}