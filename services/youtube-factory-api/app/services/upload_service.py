"""UploadService — placeholder interface.

Responsible for:
- Authenticating with YouTube Data API v3
- Uploading video files with resumable upload protocol
- Setting metadata (title, description, tags, thumbnail)
- Managing upload status and progress tracking
- Handling quota limits and retry logic
"""
from dataclasses import dataclass

from app.services.video_editor import VideoOutput
from app.services.thumbnail_generator import Thumbnail
from app.services.seo_generator import SEOPackage


@dataclass
class UploadResult:
    youtube_id: str
    youtube_url: str
    status: str  # uploaded | processing | live | failed
    upload_progress: float = 1.0  # 0.0 – 1.0
    processing_progress: float = 0.0
    error: str | None = None


class UploadService:
    """Placeholder implementation — real YouTube upload to be implemented."""

    async def upload_video(
        self,
        video: VideoOutput,
        seo_package: SEOPackage,
        thumbnail: Thumbnail | None = None,
        privacy: str = "private",
        made_for_kids: bool = False,
    ) -> UploadResult:
        """Upload a video to YouTube with full metadata.

        Args:
            video: VideoOutput to upload.
            seo_package: SEOPackage with title, description, tags.
            thumbnail: Optional Thumbnail to set.
            privacy: "private" | "unlisted" | "public".
            made_for_kids: YouTube COPPA flag.

        Returns:
            UploadResult with youtube_id and url.
        """
        # TODO: Implement using google-auth + googleapiclient:
        #   1. Build youtube service client with credentials
        #   2. Create media body from video.local_path
        #   3. Call videos.insert() with resumable=True
        #   4. Poll for upload completion
        #   5. Set thumbnail via thumbnails.set()
        return UploadResult(
            youtube_id="placeholder_video_id",
            youtube_url="https://youtube.com/watch?v=placeholder_video_id",
            status="uploaded",
        )

    async def set_thumbnail(self, youtube_id: str, thumbnail: Thumbnail) -> bool:
        """Set a custom thumbnail for an uploaded video.

        Args:
            youtube_id: YouTube video ID.
            thumbnail: Thumbnail to upload and set.

        Returns:
            True if successful.
        """
        # TODO: Implement using YouTube Data API thumbnails.set()
        return True

    async def update_metadata(
        self,
        youtube_id: str,
        title: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> bool:
        """Update metadata on an existing YouTube video.

        Args:
            youtube_id: YouTube video ID.
            title: New title (optional).
            description: New description (optional).
            tags: New tag list (optional).

        Returns:
            True if successful.
        """
        # TODO: Implement using YouTube Data API videos.update()
        return True

    async def get_upload_status(self, youtube_id: str) -> UploadResult:
        """Check the processing status of an uploaded video.

        Args:
            youtube_id: YouTube video ID.

        Returns:
            UploadResult with current status.
        """
        # TODO: Implement using YouTube Data API videos.list() with status part
        return UploadResult(
            youtube_id=youtube_id,
            youtube_url=f"https://youtube.com/watch?v={youtube_id}",
            status="processing",
            processing_progress=0.5,
        )
