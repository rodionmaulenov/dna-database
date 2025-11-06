from ninja import NinjaAPI

from dna.views import upload_router

api = NinjaAPI()

api.add_router("/upload/", upload_router)
