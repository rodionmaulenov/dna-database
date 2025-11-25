from ninja import NinjaAPI

from dna.views.file_views import file_router
from dna.views.list_views import list_router
from dna.views.person_views import person_router
from dna.views.upload_views import upload_router

api = NinjaAPI()

api.add_router("/dna/", list_router)
api.add_router("/dna/upload/", upload_router)
api.add_router("/dna/person/", person_router)
api.add_router("/dna/file/", file_router)