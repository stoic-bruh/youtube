"""Media generation Celery tasks (images, voice, video). [PLACEHOLDER]"""
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, name="media.generate_image", max_retries=2)
def generate_image(self, prompt: str, scene_index: int, style: str = "cinematic") -> dict:
    """Generate a scene image from a prompt. [PLACEHOLDER]
    TODO: Implement using ImageGenerator.generate_for_scene().
    """
    return {"scene_index": scene_index, "local_path": "", "url": "", "provider": "placeholder"}


@celery_app.task(bind=True, name="media.generate_voice", max_retries=2)
def generate_voice(self, text: str, voice_id: str = "alloy") -> dict:
    """Generate voice audio from text. [PLACEHOLDER]
    TODO: Implement using VoiceGenerator.generate_narration().
    """
    return {"local_path": "", "duration_seconds": 0, "provider": "placeholder"}


@celery_app.task(bind=True, name="media.compose_video", max_retries=1)
def compose_video(self, scene_plan: dict, images: list[dict], narration: dict) -> dict:
    """Compose final video from scenes, images, and narration. [PLACEHOLDER]
    TODO: Implement using VideoEditor.compose_video() with MoviePy.
    """
    return {"local_path": "", "duration_seconds": 0, "format": "mp4"}


@celery_app.task(bind=True, name="media.generate_subtitles", max_retries=2)
def generate_subtitles(self, audio_path: str, language: str = "en") -> dict:
    """Generate subtitles from audio via Whisper. [PLACEHOLDER]
    TODO: Implement using SubtitleGenerator.generate_from_audio().
    """
    return {"entries": [], "language": language, "format": "srt"}


@celery_app.task(bind=True, name="media.generate_thumbnail", max_retries=2)
def generate_thumbnail(self, script: dict, research: dict) -> dict:
    """Generate thumbnail variants. [PLACEHOLDER]
    TODO: Implement using ThumbnailGenerator.generate().
    """
    return {"thumbnails": [], "selected": None}
