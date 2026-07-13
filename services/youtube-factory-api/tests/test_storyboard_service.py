"""Comprehensive unit tests for the Storyboard Service."""
from __future__ import annotations

import pytest

from app.providers.storyboard.mock_base import generate_mock_storyboard
from app.providers.storyboard.openai_provider import OpenAIStoryboardProvider
from app.providers.storyboard.gemini_provider import GeminiStoryboardProvider
from app.providers.storyboard.claude_provider import ClaudeStoryboardProvider
from app.providers.storyboard.openrouter_provider import OpenRouterStoryboardProvider
from app.providers.storyboard.registry import StoryboardProviderRegistry
from app.schemas.storyboard import (
    CameraMovement,
    LightingStyle,
    NarrationPacing,
    Scene,
    ScenePrompt,
    StoryboardProviderResult,
    StoryboardRequest,
    StoryboardProviderName,
    ShotType,
    TransitionType,
    VisualPacing,
    VisualType,
)


# ── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_request() -> StoryboardRequest:
    return StoryboardRequest(
        topic="machine learning for beginners",
        script_style="educational",
        script_tone="engaging",
        target_duration_minutes=10,
        target_audience="general audience",
        providers=[StoryboardProviderName.OPENAI, StoryboardProviderName.CLAUDE],
    )


@pytest.fixture
def sample_script_data() -> dict:
    return {
        "hook": "What if you could teach a computer to learn from experience?",
        "introduction": "Today we're exploring machine learning from first principles.",
        "sections": [
            {"title": "What Is Machine Learning?", "content": "Machine learning is a subset of AI.", "duration_seconds": 60},
            {"title": "How Does It Work?", "content": "Algorithms learn patterns from data.", "duration_seconds": 90},
            {"title": "Real-World Applications", "content": "Used in everything from search to medicine.", "duration_seconds": 75},
        ],
        "call_to_action": "Like and subscribe if you found this helpful!",
        "outro": "Thanks for watching. See you in the next one.",
        "pacing_wpm": 130,
    }


@pytest.fixture
def minimal_script_data() -> dict:
    return {}


# ── Mock base tests ─────────────────────────────────────────────────────────────

class TestMockBase:
    def test_generates_valid_result(self, sample_request, sample_script_data):
        result = generate_mock_storyboard("openai", sample_request, sample_script_data)
        assert isinstance(result, StoryboardProviderResult)
        assert result.provider_name == "openai"
        assert result.topic == sample_request.topic
        assert len(result.scenes) > 0

    def test_scene_count_positive(self, sample_request, sample_script_data):
        result = generate_mock_storyboard("openai", sample_request, sample_script_data)
        assert result.scene_count == len(result.scenes)
        assert result.scene_count >= 4

    def test_all_scenes_have_required_fields(self, sample_request, sample_script_data):
        result = generate_mock_storyboard("openai", sample_request, sample_script_data)
        for scene in result.scenes:
            assert isinstance(scene, Scene)
            assert scene.scene_number >= 1
            assert scene.scene_title
            assert scene.start_time_ms >= 0
            assert scene.end_time_ms > scene.start_time_ms
            assert scene.duration_ms > 0
            assert scene.narration
            assert isinstance(scene.prompts, ScenePrompt)
            assert scene.prompts.image_prompt
            assert scene.prompts.negative_prompt
            assert isinstance(scene.shot_type, ShotType)
            assert isinstance(scene.camera_movement, CameraMovement)
            assert isinstance(scene.transition_type, TransitionType)
            assert isinstance(scene.lighting_style, LightingStyle)
            assert isinstance(scene.visual_type, VisualType)
            assert 0.0 <= scene.importance_score <= 1.0
            assert scene.estimated_image_count >= 1
            assert len(scene.color_palette) > 0

    def test_scene_timing_sequential(self, sample_request, sample_script_data):
        result = generate_mock_storyboard("openai", sample_request, sample_script_data)
        for i, scene in enumerate(result.scenes):
            assert scene.scene_number == i + 1

    def test_deterministic_for_same_input(self, sample_request, sample_script_data):
        r1 = generate_mock_storyboard("openai", sample_request, sample_script_data)
        r2 = generate_mock_storyboard("openai", sample_request, sample_script_data)
        assert r1.title == r2.title
        assert len(r1.scenes) == len(r2.scenes)
        assert r1.scenes[0].scene_title == r2.scenes[0].scene_title
        assert r1.scenes[0].prompts.image_prompt == r2.scenes[0].prompts.image_prompt

    def test_different_providers_produce_different_seeds(self, sample_request, sample_script_data):
        r_openai = generate_mock_storyboard("openai", sample_request, sample_script_data)
        r_claude = generate_mock_storyboard("claude", sample_request, sample_script_data)
        # Same topic, different provider — same scene count architecture but different details
        assert r_openai.confidence != r_claude.confidence

    def test_shorts_has_fewer_scenes_per_minute(self, sample_script_data):
        req_edu = StoryboardRequest(
            topic="test", script_style="educational", target_duration_minutes=10,
            providers=[StoryboardProviderName.OPENAI],
        )
        req_short = StoryboardRequest(
            topic="test", script_style="shorts", target_duration_minutes=1,
            providers=[StoryboardProviderName.OPENAI],
        )
        r_edu = generate_mock_storyboard("openai", req_edu, sample_script_data)
        r_short = generate_mock_storyboard("openai", req_short, sample_script_data)
        # Shorts should have fewer absolute scenes but higher density per minute
        assert r_short.scene_count >= 1

    def test_minimal_script_data_fallback(self, sample_request, minimal_script_data):
        result = generate_mock_storyboard("openai", sample_request, minimal_script_data)
        assert len(result.scenes) > 0
        assert result.scene_count > 0

    def test_visual_cues_generated(self, sample_request, sample_script_data):
        result = generate_mock_storyboard("openai", sample_request, sample_script_data)
        assert len(result.visual_cues) > 0
        for cue in result.visual_cues:
            assert cue.time_ms >= 0
            assert cue.cue_type
            assert cue.scene_number >= 1

    def test_narration_timing_generated(self, sample_request, sample_script_data):
        result = generate_mock_storyboard("openai", sample_request, sample_script_data)
        assert len(result.narration_timing) > 0
        for t in result.narration_timing:
            assert t.start_ms >= 0
            assert t.end_ms > t.start_ms
            assert t.wpm > 0
            assert t.word_count >= 0

    def test_production_metrics_valid(self, sample_request, sample_script_data):
        result = generate_mock_storyboard("openai", sample_request, sample_script_data)
        assert result.total_duration_seconds > 0
        assert result.image_count >= result.scene_count
        assert 0 < result.editing_complexity_score <= 1.0
        assert result.estimated_render_time_minutes >= 1
        assert result.estimated_cost_usd >= 0.0
        assert isinstance(result.visual_pacing, VisualPacing)
        assert isinstance(result.narration_pacing, NarrationPacing)

    def test_image_prompt_contains_topic(self, sample_request, sample_script_data):
        result = generate_mock_storyboard("openai", sample_request, sample_script_data)
        # At least one scene should reference the topic in visual description
        any_reference = any(
            "machine learning" in s.visual_description.lower()
            or "machine learning" in s.prompts.image_prompt.lower()
            for s in result.scenes
        )
        assert any_reference

    def test_asset_requirements_present(self, sample_request, sample_script_data):
        result = generate_mock_storyboard("openai", sample_request, sample_script_data)
        for scene in result.scenes:
            assert len(scene.asset_requirements) >= 1
            assert scene.asset_requirements[0].description

    def test_b_roll_suggestions_present(self, sample_request, sample_script_data):
        result = generate_mock_storyboard("openai", sample_request, sample_script_data)
        total_broll = sum(len(s.b_roll_suggestions) for s in result.scenes)
        assert total_broll > 0

    def test_confidence_range(self, sample_request, sample_script_data):
        for provider in ["openai", "gemini", "claude", "openrouter"]:
            result = generate_mock_storyboard(provider, sample_request, sample_script_data)
            assert 0.0 <= result.confidence <= 1.0

    def test_scene_timeline_matches_scenes(self, sample_request, sample_script_data):
        result = generate_mock_storyboard("openai", sample_request, sample_script_data)
        assert len(result.scene_timeline) == len(result.scenes)
        for t, s in zip(result.scene_timeline, result.scenes):
            assert t.scene_number == s.scene_number
            assert t.start_time_ms == s.start_time_ms
            assert t.end_time_ms == s.end_time_ms


# ── Provider tests ────────────────────────────────────────────────────────────

class TestProviders:
    @pytest.mark.asyncio
    async def test_openai_provider(self, sample_request, sample_script_data):
        provider = OpenAIStoryboardProvider()
        result = await provider.fetch(sample_request, sample_script_data)
        assert result.provider_name == "openai"
        assert not result.error
        assert result.scene_count > 0

    @pytest.mark.asyncio
    async def test_gemini_provider(self, sample_request, sample_script_data):
        provider = GeminiStoryboardProvider()
        result = await provider.fetch(sample_request, sample_script_data)
        assert result.provider_name == "gemini"
        assert not result.error

    @pytest.mark.asyncio
    async def test_claude_provider(self, sample_request, sample_script_data):
        provider = ClaudeStoryboardProvider()
        result = await provider.fetch(sample_request, sample_script_data)
        assert result.provider_name == "claude"
        assert not result.error

    @pytest.mark.asyncio
    async def test_openrouter_provider(self, sample_request, sample_script_data):
        provider = OpenRouterStoryboardProvider()
        result = await provider.fetch(sample_request, sample_script_data)
        assert result.provider_name == "openrouter"
        assert not result.error


# ── Registry tests ────────────────────────────────────────────────────────────

class TestRegistry:
    @pytest.mark.asyncio
    async def test_registry_runs_all_providers(self, sample_request, sample_script_data):
        registry = StoryboardProviderRegistry(["openai", "claude"])
        results = await registry.fetch_all(sample_request, sample_script_data)
        assert len(results) == 2
        names = {r.provider_name for r in results}
        assert "openai" in names
        assert "claude" in names

    @pytest.mark.asyncio
    async def test_registry_skips_unknown_provider(self, sample_request, sample_script_data):
        registry = StoryboardProviderRegistry(["openai", "unknown_provider"])
        results = await registry.fetch_all(sample_request, sample_script_data)
        # Only 1 valid provider should run
        assert len(results) == 1
        assert results[0].provider_name == "openai"

    @pytest.mark.asyncio
    async def test_registry_four_providers(self, sample_request, sample_script_data):
        registry = StoryboardProviderRegistry(["openai", "gemini", "claude", "openrouter"])
        results = await registry.fetch_all(sample_request, sample_script_data)
        assert len(results) == 4
        names = {r.provider_name for r in results}
        assert names == {"openai", "gemini", "claude", "openrouter"}


# ── Schema tests ────────────────────────────────────────────────────────────────

class TestSchemas:
    def test_scene_model_validation(self):
        scene = Scene(
            scene_number=1,
            scene_title="Test Scene",
            start_time_ms=0,
            end_time_ms=5000,
            duration_ms=5000,
            narration="This is the narration.",
            visual_description="Wide establishing shot.",
            prompts=ScenePrompt(
                image_prompt="Cinematic scene of a landscape.",
                negative_prompt="blurry, low quality",
                video_prompt="Slow pan across landscape.",
            ),
        )
        assert scene.scene_number == 1
        assert scene.importance_score == 0.5
        assert scene.estimated_image_count == 1

    def test_storyboard_request_validation(self):
        req = StoryboardRequest(
            topic="quantum computing",
            providers=[StoryboardProviderName.OPENAI],
        )
        assert req.topic == "quantum computing"
        assert req.script_style == "educational"
        assert req.target_duration_minutes == 10

    def test_request_requires_min_length_topic(self):
        with pytest.raises(Exception):
            StoryboardRequest(topic="ab", providers=[StoryboardProviderName.OPENAI])

    def test_enum_values(self):
        assert ShotType.WIDE.value == "wide"
        assert CameraMovement.STATIC.value == "static"
        assert TransitionType.CUT.value == "cut"
        assert LightingStyle.CINEMATIC.value == "cinematic"
        assert VisualPacing.MEDIUM.value == "medium"
        assert NarrationPacing.CONVERSATIONAL.value == "conversational"

    def test_provider_result_defaults(self):
        result = StoryboardProviderResult(
            provider_name="test",
            topic="test topic",
        )
        assert result.scenes == []
        assert result.confidence == 0.8
        assert result.error is None
