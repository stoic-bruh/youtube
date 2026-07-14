"""Unit tests for ThumbnailService and the Thumbnail Engine scoring utilities.

Tests pure-logic functions that do not require a running database, real video
files, or FFmpeg. The execute_thumbnail path (which needs FFmpeg + Pillow +
real JPEG files) is covered by integration tests elsewhere.

Run with: pytest tests/test_thumbnail_service.py -v
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Scoring utilities ─────────────────────────────────────────────────────────

class TestSharpnessScore:
    """sharpness_score needs a real JPEG — test it with a synthesized image."""

    def test_returns_float(self, tmp_path):
        from PIL import Image
        from app.services.postprocess.scoring import sharpness_score

        img_path = str(tmp_path / "test.jpg")
        img = Image.new("RGB", (64, 64), color=(128, 128, 128))
        img.save(img_path)
        result = sharpness_score(img_path)
        assert isinstance(result, float)

    def test_flat_image_has_low_sharpness(self, tmp_path):
        from PIL import Image, ImageDraw
        from app.services.postprocess.scoring import sharpness_score

        # Use a large image so that border artifacts from FIND_EDGES are a tiny
        # fraction of the total pixel count (the filter kernel clips at edges,
        # producing a border ring of non-zero values even for flat images).
        flat = str(tmp_path / "flat.png")
        Image.new("RGB", (512, 512), color=(100, 100, 100)).save(flat)

        # A high-contrast image (checkerboard) should score substantially higher.
        contrast = str(tmp_path / "contrast.png")
        img = Image.new("RGB", (512, 512), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        for x in range(0, 512, 2):
            draw.line([(x, 0), (x, 511)], fill=(255, 255, 255), width=1)
        img.save(contrast)

        flat_score = sharpness_score(flat)
        contrast_score = sharpness_score(contrast)

        # The high-contrast image must score meaningfully higher than the flat one.
        assert contrast_score > flat_score * 10, (
            f"Expected contrast ({contrast_score:.1f}) >> flat ({flat_score:.1f})"
        )

    def test_high_contrast_image_has_higher_sharpness(self, tmp_path):
        from PIL import Image, ImageDraw
        from app.services.postprocess.scoring import sharpness_score

        # Use PNG (lossless) so JPEG artifacts don't inflate the flat baseline
        sharp_path = str(tmp_path / "sharp.png")
        img = Image.new("RGB", (128, 128), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Alternate black/white stripes — maximises edge density
        for x in range(0, 128, 2):
            draw.line([(x, 0), (x, 127)], fill=(255, 255, 255), width=1)
        img.save(sharp_path)

        flat_path = str(tmp_path / "flat2.png")
        Image.new("RGB", (128, 128), color=(128, 128, 128)).save(flat_path)

        assert sharpness_score(sharp_path) > sharpness_score(flat_path)


class TestBrightness:
    def test_black_image_near_zero(self, tmp_path):
        from PIL import Image
        from app.services.postprocess.scoring import brightness

        p = str(tmp_path / "black.jpg")
        Image.new("RGB", (64, 64), color=(0, 0, 0)).save(p)
        assert brightness(p) < 5.0

    def test_white_image_near_255(self, tmp_path):
        from PIL import Image
        from app.services.postprocess.scoring import brightness

        p = str(tmp_path / "white.jpg")
        Image.new("RGB", (64, 64), color=(255, 255, 255)).save(p)
        assert brightness(p) > 250.0

    def test_returns_float(self, tmp_path):
        from PIL import Image
        from app.services.postprocess.scoring import brightness

        p = str(tmp_path / "mid.jpg")
        Image.new("RGB", (64, 64), color=(128, 128, 128)).save(p)
        assert isinstance(brightness(p), float)


class TestDominantColor:
    def test_returns_hex_string(self, tmp_path):
        from PIL import Image
        from app.services.postprocess.scoring import dominant_color

        p = str(tmp_path / "red.jpg")
        Image.new("RGB", (64, 64), color=(200, 10, 10)).save(p)
        result = dominant_color(p)
        assert result.startswith("#")
        assert len(result) == 7

    def test_all_red_image_gives_reddish_color(self, tmp_path):
        from PIL import Image
        from app.services.postprocess.scoring import dominant_color

        p = str(tmp_path / "red2.jpg")
        Image.new("RGB", (64, 64), color=(255, 0, 0)).save(p)
        color = dominant_color(p)
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        # Red channel should dominate
        assert r > g and r > b


class TestPlaceholderDetector:
    def test_detect_faces_returns_none(self, tmp_path):
        from PIL import Image
        from app.services.postprocess.scoring import PlaceholderDetector

        p = str(tmp_path / "face.jpg")
        Image.new("RGB", (64, 64), color=(255, 200, 180)).save(p)
        assert PlaceholderDetector.detect_faces(p) is None

    def test_detect_objects_returns_empty_list(self, tmp_path):
        from PIL import Image
        from app.services.postprocess.scoring import PlaceholderDetector

        p = str(tmp_path / "obj.jpg")
        Image.new("RGB", (64, 64), color=(100, 100, 100)).save(p)
        result = PlaceholderDetector.detect_objects(p)
        assert isinstance(result, list)
        assert len(result) == 0


# ── ThumbnailService unit tests (mocked repo + render) ───────────────────────

def _make_repo() -> MagicMock:
    repo = MagicMock()
    repo._db = AsyncMock()
    return repo


def _make_render(has_output: bool = True, is_completed: bool = True, video_path: str = "/tmp/fake.mp4") -> MagicMock:
    render = MagicMock()
    render.id = "render-abc"
    render.status = "completed" if is_completed else "running"
    render.render_output = {"local_path": video_path} if has_output else {}
    render.timeline_id = None
    render.voice_id = None
    return render


class TestThumbnailServiceStartThumbnail:
    @pytest.mark.asyncio
    async def test_raises_if_render_not_found(self):
        from app.services.thumbnail_service import ThumbnailService
        from app.schemas.thumbnail import ThumbnailRequest

        repo = _make_repo()
        render_repo = MagicMock()
        render_repo.get = AsyncMock(return_value=None)

        service = ThumbnailService(repo, render_repo=render_repo)
        with pytest.raises(ValueError, match="not found"):
            await service.start_thumbnail(ThumbnailRequest(render_id="missing"))

    @pytest.mark.asyncio
    async def test_raises_if_render_not_completed(self):
        from app.services.thumbnail_service import ThumbnailService
        from app.schemas.thumbnail import ThumbnailRequest

        repo = _make_repo()
        render_repo = MagicMock()
        render_repo.get = AsyncMock(return_value=_make_render(is_completed=False))

        service = ThumbnailService(repo, render_repo=render_repo)
        with pytest.raises(ValueError, match="not completed"):
            await service.start_thumbnail(ThumbnailRequest(render_id="render-abc"))

    @pytest.mark.asyncio
    async def test_raises_if_no_output_file(self):
        from app.services.thumbnail_service import ThumbnailService
        from app.schemas.thumbnail import ThumbnailRequest

        repo = _make_repo()
        render_repo = MagicMock()
        render_repo.get = AsyncMock(return_value=_make_render(has_output=False))

        service = ThumbnailService(repo, render_repo=render_repo)
        with pytest.raises(ValueError, match="no output file"):
            await service.start_thumbnail(ThumbnailRequest(render_id="render-abc"))

    @pytest.mark.asyncio
    async def test_creates_db_record_on_valid_render(self):
        from app.services.thumbnail_service import ThumbnailService
        from app.schemas.thumbnail import ThumbnailRequest

        repo = _make_repo()
        render_repo = MagicMock()
        render_repo.get = AsyncMock(return_value=_make_render())

        created_thumbnail = MagicMock()
        created_thumbnail.id = "thumb-1"
        repo.create = AsyncMock(return_value=created_thumbnail)

        service = ThumbnailService(repo, render_repo=render_repo)
        with patch("app.tasks.thumbnail_tasks.run_thumbnail_task") as mock_task:
            mock_task.delay = MagicMock()
            result = await service.start_thumbnail(ThumbnailRequest(render_id="render-abc"))

        assert result.id == "thumb-1"
        repo.create.assert_awaited_once()


class TestThumbnailServiceListDelete:
    @pytest.mark.asyncio
    async def test_list_delegates_to_repo(self):
        from app.services.thumbnail_service import ThumbnailService

        repo = _make_repo()
        repo.list = AsyncMock(return_value=([], 0))

        service = ThumbnailService(repo)
        result, total = await service.list_thumbnails(limit=10, offset=0)
        assert result == []
        assert total == 0
        repo.list.assert_awaited_once_with(limit=10, offset=0)

    @pytest.mark.asyncio
    async def test_delete_removes_candidate_files(self, tmp_path):
        from app.services.thumbnail_service import ThumbnailService

        candidate_path = str(tmp_path / "candidate.jpg")
        from PIL import Image
        Image.new("RGB", (10, 10)).save(candidate_path)

        repo = _make_repo()
        thumbnail = MagicMock()
        thumbnail.candidates = [{"candidate_id": "c0", "path": candidate_path}]
        repo.get = AsyncMock(return_value=thumbnail)
        repo.delete = AsyncMock(return_value=True)

        service = ThumbnailService(repo)
        result = await service.delete_thumbnail("thumb-1")

        assert result is True
        # File should be removed
        import os
        assert not os.path.isfile(candidate_path)
