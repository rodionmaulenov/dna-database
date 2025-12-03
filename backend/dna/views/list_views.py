import logging

from ninja import Router

from django.db.models import Max, Prefetch

from dna.models import Person, UploadedFile
from dna.schemas import DNADataListResponse
from dna.utils.response_builders import build_parent_with_children_response, build_orphan_child_response

logger = logging.getLogger(__name__)

list_router = Router()


@list_router.get('list/', response=DNADataListResponse)
def get_all_dna_data(request, page: int = 1, page_size: int = 20):
    logger.info(f"📋 Loading page {page}, size {page_size}")

    start: int = (page - 1) * page_size
    end: int = start + page_size

    # Single query for parents count
    parents_count: int = Person.objects.filter(role__in=['father', 'mother']).count()

    # Orphan children using NOT EXISTS (faster than exclude__in)
    orphan_children_qs = Person.objects.filter(role='child').exclude(
        uploaded_files__persons__role__in=['father', 'mother']
    ).distinct()

    # Prefetch setup
    children_prefetch = Prefetch(
        'persons',
        queryset=Person.objects.filter(role='child').prefetch_related('loci', 'uploaded_files'),
        to_attr='file_children'
    )

    result = []

    # Case 1: Page is within parents range
    if start < parents_count:
        parents = Person.objects.filter(
            role__in=['father', 'mother']
        ).annotate(
            latest_upload=Max('uploaded_files__uploaded_at')
        ).prefetch_related(
            'loci',
            Prefetch('uploaded_files', queryset=UploadedFile.objects.prefetch_related(children_prefetch))
        ).order_by('-latest_upload')[start:end]

        for parent in parents:
            response = build_parent_with_children_response(parent)
            if response:
                result.append(response)

    # Case 2: Need orphans to fill page
    remaining_slots: int = page_size - len(result)
    if remaining_slots > 0:
        orphan_start: int = max(0, start - parents_count)
        orphan_end: int = orphan_start + remaining_slots

        orphans = orphan_children_qs.annotate(
            latest_upload=Max('uploaded_files__uploaded_at')
        ).prefetch_related('loci', 'uploaded_files').order_by('-latest_upload')[orphan_start:orphan_end]

        for orphan in orphans:
            response = build_orphan_child_response(orphan)
            if response:
                result.append(response)

    logger.info(f"📊 Returning {len(result)} records from {parents_count} total")

    return DNADataListResponse(
        data=result,
        total=parents_count,  # ✅ Only parents count
        page=page,
        page_size=page_size
    )
