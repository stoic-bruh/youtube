"""ImageGenerator — placeholder interface.

Responsible for:
- Generating scene images from prompts (DALL-E / Stable Diffusion)
- Image style consistency across a video
- Image upscaling and post-processing
- Asset caching to avoid duplicate generation
"""
from dataclasses import dataclass

from app.services.scene_planner import Scene, ScenePlan


@dataclass
class GeneratedImage:
    scene_index: int
    prompt: str
    local_path: str
    url: str
    width: int = 1920
    height: int = 1080
    provider: str = "placeholder"
    cost_usd: float = 0.0


class ImageGenerator:
    """Placeholder implementation — real image generation to be implemented."""

    async def generate_for_scene(self, scene: Scene, style: str = "cinematic") -> GeneratedImage:
        """Generate an image for a single scene.

        Args:
            scene: Scene object with image_prompt.
            style: Visual style directive passed to the image model.

        Returns:
            GeneratedImage with local_path and url.
        """
        # TODO: Implement using DALL-E 3 / Stable Diffusion API
        return GeneratedImage(
            scene_index=scene.index,
            prompt=scene.image_prompt,
            local_path=f"/tmp/scene_{scene.index:04d}.png",
            url="",
            provider="placeholder",
        )

    async def generate_for_plan(
        self, scene_plan: ScenePlan, style: str = "cinematic"
    ) -> list[GeneratedImage]:
        """Generate images for all scenes in a plan.

        Args:
            scene_plan: ScenePlan from ScenePlanner.
            style: Shared visual style for the whole video.

        Returns:
            List of GeneratedImage in scene order.
        """
        # TODO: Implement with concurrency control (respect rate limits)
        return [
            await self.generate_for_scene(scene, style) for scene in scene_plan.scenes
        ]

    async def upscale(self, image: GeneratedImage, target_width: int = 3840) -> GeneratedImage:
        """Upscale an image to a higher resolution.

        Args:
            image: GeneratedImage to upscale.
            target_width: Target width in pixels.

        Returns:
            Upscaled GeneratedImage.
        """
        # TODO: Implement using Real-ESRGAN or Stability AI upscaler
        return GeneratedImage(**{**image.__dict__, "width": target_width, "height": target_width * 9 // 16})
