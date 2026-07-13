"""Research API endpoints — POST /research, GET /research/{id}, DELETE /research/{id}."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.research_repository import ResearchRepository
from app.schemas.research import ResearchRequest, ResearchResultSchema, ResearchStatus
from app.services.research_service import ResearchService

router = APIRouter()


def _get_service(db: AsyncSession) -> ResearchService:
    repo = ResearchRepository(db)
    return ResearchService(repo)


def _to_api(result) -> dict:
    """Convert ORM model to API response dict."""
    return {
        "id": result.id,
        "topic": result.topic,
        "targetAudience": result.target_audience,
        "videoLengthMinutes": result.video_length_minutes,
        "language": result.language,
        "style": result.style,
        "tone": result.tone,
        "status": result.status,
        "jobId": result.job_id,
        "summary": result.summary,
        "confidenceScore": result.confidence_score,
        "estimatedDifficulty": result.estimated_difficulty,
        "sections": _coerce_sections(result.sections),
        "references": _coerce_references(result.references),
        "keywords": _coerce_keywords(result.keywords),
        "providers": result.providers or [],
        "usedProviders": result.used_providers or [],
        "logs": result.logs or [],
        "errorMessage": result.error_message,
        "createdAt": result.created_at.isoformat(),
        "updatedAt": result.updated_at.isoformat(),
        "completedAt": result.completed_at.isoformat() if result.completed_at else None,
    }


def _coerce_sections(raw: list | None) -> list[dict]:
    if not raw:
        return []
    out = []
    for s in raw:
        if isinstance(s, dict):
            # Normalize field names from snake_case Pydantic model dump
            out.append({
                "sectionType": s.get("section_type") or s.get("sectionType", ""),
                "title": s.get("title", ""),
                "content": s.get("content", ""),
                "confidence": s.get("confidence", 0.5),
                "items": s.get("items", []),
                "sourceIds": s.get("source_ids") or s.get("sourceIds", []),
            })
    return out


def _coerce_references(raw: list | None) -> list[dict]:
    if not raw:
        return []
    out = []
    for r in raw:
        if isinstance(r, dict):
            out.append({
                "id": r.get("id", ""),
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "sourceType": r.get("source_type") or r.get("sourceType", "web"),
                "author": r.get("author"),
                "publishedAt": r.get("published_at") or r.get("publishedAt"),
                "snippet": r.get("snippet"),
                "credibilityScore": r.get("credibility_score") or r.get("credibilityScore", 0.5),
                "citationFormat": r.get("citation_format") or r.get("citationFormat", ""),
                "provider": r.get("provider", ""),
            })
    return out


def _coerce_keywords(raw: list | None) -> list[dict]:
    if not raw:
        return []
    out = []
    for k in raw:
        if isinstance(k, dict):
            out.append({
                "term": k.get("term", ""),
                "relevance": k.get("relevance", 0.5),
                "searchVolume": k.get("search_volume") or k.get("searchVolume"),
                "difficulty": k.get("difficulty"),
                "semanticTags": k.get("semantic_tags") or k.get("semanticTags", []),
            })
    return out


@router.get("")
async def list_research(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    service = _get_service(db)
    rows, total = await service.list_research(limit=limit, offset=offset, status=status)
    return {"items": [_to_api(r) for r in rows], "total": total}


@router.post("", status_code=202)
async def start_research(
    body: ResearchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    service = _get_service(db)
    result = await service.start_research(body)
    return _to_api(result)


@router.get("/{id}")
async def get_research(
    id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    service = _get_service(db)
    result = await service.get_research(id)
    if not result:
        raise HTTPException(status_code=404, detail="Research not found")
    return _to_api(result)


@router.delete("/{id}", status_code=204, response_model=None)
async def delete_research(
    id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = _get_service(db)
    deleted = await service.delete_research(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Research not found")
