"""Builds a fully-resolved RenderPlan from a TimelineResult + VoiceResult +
AssetCollection (a list of AssetResult rows). Pure/no I/O beyond the objects
passed in, so it's usable from both the async service layer and tests.

Mirrors the equivalent builder in artifacts/api-server/src/routes/render.ts —
keep the two in sync when the RenderPlan shape changes.
"""
from __future__ import annotations

from app.schemas.render import (
    RenderAspectRatio,
    RenderClip,
    RenderCropMode,
    RenderPlan,
    RenderRequest,
    RenderResolution,
    RenderScene,
    RenderTransition,
    RenderTransitionType,
    RESOLUTION_DIMENSIONS,
)

_PAN_CYCLE = ["right", "left", "up", "down"]


def build_render_plan(
    request: RenderRequest,
    *,
    timeline,
    voice=None,
    assets: list | None = None,
) -> RenderPlan:
    """Assemble a RenderPlan document from the source Timeline/Voice/Asset rows.

    Args:
        request: The RenderRequest configuration (resolution/fps/aspect/etc).
        timeline: TimelineResult ORM row (has `.scenes`, `.tracks`, `.title`).
        voice: Optional VoiceResult ORM row (has `.sections`) providing
            per-section narration text/timing for audio sync.
        assets: Optional list of AssetResult ORM rows to map onto scenes by
            `scene_id`.
    """
    assets = assets or []
    width, height = RESOLUTION_DIMENSIONS[request.resolution.value]
    if request.aspect_ratio == RenderAspectRatio.VERTICAL:
        width, height = min(width, height), max(width, height)
    elif request.aspect_ratio == RenderAspectRatio.SQUARE:
        side = min(width, height)
        width = height = side

    assets_by_scene: dict[str, list] = {}
    for asset in assets:
        scene_id = getattr(asset, "scene_id", None)
        if scene_id:
            assets_by_scene.setdefault(scene_id, []).append(asset)

    voice_sections = list(getattr(voice, "sections", None) or []) if voice else []

    scenes: list[RenderScene] = []
    timeline_scenes = list(getattr(timeline, "scenes", None) or [])
    for i, scene_doc in enumerate(sorted(timeline_scenes, key=lambda s: s.get("order", s.get("sceneIndex", 0)))):
        scene_id = scene_doc.get("id") or scene_doc.get("sceneId") or f"scene-{i}"
        start_ms = int(scene_doc.get("startMs", scene_doc.get("start_ms", 0)))
        end_ms = int(scene_doc.get("endMs", scene_doc.get("end_ms", start_ms + 4000)))
        duration_ms = max(end_ms - start_ms, 500)
        narration_text = scene_doc.get("narration", "") or (
            voice_sections[i]["text"] if i < len(voice_sections) and isinstance(voice_sections[i], dict) else ""
        )

        scene_assets = assets_by_scene.get(scene_id, [])
        clips: list[RenderClip] = []
        if scene_assets:
            asset = scene_assets[0]
            clips.append(
                RenderClip(
                    clip_id=f"{scene_id}-clip-0",
                    scene_index=i,
                    asset_id=getattr(asset, "id", None),
                    kind=getattr(asset, "asset_kind", "image") or "image",
                    source_path=getattr(asset, "local_cache_path", None),
                    start_ms=start_ms,
                    end_ms=end_ms,
                    duration_ms=duration_ms,
                    ken_burns=True,
                    pan_direction=_PAN_CYCLE[i % len(_PAN_CYCLE)],
                )
            )
        else:
            clips.append(
                RenderClip(
                    clip_id=f"{scene_id}-clip-placeholder",
                    scene_index=i,
                    kind="placeholder",
                    source_path=None,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    duration_ms=duration_ms,
                    ken_burns=True,
                    pan_direction=_PAN_CYCLE[i % len(_PAN_CYCLE)],
                )
            )

        scenes.append(
            RenderScene(
                scene_index=i,
                title=scene_doc.get("title", f"Scene {i + 1}"),
                narration=narration_text,
                start_ms=start_ms,
                end_ms=end_ms,
                duration_ms=duration_ms,
                clips=clips,
                transition_out=RenderTransition(
                    type=RenderTransitionType.CUT if i == len(timeline_scenes) - 1 else RenderTransitionType.CROSSFADE,
                    duration_ms=500,
                ),
            )
        )

    audio_tracks = []
    if voice_sections:
        cursor_ms = 0
        for section in voice_sections:
            if not isinstance(section, dict):
                continue
            s_start = int(section.get("start_ms", section.get("startMs", cursor_ms)))
            s_end = int(section.get("end_ms", section.get("endMs", s_start + section.get("duration_ms", section.get("durationMs", 3000)))))
            audio_tracks.append(
                {
                    "kind": "narration",
                    "source_path": section.get("local_path", section.get("localPath")),
                    "start_ms": s_start,
                    "end_ms": s_end,
                    "volume": 1.0,
                }
            )
            cursor_ms = s_end

    from app.schemas.render import RenderAudioTrack, RenderVideoTrack

    total_duration_ms = max((s.end_ms for s in scenes), default=0)

    return RenderPlan(
        timeline_id=timeline.id,
        voice_id=getattr(voice, "id", None) if voice else None,
        title=getattr(timeline, "title", None) or getattr(timeline, "topic", "") or "Untitled Render",
        resolution=request.resolution,
        width=width,
        height=height,
        fps=request.fps,
        aspect_ratio=request.aspect_ratio,
        crop_mode=request.crop_mode,
        hardware_acceleration=request.hardware_acceleration,
        add_background_music=request.add_background_music,
        background_music_path=None,
        music_volume=request.music_volume,
        scenes=scenes,
        video_tracks=[RenderVideoTrack(kind="main", scene_indices=[s.scene_index for s in scenes])],
        audio_tracks=[RenderAudioTrack(**t) for t in audio_tracks],
        total_duration_ms=total_duration_ms,
    )
