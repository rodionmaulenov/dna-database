import logging

from ninja import Router

from dna.models import Person, UploadedFile
from dna.schemas import DNADataListResponse
from dna.utils.response_builders import build_person_response, build_parent_with_children_response

logger = logging.getLogger(__name__)

list_router = Router()


@list_router.get('list/', response=DNADataListResponse)
def get_all_dna_data(request, page: int = 1, page_size: int = 20):
    """List all DNA records grouped by parent with pagination"""

    logger.info(f"📋 Loading all uploads - page {page}, size {page_size}")

    # Get all parents with prefetch
    parents = Person.objects.filter(
        role__in=['father', 'mother']
    ).prefetch_related(
        'loci',
        'uploaded_files__persons',  # ✅ Prefetch children through files
    ).order_by('-id')

    total_count = parents.count()

    # Paginate parents
    start = (page - 1) * page_size
    end = start + page_size
    parents_page = parents[start:end]

    result = []
    for parent in parents_page:
        response = build_parent_with_children_response(parent)  # ✅ Use new function
        if response:
            result.append(response)

    logger.info(f"📊 Returning {len(result)} parent(s) from {total_count} total")

    return DNADataListResponse(
        data=result,
        total=total_count,
        page=page,
        page_size=page_size
    )


@list_router.get('filter/', response=DNADataListResponse)
def filter_by_persons(request, person_ids: str):
    """
    Filter DNA records by specific person IDs (optimized)
    Returns requested persons AND their direct relationships
    """
    try:
        person_id_list = [int(id.strip()) for id in person_ids.split(',')]
        logger.info(f"🔍 Filtering by person_ids: {person_id_list}")

        # ✅ OPTIMIZATION 1: Single bulk query with all prefetches
        persons = Person.objects.filter(
            id__in=person_id_list
        ).prefetch_related(
            'uploaded_files__persons__loci',
            'uploaded_files__persons__uploaded_files'
        ).select_related()  # Use if Person has FK relationships

        if not persons.exists():
            logger.warning("❌ No persons found")
            return DNADataListResponse(data=[], total=0, page=1, page_size=0)

        # ✅ OPTIMIZATION 2: Collect uploads in single pass (O(n))
        uploads_map = {}  # {upload_id: (upload_obj, [requested_person_ids])}

        for person in persons:
            # Use already-prefetched data (no additional queries)
            person_files = person.uploaded_files.all()
            if person_files:
                upload = person_files[0]  # First upload (already sorted by prefetch)

                if upload.pk not in uploads_map:
                    uploads_map[upload.pk] = (upload, [])

                uploads_map[upload.pk][1].append(person.id)

        logger.info(f"📦 Found {len(uploads_map)} unique upload(s)")

        # ✅ OPTIMIZATION 3: Process uploads (already prefetched, no queries)
        result = []

        for upload_id, (upload, requested_ids) in uploads_map.items():
            # All persons already prefetched
            all_persons_in_file = upload.persons.all()

            # Build response
            response = build_person_response(upload, all_persons_in_file)

            if not response:
                continue

            logger.info(f"  📋 Upload {upload_id}: requested persons {requested_ids}")

            # ✅ FILTER LOGIC: Keep requested persons + relationships

            # Case 1: Requested person is parent → Keep parent + all children
            if response.parent and response.parent.id in requested_ids:
                logger.info(f"✅ Parent requested → keeping parent + all children")
                result.append(response)
                continue

            # Case 2: Requested persons are children → Keep children + parent
            if response.children:
                # Filter to only requested children
                filtered_children = [
                    c for c in response.children
                    if c.id in requested_ids
                ]

                if filtered_children:
                    logger.info(f"✅ {len(filtered_children)} child(ren) requested → keeping + parent")
                    response.children = filtered_children
                    # Keep parent (don't filter it out)
                    result.append(response)
                    continue
                else:
                    response.children = None

            # Case 3: Single child
            if response.child and response.child.id in requested_ids:
                logger.info(f"✅ Single child requested → keeping + parent")
                result.append(response)
                continue

            # Case 4: No match (shouldn't happen)
            logger.warning(f"⚠️ No matching persons in response")

        logger.info(f"📊 Returning {len(result)} filtered record(s)")

        return DNADataListResponse(
            data=result,
            total=len(result),
            page=1,
            page_size=len(result)
        )

    except Exception as e:
        logger.error(f"❌ filter_by_persons error: {e}", exc_info=True)
        return DNADataListResponse(data=[], total=0, page=1, page_size=0)