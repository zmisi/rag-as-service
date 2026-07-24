"""v1 routers."""

from fastapi import APIRouter

from rag_api.api.v1.conversations import router as conversations_router
from rag_api.api.v1.documents import router as documents_router
from rag_api.api.v1.faq_suggestions import router as faq_suggestions_router

api_router = APIRouter()
api_router.include_router(conversations_router)
api_router.include_router(documents_router)
api_router.include_router(faq_suggestions_router)
