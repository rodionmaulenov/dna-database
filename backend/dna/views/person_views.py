import logging
from django.shortcuts import get_object_or_404
from ninja import Router
from dna.models import Person, DNALocus
from dna.schemas import UpdatePersonRequest, UpdatePersonResponse, UpdatePersonData, LocusData
from dna.utils.file_helpers import delete_uploaded_files
from dna.utils.response_helpers import error_response, success_response

logger = logging.getLogger(__name__)
person_router = Router()




@person_router.patch('update/{person_id}/', response={200: UpdatePersonResponse, 400: dict, 404: dict, 422: dict, 500: dict})
def update_person(request, person_id: int, data: UpdatePersonRequest):
    """Update person name, role, and loci"""
    # ✅ ADD THIS AT THE TOP
    logger.info(f"📝 Updating person {person_id}")
    logger.info(f"   Name: {data.name}")
    logger.info(f"   Role: {data.role}")
    logger.info(f"   Loci updates: {len(data.loci) if data.loci else 0}")
    logger.info(f"   New loci: {len(data.new_loci) if data.new_loci else 0}")
    logger.info(f"   Deleted loci IDs: {data.deleted_loci_ids}")
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

        # Update existing loci
        if data.loci is not None:
            for locus_data in data.loci:
                try:
                    locus = DNALocus.objects.get(id=locus_data.id, person=person)
                    locus.allele_1 = locus_data.allele_1
                    locus.allele_2 = locus_data.allele_2
                    locus.save()
                    if 'loci' not in updated_fields:
                        updated_fields.append('loci')
                except DNALocus.DoesNotExist:
                    return 404, {'success': False, 'errors': [f'Locus {locus_data.id} not found']}

        # Create new loci
        if data.new_loci is not None and len(data.new_loci) > 0:
            for new_locus in data.new_loci:
                DNALocus.objects.create(
                    person=person,
                    locus_name=new_locus.locus_name,
                    allele_1=new_locus.allele_1,
                    allele_2=new_locus.allele_2
                )
            updated_fields.append('new_loci')
            person.loci_count = person.loci.count()

        # Delete loci
        if data.deleted_loci_ids is not None and len(data.deleted_loci_ids) > 0:
            deleted_count = DNALocus.objects.filter(id__in=data.deleted_loci_ids, person=person).delete()[0]
            if deleted_count > 0:
                updated_fields.append('deleted_loci')
                person.loci_count = person.loci.count()

        if not updated_fields:
            return 400, {'success': False, 'errors': ['No fields to update']}

        person.save()

        # Build response with updated loci
        loci_data = [
            LocusData(
                id=locus.id,
                locus_name=locus.locus_name,
                allele_1=locus.allele_1 or '',
                allele_2=locus.allele_2 or ''
            )
            for locus in person.loci.all().order_by('id')
        ]

        return 200, UpdatePersonResponse(
            success=True,
            message=f'Updated {", ".join(set(updated_fields))}',
            data=UpdatePersonData(
                id=person.pk,
                name=person.name,
                role=person.role,
                loci_count=person.loci.count(),
                loci=loci_data
            )
        )

    except Exception as e:
        logger.error(f"Update person error: {e}", exc_info=True)
        return 500, {'success': False, 'errors': ['Failed to update person']}


@person_router.delete('delete/{person_id}/', response={200: dict, 404: dict, 500: dict})
def delete_person(request, person_id: int):
    """Delete a person and all related data"""
    try:
        person = get_object_or_404(Person, id=person_id)
        person_name = person.name
        person_role = person.role

        if person_role in ['father', 'mother']:
            # Parent deletion
            parent_files = person.uploaded_files.all()
            children = Person.objects.filter(
                uploaded_files__in=parent_files,
                role='child'
            ).distinct()

            children_count = children.count()

            # Delete children
            for child in children:
                child.delete()

            # Delete files
            file_count = delete_uploaded_files(parent_files)

            # Delete parent
            person.delete()

            return success_response(
                200,
                f'Deleted {person_name}, {children_count} children, and {file_count} files',
                log_message=f"Deleted parent {person_name} + {children_count} children + {file_count} files"
            )
        else:
            # Child deletion
            child_files = person.uploaded_files.all()
            file_count = delete_uploaded_files(child_files)
            person.delete()

            return success_response(
                200,
                f'Deleted {person_name} and {file_count} files',
                log_message=f"Deleted child {person_name} + {file_count} files"
            )

    except Person.DoesNotExist:
        return error_response(404, 'Person not found', f"Person {person_id} not found")
    except Exception as e:
        return error_response(
            500,
            'Failed to delete person',
            log_message=f"Failed to delete person {person_id}: {e}",
            exc_info=True
        )