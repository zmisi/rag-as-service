"""v1 routers."""

from fastapi import APIRouter

# conversations first: loads agent.service before dependencies package (avoids
# clients.llm ↔ agent circular import).
from rag_api.api.v1.conversations import router as conversations_router
from rag_api.api.v1.documents import router as documents_router
from rag_api.api.v1.folders import router as folders_router
from rag_api.api.v1.faq_suggestions import router as faq_suggestions_router
from rag_api.api.v1.members import router as members_router
from rag_api.api.v1.widget import router as widget_router
from rag_api.api.v1.widget_admin import router as widget_admin_router
from rag_api.api.v1.api_keys_admin import router as api_keys_admin_router
from rag_api.api.v1.debug_admin import router as debug_admin_router

api_router = APIRouter()
api_router.include_router(conversations_router)
api_router.include_router(documents_router)
api_router.include_router(folders_router)
api_router.include_router(faq_suggestions_router)
api_router.include_router(members_router)
api_router.include_router(widget_router)
api_router.include_router(widget_admin_router)
api_router.include_router(api_keys_admin_router)
api_router.include_router(debug_admin_router)
