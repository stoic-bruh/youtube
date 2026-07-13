"""Deterministic seeded mock asset generator — used by all provider stubs."""
from __future__ import annotations

import hashlib
import random
from typing import Any

from app.schemas.asset import AssetKind, AssetLicense, AssetProviderResult

# ── Lookup tables ──────────────────────────────────────────────────────────────

_PHOTO_TAGS: dict[str, list[str]] = {
    "educational": ["classroom", "learning", "books", "knowledge", "students"],
    "documentary": ["nature", "wildlife", "landscape", "people", "culture"],
    "tutorial": ["hands", "screen", "workspace", "tools", "demonstration"],
    "storytelling": ["narrative", "emotion", "character", "journey", "drama"],
    "news": ["journalism", "breaking", "reporter", "world", "current"],
    "default": ["visual", "concept", "abstract", "modern", "creative"],
}

_VIDEO_TAGS = ["motion", "footage", "clip", "background", "cinematic", "timelapse", "aerial"]
_ICON_TAGS = ["ui", "interface", "symbol", "glyph", "vector"]

_ASPECT_RATIOS: dict[str, str] = {
    "16:9": "16:9",
    "4:3": "4:3",
    "1:1": "1:1",
    "9:16": "9:16",
    "21:9": "21:9",
}

_LICENSES_STOCK = [
    AssetLicense.CC0,
    AssetLicense.PUBLIC_DOMAIN,
    AssetLicense.CC_BY,
    AssetLicense.COMMERCIAL,
]
_LICENSES_GENERATED = [AssetLicense.GENERATED]
_LICENSES_ICON = [AssetLicense.MIT, AssetLicense.CC0]

# Provider-specific cost tables (USD per asset)
_PROVIDER_COSTS: dict[str, float] = {
    "flux": 0.055,
    "sdxl": 0.032,
    "gpt_image": 0.040,
    "gemini_image": 0.038,
    "ideogram": 0.080,
    "wikimedia": 0.0,
    "unsplash": 0.0,
    "pixabay": 0.0,
    "pexels": 0.0,
    "pexels_video": 0.0,
    "pixabay_video": 0.0,
    "mixkit": 0.0,
    "lucide": 0.0,
    "heroicons": 0.0,
    "material_icons": 0.0,
}

# Provider-specific base URLs for mock assets
_PROVIDER_URLS: dict[str, str] = {
    "flux": "https://cdn.flux.ai/generated",
    "sdxl": "https://cdn.stability.ai/generated",
    "gpt_image": "https://oaidalleapiprodscus.blob.core.windows.net/generated",
    "gemini_image": "https://generativelanguage.googleapis.com/generated",
    "ideogram": "https://cdn.ideogram.ai/generated",
    "wikimedia": "https://upload.wikimedia.org/wikipedia/commons",
    "unsplash": "https://images.unsplash.com/photo",
    "pixabay": "https://pixabay.com/images",
    "pexels": "https://images.pexels.com/photos",
    "pexels_video": "https://videos.pexels.com/video-files",
    "pixabay_video": "https://pixabay.com/videos",
    "mixkit": "https://assets.mixkit.co/videos",
    "lucide": "https://cdn.jsdelivr.net/npm/lucide-static/icons",
    "heroicons": "https://cdn.jsdelivr.net/npm/heroicons",
    "material_icons": "https://fonts.gstatic.com/s/i/materialicons",
}

_IMAGE_DIMS: list[tuple[int, int]] = [
    (1920, 1080), (1280, 720), (2560, 1440), (3840, 2160), (1024, 1024),
]
_VIDEO_DIMS: list[tuple[int, int]] = [(1920, 1080), (1280, 720), (3840, 2160)]
_ICON_DIMS: list[tuple[int, int]] = [(24, 24), (48, 48), (64, 64), (128, 128)]


class _RNG:
    """Seeded random for deterministic mock output."""

    def __init__(self, seed: str) -> None:
        digest = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
        self._r = random.Random(digest)  # noqa: S311

    def choice(self, seq: list[Any]) -> Any:
        return self._r.choice(seq)

    def float(self, lo: float, hi: float) -> float:
        return round(lo + self._r.random() * (hi - lo), 4)

    def int(self, lo: int, hi: int) -> int:
        return self._r.randint(lo, hi)

    def bool(self, p: float = 0.5) -> bool:
        return self._r.random() < p

    def sample(self, seq: list[Any], k: int) -> list[Any]:
        return self._r.sample(seq, min(k, len(seq)))


def _aspect(w: int, h: int) -> str:
    from math import gcd
    d = gcd(w, h)
    return f"{w // d}:{h // d}"


class MockAssetGenerator:
    """Generates fully-populated deterministic AssetProviderResult for any provider."""

    def generate(
        self,
        provider_name: str,
        query: str,
        asset_kind: AssetKind,
        *,
        prompt: str = "",
        negative_prompt: str = "",
        width: int = 1920,
        height: int = 1080,
        style_hint: str = "default",
        scene_index: int = 0,
    ) -> AssetProviderResult:
        seed = f"{provider_name}:{query}:{asset_kind}:{scene_index}"
        rng = _RNG(seed)

        # Decide if this provider "finds" or "generates" a result
        is_generator = provider_name in {
            "flux", "sdxl", "gpt_image", "gemini_image", "ideogram"
        }
        is_icon = provider_name in {"lucide", "heroicons", "material_icons"}
        is_video = "video" in provider_name or provider_name == "mixkit"

        # Stock providers: simulate a 90 % hit rate
        if not is_generator and not rng.bool(0.90):
            return AssetProviderResult(
                provider_name=provider_name,
                found=False,
                asset_kind=asset_kind,
                error="No matching asset found in stock library",
            )

        # Dimensions
        if is_icon:
            dims = rng.choice(_ICON_DIMS)
        elif is_video:
            dims = rng.choice(_VIDEO_DIMS)
        else:
            dims = (width, height)

        w, h = dims

        # Unique asset ID
        asset_id = f"mock-{provider_name}-{abs(hash(seed)) % 10_000_000:07d}"

        # URL
        base_url = _PROVIDER_URLS.get(provider_name, "https://mock.asset.local")
        if is_icon:
            ext = "svg"
            url = f"{base_url}/{query.replace(' ', '-').lower()}.{ext}"
        elif is_video:
            ext = "mp4"
            url = f"{base_url}/{asset_id}.{ext}"
        else:
            ext = "jpg" if not is_generator else "png"
            url = f"{base_url}/{asset_id}.{ext}"

        # License
        if is_generator:
            license_ = rng.choice(_LICENSES_GENERATED)
        elif is_icon:
            license_ = rng.choice(_LICENSES_ICON)
        else:
            license_ = rng.choice(_LICENSES_STOCK)

        # Tags
        tag_pool = _VIDEO_TAGS if is_video else (_ICON_TAGS if is_icon else _PHOTO_TAGS.get(style_hint, _PHOTO_TAGS["default"]))
        keyword_tags = query.split()[:3]
        tags = keyword_tags + rng.sample(tag_pool, 3)

        # Scores
        quality_score = rng.float(0.72, 0.98)
        relevance_score = rng.float(0.68, 0.99)

        # File size (bytes)
        if is_icon:
            file_size = rng.int(2_000, 20_000)
        elif is_video:
            file_size = rng.int(5_000_000, 80_000_000)
        else:
            file_size = rng.int(400_000, 8_000_000)

        # Cost
        cost = _PROVIDER_COSTS.get(provider_name, 0.0)
        if is_generator:
            cost = round(cost * rng.float(0.8, 1.2), 4)

        # Generation time (ms)
        if is_generator:
            gen_time = rng.int(2000, 12000)
        else:
            gen_time = rng.int(100, 800)

        # Generation parameters
        gen_params: dict[str, Any] = {"width": w, "height": h}
        if is_generator:
            gen_params.update({
                "steps": rng.int(20, 50),
                "guidance_scale": round(rng.float(5.0, 12.0), 1),
                "seed": rng.int(0, 2**31),
                "scheduler": rng.choice(["DPM++", "DDIM", "Euler a", "PNDM"]),
            })

        cache_dir = f"/tmp/asset_cache/{provider_name}"
        local_path = f"{cache_dir}/{asset_id}.{ext}"
        thumb_path = f"{cache_dir}/thumb_{asset_id}.jpg" if not is_icon else None

        return AssetProviderResult(
            provider_name=provider_name,
            found=True,
            asset_kind=asset_kind,
            provider_asset_id=asset_id,
            source_url=url,
            license=license_,
            prompt=prompt or query,
            negative_prompt=negative_prompt,
            generation_parameters=gen_params,
            width=w,
            height=h,
            aspect_ratio=_aspect(w, h),
            cost_estimate_usd=cost,
            generation_time_ms=gen_time,
            file_size_bytes=file_size,
            tags=tags,
            quality_score=quality_score,
            relevance_score=relevance_score,
        )
