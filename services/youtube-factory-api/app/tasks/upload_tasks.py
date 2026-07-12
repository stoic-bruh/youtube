"""YouTube upload Celery tasks. [PLACEHOLDER]"""
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, name="upload.upload_video", max_retries=3)
def upload_video(
    self,
    video_path: str,
    seo_package: dict,
    thumbnail_path: str | None = None,
    privacy: str = "private",
) -> dict:
    """Upload video to YouTube. [PLACEHOLDER]
    TODO: Implement using UploadService.upload_video() with google-auth.
    """
    return {"youtube_id": "placeholder", "youtube_url": "", "status": "placeholder"}


@celery_app.task(bind=True, name="upload.set_thumbnail", max_retries=2)
def set_thumbnail(self, youtube_id: str, thumbnail_path: str) -> bool:
    """Set custom thumbnail on YouTube video. [PLACEHOLDER]
    TODO: Implement using YouTube Data API thumbnails.set().
    """
    return False


@celery_app.task(bind=True, name="upload.poll_processing", max_retries=20)
def poll_processing_status(self, youtube_id: str) -> dict:
    """Poll YouTube for video processing status. [PLACEHOLDER]
    TODO: Implement using YouTube Data API videos.list() with status part.
    """
    return {"youtube_id": youtube_id, "status": "processing", "processing_progress": 0.0}
