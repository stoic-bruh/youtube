"""ScenePlanner — placeholder interface.

Responsible for:
- Breaking a script into scenes/shots
- Assigning visual type to each scene (B-roll, talking head, animation, text overlay)
- Generating image prompts for each scene
- Scene timing calculations
"""
from dataclasses import dataclass, field

from app.services.script_service import Script


@dataclass
class Scene:
    index: int
    script_segment: str
    visual_type: str  # b-roll | talking-head | animation | text-overlay | stock
    image_prompt: str
    duration_seconds: float = 5.0
    narration: str = ""
    on_screen_text: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class ScenePlan:
    scenes: list[Scene]
    total_duration_seconds: float = 0.0
    scene_count: int = 0


class ScenePlanner:
    """Placeholder implementation — real scene planning to be implemented."""

    async def plan_scenes(self, script: Script) -> ScenePlan:
        """Break a script into individual scenes with visual assignments.

        Args:
            script: Script object from ScriptService.

        Returns:
            ScenePlan with list of Scene objects.
        """
        # TODO: Implement using OpenAI structured output to split script + assign visuals
        scenes = []
        for i, section in enumerate(script.sections or [{"title": "Main", "content": script.body}]):
            scenes.append(
                Scene(
                    index=i,
                    script_segment=str(section.get("content", "")),
                    visual_type="b-roll",
                    image_prompt=f"[PLACEHOLDER] Visual for: {section.get('title', 'scene')}",
                    duration_seconds=5.0,
                    narration=str(section.get("content", "")),
                )
            )

        return ScenePlan(
            scenes=scenes,
            total_duration_seconds=sum(s.duration_seconds for s in scenes),
            scene_count=len(scenes),
        )

    async def generate_image_prompts(self, scene_plan: ScenePlan) -> ScenePlan:
        """Enhance each scene with detailed image generation prompts.

        Args:
            scene_plan: ScenePlan from plan_scenes().

        Returns:
            ScenePlan with enriched image_prompt fields.
        """
        # TODO: Implement using OpenAI to generate detailed visual descriptions
        for scene in scene_plan.scenes:
            scene.image_prompt = f"[PLACEHOLDER] Detailed cinematic prompt: {scene.image_prompt}"
        return scene_plan
