from fastapi import APIRouter

from app.api.schemas import HealthResponse
from app.core.settings import settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        llm_provider=settings.llm_provider,
        embeddings_provider=settings.embeddings_provider,
        neo4j_uri=settings.neo4j_uri,
    )
