"""v1 routers."""

from fastapi import APIRouter

from rag_api.api.v1.conversations import router as conversations_router

api_router = APIRouter()
api_router.include_router(conversations_router)
