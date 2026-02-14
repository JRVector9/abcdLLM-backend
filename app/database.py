from pocketbase import PocketBase

from app.config import settings

pb = PocketBase(settings.POCKETBASE_URL)
