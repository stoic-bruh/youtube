"""Media Timeline Engine API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.timeline import TimelineResult
from app.schemas.timeline import (
    TimelineList,
    TimelineRequest,
    TimelineResultSchema,
    TimelineStatus,
    TimelineRenderPlan,
    TimelineMetadata,
    TimelineTrack,
    TimelineScene,
    TimelineMarker,
    TrackKind,
    TransitionType,
    MarkerType,
)
from app.services.timeline_service import TimelineService

router = APIRouter(prefix="/timelines", tags=["timelines"])


def _to_api(t: TimelineResult) -> TimelineResultSchema:
    """Coerce ORM model → API schema."""
    tracks = []
    for raw_track in (t.tracks or []):
        if isinstance(raw_track, dict):
            clips_raw = raw_track.get("clips", [])
            from app.schemas.timeline import TimelineClip
            clips = [TimelineClip(**c) for c in clips_raw if isinstance(c, dict)]
            tracks.append(TimelineTrack(
                track_id=raw_track.get("track_id", ""),
                kind=TrackKind(raw_track.get("kind", "video")),
                order=raw_track.get("order", 0),
                label=raw_track.get("label", ""),
                clips=clips,
                is_muted=raw_track.get("is_muted", False),
                is_locked=raw_track.get("is_locked", False),
            ))

    scenes = []
    for raw_scene in (t.scenes or []):
        if isinstance(raw_scene, dict):
            scenes.append(TimelineScene(
                scene_id=raw_scene.get("scene_id", ""),
                scene_number=raw_scene.get("scene_number", 1),
                title=raw_scene.get("title", ""),
                start_ms=raw_scene.get("start_ms", 0),
                end_ms=raw_scene.get("end_ms", 0),
                duration_ms=raw_scene.get("duration_ms", 0),
                has_video_asset=raw_scene.get("has_video_asset", False),
                has_audio_placeholder=raw_scene.get("has_audio_placeholder", False),
                asset_ids=raw_scene.get("asset_ids", []),
                transition_in=TransitionType(raw_scene.get("transition_in", "cut")),
                transition_out=TransitionType(raw_scene.get("transition_out", "cut")),
                narration=raw_scene.get("narration"),
                visual_description=raw_scene.get("visual_description"),
            ))

    markers = []
    for raw_marker in (t.markers or []):
        if isinstance(raw_marker, dict):
            markers.append(TimelineMarker(
                marker_id=raw_marker.get("marker_id", ""),
                label=raw_marker.get("label", ""),
                timestamp_ms=raw_marker.get("timestamp_ms", 0),
                marker_type=MarkerType(raw_marker.get("marker_type", "chapter")),
                color=raw_marker.get("color"),
            ))

    render_plan = None
    if t.render_plan and isinstance(t.render_plan, dict):
        from app.schemas.timeline import RenderFormat
        render_plan = TimelineRenderPlan(
            width=t.render_plan.get("width", 1920),
            height=t.render_plan.get("height", 1080),
            fps=t.render_plan.get("fps", 30),
            format=RenderFormat(t.render_plan.get("format", "mp4")),
            codec=t.render_plan.get("codec", "h264"),
            audio_codec=t.render_plan.get("audio_codec", "aac"),
            bitrate_kbps=t.render_plan.get("bitrate_kbps", 8000),
            estimated_render_time_ms=t.render_plan.get("estimated_render_time_ms"),
        )

    metadata = None
    if t.timeline_metadata and isinstance(t.timeline_metadata, dict):
        metadata = TimelineMetadata(**t.timeline_metadata)

    return TimelineResultSchema(
        id=t.id,
        storyboard_id=t.storyboard_id,
        script_id=t.script_id,
        topic=t.topic,
        title=t.title,
        status=TimelineStatus(t.status),
        total_duration_ms=t.total_duration_ms,
        total_scenes=t.total_scenes,
        tracks=tracks,
        scenes=scenes,
        markers=markers,
        render_plan=render_plan,
        metadata=metadata,
        validation_errors=t.validation_errors or [],
        logs=t.logs or [],
        error_message=t.error_message,
        created_at=t.created_at,
        updated_at=t.updated_at,
        completed_at=t.completed_at,
    )


@router.get("", response_model=TimelineList)
async def list_timelines(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    storyboard_id: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> TimelineList:
    """Return a paginated list of timeline results."""
    service = TimelineService(db)
    timelines, total = await service.list_timelines(
        limit=limit,
        offset=offset,
        storyboard_id=storyboard_id,
        status=status,
    )
    return TimelineList(items=[_to_api(t) for t in timelines], total=total)


@router.post("", response_model=TimelineResultSchema, status_code=202)
async def build_timeline(
    request: TimelineRequest,
    db: AsyncSession = Depends(get_db),
) -> TimelineResultSchema:
    """
    Build a media timeline from a storyboard.
    Merges storyboard scenes + acquired assets + placeholder voice timings.
    Returns 202 with the completed timeline (built inline; Celery for async).
    """
    service = TimelineService(db)
    timeline = await service.build_timeline(request)
    return _to_api(timeline)


@router.get("/{timeline_id}", response_model=TimelineResultSchema)
async def get_timeline(
    timeline_id: str,
    db: AsyncSession = Depends(get_db),
) -> TimelineResultSchema:
    """Fetch a single timeline by ID."""
    service = TimelineService(db)
    timeline = await service.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail=f"Timeline {timeline_id!r} not found")
    return _to_api(timeline)


@router.delete("/{timeline_id}", status_code=204)
async def delete_timeline(
    timeline_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a timeline record."""
    service = TimelineService(db)
    deleted = await service.delete_timeline(timeline_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Timeline {timeline_id!r} not found")
