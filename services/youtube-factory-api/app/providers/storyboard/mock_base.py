"""Deterministic mock storyboard generator.

Uses a seeded PRNG so identical inputs always produce identical outputs.
All provider stubs delegate here until real AI providers are wired in.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any

from app.schemas.storyboard import (
    AnimationInstruction,
    AssetType,
    CameraMovement,
    LightingStyle,
    NarrationPacing,
    NarrationTiming,
    Scene,
    SceneAsset,
    ScenePrompt,
    SceneTimeline,
    ShotType,
    StoryboardProviderResult,
    StoryboardRequest,
    SubtitleTiming,
    TransitionType,
    VisualCue,
    VisualPacing,
    VisualType,
)


# ── Seeded random ─────────────────────────────────────────────────────────────

class _SeededRandom:
    def __init__(self, seed_str: str) -> None:
        digest = hashlib.md5(seed_str.encode()).hexdigest()
        self._seed = int(digest[:8], 16) or 1

    def _next(self) -> int:
        self._seed ^= self._seed << 13
        self._seed ^= self._seed >> 17
        self._seed ^= self._seed << 5
        return abs(self._seed)

    def float(self, lo: float = 0.0, hi: float = 1.0) -> float:
        return lo + (self._next() % 10_000) / 10_000 * (hi - lo)

    def int(self, lo: int, hi: int) -> int:
        return lo + self._next() % (hi - lo + 1)

    def choice(self, seq: list) -> Any:
        return seq[self._next() % len(seq)]

    def sample(self, seq: list, k: int) -> list:
        pool = list(seq)
        out: list = []
        for _ in range(min(k, len(pool))):
            i = self._next() % len(pool)
            out.append(pool.pop(i))
        return out

    def flt(self, lo: float, hi: float) -> float:
        return round(self.float(lo, hi), 3)


# ── Lookup tables ─────────────────────────────────────────────────────────────

_CAMERA_ANGLES = ["eye_level", "high_angle", "low_angle", "dutch_tilt", "overhead", "worm's_eye"]

_EMOTIONS = ["curious", "excited", "pensive", "dramatic", "hopeful", "determined",
             "surprised", "contemplative", "energetic", "calm", "intense", "inspiring"]

_MUSIC_MOODS = [
    "ambient electronic", "uplifting orchestral", "tense minimalist", "warm acoustic",
    "cinematic epic", "neutral documentary", "subtle tension", "bright and optimistic",
    "mysterious atmospheric", "energetic indie", "calm piano", "inspirational strings",
]

_SFX = [
    "subtle whoosh", "soft keyboard clicks", "ambient office noise", "gentle notification ping",
    "page turn", "digital beep", "subtle chime", "nature ambience", "clock ticking",
    "soft breath", "paper rustle", "footsteps", "water flow",
]

_PALETTES: dict[str, list[str]] = {
    "educational": [["#1a1a2e", "#16213e", "#0f3460", "#e94560"],
                    ["#2c3e50", "#3498db", "#ecf0f1", "#e74c3c"],
                    ["#0d1117", "#161b22", "#21262d", "#58a6ff"]],
    "documentary": [["#1c1c1e", "#2c2c2e", "#8e8e93", "#ffffff"],
                    ["#1a0a00", "#4a2000", "#d4782a", "#f5e6d3"],
                    ["#0f1e2e", "#1e3a52", "#4a8fa8", "#c8e6f0"]],
    "tutorial":    [["#0a192f", "#172a45", "#64ffda", "#ccd6f6"],
                    ["#1e1e2e", "#313244", "#89b4fa", "#cba6f7"],
                    ["#141414", "#282828", "#f8f8f2", "#50fa7b"]],
    "storytelling":[["#1a0533", "#3d1066", "#9b59b6", "#f1c40f"],
                    ["#0e1111", "#1c2321", "#4a4e69", "#f2e9e4"],
                    ["#1b1b2f", "#2b2d42", "#8d99ae", "#ef233c"]],
    "news":        [["#000000", "#1a1a1a", "#cc0000", "#ffffff"],
                    ["#0a0a0a", "#1d1d1d", "#0066cc", "#f0f0f0"]],
    "long_form":   [["#0d0d0d", "#1a1a1a", "#333333", "#e0e0e0"],
                    ["#1b1f23", "#2d333b", "#444c56", "#adbac7"]],
    "shorts":      [["#ff0050", "#00f593", "#0044ff", "#ffffff"],
                    ["#ff6b35", "#f7c948", "#26c485", "#1e1e1e"]],
}

_BROLL: dict[str, list[str]] = {
    "educational": [
        "Close-up of textbook pages turning", "Person writing equations on whiteboard",
        "Abstract data visualization animation", "Scientists collaborating in a lab",
        "Time-lapse of a city at night", "Microscope view of cells dividing",
    ],
    "documentary": [
        "Archival black-and-white footage", "Sweeping aerial landscape shot",
        "Interview subject in natural setting", "Historical photographs pan-and-scan",
        "Environmental wide shots with atmosphere", "Slow-motion crowd scene",
    ],
    "tutorial": [
        "Screen recording with cursor highlights", "Hands typing on keyboard close-up",
        "Split-screen before/after comparison", "Step-by-step hands demonstration",
        "Annotated diagram with animated arrows", "Progress bar filling up animation",
    ],
    "storytelling": [
        "Emotional reaction close-up", "Environment establishing shot",
        "Symbolic object in dramatic lighting", "Time-lapse of sun rising",
        "Slow motion water ripple", "Candlelight flickering in darkness",
    ],
    "news": [
        "Location establishing shot", "Interview soundbite clip",
        "Data chart animation", "Street-level environment shot",
    ],
    "long_form": [
        "Deep-focus environment shot", "Expert interview setup",
        "Abstract concept visualization", "Historical context imagery",
    ],
    "shorts": [
        "Fast-cut reaction shot", "Dynamic text animation", "Trending visual effect",
    ],
}

_STOCK_FOOTAGE: dict[str, list[str]] = {
    "educational": ["Person studying with books and coffee", "Classroom lecture overview",
                    "Digital circuit board patterns", "DNA helix rotating"],
    "documentary": ["Sunrise over mountains", "Urban infrastructure timelapse",
                    "Ocean waves on coastline", "Historic building facade"],
    "tutorial":    ["Developer at dual monitor setup", "Whiteboard planning session",
                    "Tool usage demonstration hands", "Organized workspace flat lay"],
    "storytelling":["Two people in conversation", "Silhouette at sunset",
                    "Rain on window glass", "Empty road stretching to horizon"],
    "news":        ["Press conference exterior", "Business district street level",
                    "Government building exterior", "Data centre servers"],
    "long_form":   ["Library interior rows of books", "Mountain summit view",
                    "Industrial facility aerial"],
    "shorts":      ["Smartphone screen recording", "Trendy cafe interior",
                    "Young person reacting to phone"],
}

_IMAGE_PROMPT_TEMPLATES = [
    "Cinematic {style} scene — {desc}. {lighting} lighting, {palette_desc} color palette. "
    "Shot on ARRI Alexa, anamorphic lens, shallow depth of field. Ultra-realistic, 8K.",
    "Professional {style} video frame — {desc}. {lighting} illumination. "
    "Color grade: {palette_desc}. Photorealistic, hyper-detailed. {camera} composition.",
    "High-production-value {style} scene — {desc}. {camera} angle. "
    "{lighting} light. {palette_desc} tones. Shot list quality, cinematic aspect ratio.",
]

_NEGATIVE_PROMPT = (
    "blurry, low quality, watermark, text, logo, grain, noise, overexposed, "
    "underexposed, amateur, cartoon, anime, painting, sketch, ugly, deformed, "
    "extra limbs, bad anatomy, duplicate, NSFW"
)

_VIDEO_PROMPT_TEMPLATES = [
    "Smooth {movement} camera movement. {lighting} lighting. {desc}. "
    "Cinematic grade. 24fps. Anamorphic look.",
    "{camera} shot, {movement} pan. {desc}. {lighting} atmosphere. "
    "Professional color grade. Film grain subtle.",
]

_SCENE_TITLES: dict[str, list[str]] = {
    "educational": ["Opening Hook", "Context Setting", "Core Concept Introduction",
                    "Deep Dive", "Visual Explanation", "Real-World Application",
                    "Common Misconception", "Expert Insight", "Data & Evidence",
                    "Practical Example", "Key Takeaway", "Summary & Recap",
                    "What's Next", "Call to Engage", "Closing Thought"],
    "documentary": ["Opening Sequence", "World Setting", "Subject Introduction",
                    "The Problem", "Historical Context", "Key Moment",
                    "Turning Point", "Impact Assessment", "Expert Perspective",
                    "The Resolution", "Legacy & Reflection", "Closing Statement"],
    "tutorial":    ["What You'll Build", "Prerequisites", "Step 1: Setup",
                    "Step 2: Foundation", "Step 3: Core Logic", "Step 4: Testing",
                    "Common Errors", "Optimisation Tips", "Final Result", "Next Steps"],
    "storytelling":["The World Before", "The Inciting Incident", "Rising Tension",
                    "The Dark Moment", "The Revelation", "The Climax",
                    "Resolution", "Reflection", "The Lesson", "New Beginning"],
    "news":        ["Breaking Development", "Background Context", "Key Facts",
                    "Expert Analysis", "Wider Implications", "Looking Ahead"],
    "long_form":   ["Cold Open", "Thesis", "Historical Background", "Core Argument 1",
                    "Core Argument 2", "Core Argument 3", "Counter-argument",
                    "Evidence & Data", "Case Study", "Synthesis", "Implications",
                    "Future Outlook", "Conclusion", "Final Thought", "Outro"],
    "shorts":      ["Hook", "The Point", "The Proof", "The Call"],
}

_OBJECTS: dict[str, list[str]] = {
    "educational": ["textbook", "whiteboard", "laptop", "notebook", "pen", "graph paper",
                    "microscope", "calculator", "globe", "diagram"],
    "documentary": ["camera", "newspaper clipping", "map", "archival photo", "microphone",
                    "journal", "artifact", "document"],
    "tutorial":    ["keyboard", "mouse", "monitor", "code editor", "terminal", "diagram",
                    "sticky note", "task board"],
    "storytelling":["window", "candle", "clock", "letter", "photograph", "door",
                    "mirror", "light fixture"],
    "news":        ["microphone", "notepad", "camera", "studio desk", "monitor", "map"],
    "long_form":   ["books", "notepad", "map", "chart", "coffee cup", "whiteboard"],
    "shorts":      ["smartphone", "product", "icon", "text graphic"],
}


# ── Core generator ────────────────────────────────────────────────────────────

def generate_mock_storyboard(
    provider: str,
    request: StoryboardRequest,
    script_data: dict,
) -> StoryboardProviderResult:
    """Generate a complete deterministic mock storyboard from a script."""

    seed = f"{provider}:{request.topic.lower().strip()}:{request.script_style}"
    rng = _SeededRandom(seed)
    style = request.script_style
    topic = request.topic
    topic_cap = topic[0].upper() + topic[1:]
    target_dur_s = request.target_duration_minutes * 60

    # ── Pull sections from script_data ──────────────────────────────────────
    raw_sections: list[dict] = script_data.get("sections") or []
    if not raw_sections:
        # Synthesise sections from topic when no script data available
        section_titles = _SCENE_TITLES.get(style, _SCENE_TITLES["educational"])[:6]
        raw_sections = [
            {"title": t, "content": f"Content for {t} covering {topic}.", "duration_seconds": target_dur_s / max(len(section_titles), 1)}
            for t in section_titles
        ]

    # Add intro / hook / outro markers if absent
    all_parts: list[dict] = []
    if script_data.get("hook"):
        all_parts.append({"title": "Hook", "content": script_data["hook"], "duration_seconds": 15, "_is_hook": True})
    if script_data.get("introduction"):
        all_parts.append({"title": "Introduction", "content": script_data["introduction"], "duration_seconds": 20})
    all_parts.extend(raw_sections)
    if script_data.get("call_to_action"):
        all_parts.append({"title": "Call to Action", "content": script_data["call_to_action"], "duration_seconds": 15})
    if script_data.get("outro"):
        all_parts.append({"title": "Outro", "content": script_data["outro"], "duration_seconds": 10})

    # Total narration time from script
    narration_total_s: float = sum(float(p.get("duration_seconds", 10)) for p in all_parts)
    if narration_total_s < 1:
        narration_total_s = target_dur_s

    # ── Scene count ────────────────────────────────────────────────────────
    scenes_per_minute = {"shorts": 8, "news": 5, "tutorial": 4, "educational": 3.5,
                         "documentary": 3, "storytelling": 3, "long_form": 3}.get(style, 3.5)
    target_scene_count = max(4, min(80, int(request.target_duration_minutes * scenes_per_minute)))

    # ── Color palette ──────────────────────────────────────────────────────
    palette_options = _PALETTES.get(style, _PALETTES["educational"])
    palette = rng.choice(palette_options)
    palette_desc = "deep navy and crimson" if "#e94560" in palette else \
                   "cool slate and blue" if "#3498db" in palette else "dark cinematic"

    # ── Visual / narration pacing ──────────────────────────────────────────
    wpm = script_data.get("pacing_wpm") or rng.int(120, 145)
    visual_pacing_val = (
        VisualPacing.FAST if style == "shorts" else
        VisualPacing.VERY_SLOW if style == "documentary" else
        VisualPacing.MEDIUM
    )
    narration_pacing_val = (
        NarrationPacing.RAPID if wpm > 155 else
        NarrationPacing.ENERGETIC if wpm > 140 else
        NarrationPacing.CONVERSATIONAL if wpm > 120 else
        NarrationPacing.DELIBERATE
    )

    # ── Generate scenes ────────────────────────────────────────────────────
    scenes: list[Scene] = []
    timeline: list[SceneTimeline] = []
    narration_timing_list: list[NarrationTiming] = []
    visual_cues: list[VisualCue] = []

    scene_num = 1
    elapsed_ms = 0

    # Distribute scenes proportionally across parts
    part_scene_counts: list[int] = []
    total_dur = sum(float(p.get("duration_seconds", 10)) for p in all_parts) or 1
    remaining = target_scene_count
    for i, part in enumerate(all_parts):
        part_dur = float(part.get("duration_seconds", 10))
        frac = part_dur / total_dur
        cnt = max(1, round(frac * target_scene_count))
        if i == len(all_parts) - 1:
            cnt = remaining
        else:
            remaining -= cnt
        part_scene_counts.append(max(1, cnt))

    scene_title_pool = list(_SCENE_TITLES.get(style, _SCENE_TITLES["educational"]))
    broll_pool = _BROLL.get(style, _BROLL["educational"])
    stock_pool = _STOCK_FOOTAGE.get(style, _STOCK_FOOTAGE["educational"])
    object_pool = _OBJECTS.get(style, _OBJECTS["educational"])

    for part_idx, (part, n_scenes) in enumerate(zip(all_parts, part_scene_counts)):
        part_dur_s = float(part.get("duration_seconds", 10))
        part_dur_ms = int(part_dur_s * 1000)
        scene_dur_ms = max(2000, part_dur_ms // n_scenes)

        narration_text: str = str(part.get("content", ""))
        part_words = narration_text.split()
        words_per_scene = max(1, len(part_words) // n_scenes)

        for s in range(n_scenes):
            s_seed = f"{seed}:scene:{scene_num}"
            srng = _SeededRandom(s_seed)

            dur_ms = scene_dur_ms + srng.int(-500, 500)
            start_ms = elapsed_ms
            end_ms = start_ms + dur_ms
            elapsed_ms = end_ms

            # Narration snippet for this scene
            word_start = s * words_per_scene
            word_end = word_start + words_per_scene
            narration_snippet = " ".join(part_words[word_start:word_end]) or narration_text[:120]

            # Scene title
            if scene_title_pool:
                scene_title = scene_title_pool.pop(0)
            else:
                scene_title = part.get("title", f"Scene {scene_num}")

            # Visual type
            visual_type_options = {
                "hook": [VisualType.B_ROLL, VisualType.TEXT_OVERLAY],
                "tutorial": [VisualType.SCREEN_RECORDING, VisualType.B_ROLL, VisualType.ANIMATION],
                "shorts": [VisualType.TEXT_OVERLAY, VisualType.B_ROLL, VisualType.ANIMATION],
            }
            vt_choices = visual_type_options.get(style, [VisualType.B_ROLL, VisualType.ILLUSTRATION, VisualType.ANIMATION])
            visual_type = srng.choice(vt_choices)

            # Camera
            shot_types = [ShotType.WIDE, ShotType.MEDIUM, ShotType.CLOSE_UP, ShotType.ESTABLISHING]
            if part_idx == 0 and s == 0:
                shot_type = ShotType.ESTABLISHING
            elif s % 3 == 0:
                shot_type = ShotType.WIDE
            elif s % 3 == 1:
                shot_type = ShotType.MEDIUM
            else:
                shot_type = ShotType.CLOSE_UP
            shot_type = ShotType(srng.choice([st.value for st in shot_types]) if srng.float() > 0.4 else shot_type.value)

            camera_angle = srng.choice(_CAMERA_ANGLES)
            cam_movements = list(CameraMovement)
            if shot_type == ShotType.ESTABLISHING:
                cam_movements_weighted = [CameraMovement.PAN_LEFT, CameraMovement.PAN_RIGHT, CameraMovement.DOLLY_IN]
            elif visual_type == VisualType.TEXT_OVERLAY:
                cam_movements_weighted = [CameraMovement.STATIC, CameraMovement.ZOOM_IN]
            else:
                cam_movements_weighted = cam_movements[:6]
            camera_movement = srng.choice(cam_movements_weighted)

            zoom_inst: str | None = None
            pan_inst: str | None = None
            if camera_movement in (CameraMovement.ZOOM_IN, CameraMovement.ZOOM_OUT):
                zoom_inst = f"{'Slow zoom in' if camera_movement == CameraMovement.ZOOM_IN else 'Slow zoom out'} over {dur_ms // 1000}s"
            elif camera_movement in (CameraMovement.PAN_LEFT, CameraMovement.PAN_RIGHT):
                pan_inst = f"{'Left' if camera_movement == CameraMovement.PAN_LEFT else 'Right'} pan at 5 degrees/second"

            # Transition
            trans_types = [TransitionType.CUT, TransitionType.DISSOLVE, TransitionType.FADE]
            if scene_num == 1:
                transition = TransitionType.FADE
            elif s == n_scenes - 1 and part_idx < len(all_parts) - 1:
                transition = srng.choice([TransitionType.DISSOLVE, TransitionType.CUT])
            else:
                transition = TransitionType.CUT
            trans_dur = 0 if transition == TransitionType.CUT else srng.int(400, 800)

            # Lighting
            lighting_map = {
                "educational": [LightingStyle.STUDIO, LightingStyle.SOFT, LightingStyle.NATURAL],
                "documentary": [LightingStyle.NATURAL, LightingStyle.CINEMATIC, LightingStyle.DRAMATIC],
                "tutorial": [LightingStyle.HIGH_KEY, LightingStyle.STUDIO, LightingStyle.SOFT],
                "storytelling": [LightingStyle.DRAMATIC, LightingStyle.LOW_KEY, LightingStyle.GOLDEN_HOUR],
                "news": [LightingStyle.STUDIO, LightingStyle.HIGH_KEY],
            }
            lighting = srng.choice(lighting_map.get(style, [LightingStyle.CINEMATIC, LightingStyle.NATURAL]))

            # Prompts
            prompt_template = srng.choice(_IMAGE_PROMPT_TEMPLATES)
            lighting_words = {"natural": "natural daylight", "studio": "professional studio",
                              "cinematic": "cinematic side", "dramatic": "dramatic chiaroscuro",
                              "soft": "soft diffuse", "golden_hour": "warm golden-hour",
                              "low_key": "low-key dark", "high_key": "high-key bright"}.get(lighting.value, "cinematic")
            visual_desc = f"{scene_title.lower()} visual for '{topic}'"
            image_prompt = (
                prompt_template
                .replace("{style}", style.replace("_", " "))
                .replace("{desc}", visual_desc)
                .replace("{lighting}", lighting_words)
                .replace("{palette_desc}", palette_desc)
                .replace("{camera}", shot_type.value.replace("_", " "))
            )
            video_prompt_template = srng.choice(_VIDEO_PROMPT_TEMPLATES)
            video_prompt = (
                video_prompt_template
                .replace("{movement}", camera_movement.value.replace("_", " "))
                .replace("{lighting}", lighting_words)
                .replace("{desc}", visual_desc)
                .replace("{camera}", shot_type.value.replace("_", " "))
            )

            # Emotion & colour
            emotion = srng.choice(_EMOTIONS)
            bg_desc = srng.choice([
                f"Clean {style.replace('_',' ')} background with subtle gradient",
                f"Blurred real-world environment suggesting {topic}",
                f"Abstract geometric pattern in {palette_desc} tones",
                f"Minimalist studio backdrop",
                f"Natural outdoor environment related to {topic}",
            ])
            fg_desc = srng.choice([
                f"Subject engaging with {srng.choice(object_pool)}",
                f"Hands demonstrating concept",
                f"Text graphic in foreground",
                f"Animated icon overlay",
            ])

            # Characters & objects
            characters: list[str] = []
            if visual_type in (VisualType.TALKING_HEAD, VisualType.B_ROLL) and srng.float() > 0.4:
                characters = srng.choice([["presenter"], ["expert subject"], ["student", "teacher"], []])
            objects = srng.sample(object_pool, srng.int(1, 3))

            # Text overlays
            text_overlays: list[str] = []
            if visual_type in (VisualType.TEXT_OVERLAY, VisualType.ANIMATION) or srng.float() > 0.6:
                text_overlays = [
                    f"KEY POINT: {scene_title.upper()}",
                    f"📌 {topic_cap}",
                ]

            # Subtitles
            subtitle = SubtitleTiming(
                start_ms=start_ms,
                end_ms=end_ms,
                text=narration_snippet[:120],
                speaker="narrator",
            )

            # Sound
            sfx = srng.sample(_SFX, srng.int(1, 2))
            music_mood = srng.choice(_MUSIC_MOODS)

            # B-roll & stock
            broll = srng.sample(broll_pool, srng.int(1, 2))
            stock = srng.sample(stock_pool, srng.int(1, 2))

            # Asset requirements
            assets: list[SceneAsset] = [
                SceneAsset(
                    asset_type=AssetType.IMAGE,
                    description=f"AI-generated {visual_type.value.replace('_',' ')} image: {visual_desc}",
                    is_required=True,
                    source_type="generate",
                ),
            ]
            if visual_type == VisualType.SCREEN_RECORDING:
                assets.append(SceneAsset(asset_type=AssetType.VIDEO_CLIP,
                                         description="Screen recording of process", source_type="record"))
            if sfx:
                assets.append(SceneAsset(asset_type=AssetType.SOUND_EFFECT,
                                         description=sfx[0], source_type="stock",
                                         search_query=f"{sfx[0]} sound effect"))

            # Animation instructions
            animations: list[AnimationInstruction] = []
            if text_overlays:
                animations.append(AnimationInstruction(
                    element="text_overlay",
                    animation_type=srng.choice(["fade_in", "slide_in", "typewriter"]),
                    duration_ms=srng.int(300, 600),
                ))
            if srng.float() > 0.5:
                animations.append(AnimationInstruction(
                    element="scene_frame",
                    animation_type=srng.choice(["fade_in", "scale"]),
                    duration_ms=srng.int(200, 500),
                ))

            # Importance score — hook and CTA are high importance
            importance = (
                0.95 if part_idx == 0 and s == 0 else
                0.90 if part.get("title") in ("Call to Action", "Outro") else
                srng.flt(0.4, 0.85)
            )

            # Build scene
            scene = Scene(
                scene_number=scene_num,
                scene_title=scene_title,
                start_time_ms=start_ms,
                end_time_ms=end_ms,
                duration_ms=dur_ms,
                narration=narration_snippet,
                visual_description=f"{shot_type.value.replace('_',' ')} shot — {bg_desc}. {fg_desc}.",
                visual_type=visual_type,
                prompts=ScenePrompt(
                    image_prompt=image_prompt,
                    negative_prompt=_NEGATIVE_PROMPT,
                    video_prompt=video_prompt,
                    style_preset="cinematic",
                ),
                shot_type=shot_type,
                camera_angle=camera_angle,
                camera_movement=camera_movement,
                zoom_instructions=zoom_inst,
                pan_instructions=pan_inst,
                animation_suggestions=animations,
                transition_type=transition,
                transition_duration_ms=trans_dur,
                scene_emotion=emotion,
                color_palette=palette,
                lighting_style=lighting,
                background_description=bg_desc,
                foreground_description=fg_desc,
                characters=characters,
                objects=objects,
                text_overlay_suggestions=text_overlays,
                subtitle_timing=subtitle,
                sound_effect_suggestions=sfx,
                background_music_mood=music_mood,
                b_roll_suggestions=broll,
                stock_footage_suggestions=stock,
                asset_requirements=assets,
                importance_score=round(importance, 3),
                estimated_image_count=srng.int(1, 3),
                estimated_video_length_seconds=round(dur_ms / 1000, 1),
            )
            scenes.append(scene)

            # Timeline entry
            timeline.append(SceneTimeline(
                scene_number=scene_num,
                scene_title=scene_title,
                start_time_ms=start_ms,
                end_time_ms=end_ms,
                duration_ms=dur_ms,
                shot_type=shot_type,
                transition_type=transition,
                visual_type=visual_type,
                importance_score=round(importance, 3),
            ))

            # Narration timing entry
            wc = len(narration_snippet.split())
            narration_timing_list.append(NarrationTiming(
                scene_number=scene_num,
                scene_title=scene_title,
                start_ms=start_ms,
                end_ms=end_ms,
                wpm=float(wpm),
                word_count=wc,
                speaker_note="narrator" if characters else None,
            ))

            # Visual cues at scene boundaries
            visual_cues.append(VisualCue(
                time_ms=start_ms,
                cue_type="cut" if transition == TransitionType.CUT else "transition",
                description=f"Scene {scene_num}: {scene_title} — {transition.value}",
                scene_number=scene_num,
                duration_ms=trans_dur,
            ))
            if text_overlays:
                visual_cues.append(VisualCue(
                    time_ms=start_ms + 200,
                    cue_type="graphic",
                    description=text_overlays[0],
                    scene_number=scene_num,
                    duration_ms=srng.int(2000, 4000),
                ))

            scene_num += 1

    total_duration_s = elapsed_ms // 1000
    image_count = sum(s.estimated_image_count for s in scenes)

    # ── Production metrics ─────────────────────────────────────────────────
    scene_count = len(scenes)
    # Editing complexity: 0–1 score based on scene count, transitions, animations
    anim_count = sum(len(s.animation_suggestions) for s in scenes)
    dissolve_count = sum(1 for s in scenes if s.transition_type != TransitionType.CUT)
    complexity = min(1.0, round(
        0.3 * min(1, scene_count / 40)
        + 0.3 * min(1, anim_count / (scene_count * 2))
        + 0.2 * min(1, dissolve_count / scene_count)
        + 0.2 * min(1, image_count / (scene_count * 2)),
        3,
    ))
    render_time_min = max(1, round(image_count * 0.15 + scene_count * 0.05))
    cost_usd = round(image_count * 0.04 + scene_count * 0.01, 2)

    # Title
    title_options = [
        f"{topic_cap} — Full Production Storyboard",
        f"Storyboard: {topic_cap}",
        f"{topic_cap} | Scene Plan v1",
        f"Production Storyboard — {topic_cap}",
    ]
    title = rng.choice(title_options)

    confidence_base = {"openai": 0.91, "gemini": 0.88, "claude": 0.93, "openrouter": 0.85}
    confidence = round(confidence_base.get(provider, 0.88) + rng.float(-0.03, 0.03), 3)

    return StoryboardProviderResult(
        provider_name=provider,
        topic=topic,
        title=title,
        scenes=scenes,
        scene_timeline=timeline,
        narration_timing=narration_timing_list,
        visual_cues=visual_cues,
        total_duration_seconds=total_duration_s,
        scene_count=scene_count,
        image_count=image_count,
        editing_complexity_score=complexity,
        estimated_render_time_minutes=render_time_min,
        estimated_cost_usd=cost_usd,
        visual_pacing=visual_pacing_val,
        narration_pacing=narration_pacing_val,
        confidence=confidence,
    )
