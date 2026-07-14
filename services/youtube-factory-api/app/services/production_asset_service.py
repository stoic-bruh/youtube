"""ProductionAssetService — aggregates Subtitle + Thumbnail + Chapter outputs
for a single render into one bundle, with an export manifest of file paths."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.models.production_asset import ProductionAsset
from app.repositories.chapter_repository import ChapterRepository
from app.repositories.production_asset_repository import ProductionAssetRepository
from app.repositories.render_repository import RenderRepository
from app.repositories.subtitle_repository import SubtitleRepository
from app.repositories.thumbnail_repository import ThumbnailRepository

logger = logging.getLogger(__name__)


class ProductionAssetService:
    def __init__(
        self,
        repo: ProductionAssetRepository,
        subtitle_repo: SubtitleRepository | None = None,
        thumbnail_repo: ThumbnailRepository | None = None,
        chapter_repo: ChapterRepository | None = None,
        render_repo: RenderRepository | None = None,
    ) -> None:
        self._repo = repo
        self._subtitle_repo = subtitle_repo or SubtitleRepository(repo._db)
        self._thumbnail_repo = thumbnail_repo or ThumbnailRepository(repo._db)
        self._chapter_repo = chapter_repo or ChapterRepository(repo._db)
        self._render_repo = render_repo or RenderRepository(repo._db)

    async def get_or_assemble(self, render_id: str) -> tuple[ProductionAsset, dict] | None:
        render = await self._render_repo.get(render_id)
        if not render:
            return None

        bundle = await self._repo.get_by_render_id(render_id)
        if not bundle:
            bundle = await self._repo.create(render_id=render_id, status="pending", export_manifest={})

        subtitle = await self._subtitle_repo.get_by_render_id(render_id)
        thumbnail = await self._thumbnail_repo.get_by_render_id(render_id)
        chapter = await self._chapter_repo.get_by_render_id(render_id)

        completed_subtitle = subtitle if subtitle and subtitle.status == "completed" else None
        completed_thumbnail = thumbnail if thumbnail and thumbnail.status == "completed" else None
        completed_chapter = chapter if chapter and chapter.status == "completed" else None

        present = [x for x in (completed_subtitle, completed_thumbnail, completed_chapter) if x]
        if len(present) == 3:
            status = "completed"
        elif present:
            status = "partial"
        else:
            status = "pending"

        export_manifest = {
            "srtPath": completed_subtitle.srt_path if completed_subtitle else None,
            "vttPath": completed_subtitle.vtt_path if completed_subtitle else None,
            "assPath": completed_subtitle.ass_path if completed_subtitle else None,
            "thumbnailPaths": [
                c["path"] for c in (completed_thumbnail.candidates or [])
                if c.get("candidate_id") in (completed_thumbnail.selected_candidate_ids or [])
            ] if completed_thumbnail else [],
            "youtubeChapters": completed_chapter.youtube_export if completed_chapter else None,
        }

        updated = await self._repo.update(
            bundle.id,
            status=status,
            subtitle_id=subtitle.id if subtitle else None,
            thumbnail_id=thumbnail.id if thumbnail else None,
            chapter_id=chapter.id if chapter else None,
            export_manifest=export_manifest,
            updated_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc) if status == "completed" else bundle.completed_at,
        )

        joined = {
            "subtitle": _model_to_dict(subtitle) if subtitle else None,
            "thumbnail": _model_to_dict(thumbnail) if thumbnail else None,
            "chapter": _model_to_dict(chapter) if chapter else None,
        }
        return updated, joined

    async def list_bundles(self, limit: int = 50, offset: int = 0) -> tuple[list[ProductionAsset], int]:
        return await self._repo.list(limit=limit, offset=offset)


def _model_to_dict(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
