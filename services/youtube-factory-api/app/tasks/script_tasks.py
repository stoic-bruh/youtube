"""Script generation Celery tasks. [PLACEHOLDER]"""
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, name="script.generate", max_retries=3)
def generate_script(self, research_result: dict, style: str = "educational") -> dict:
    """Generate a video script from research data. [PLACEHOLDER]
    TODO: Implement using ScriptService.generate_script().
    """
    return {"title": "placeholder", "hook": "", "body": "", "call_to_action": ""}


@celery_app.task(bind=True, name="script.improve", max_retries=2)
def improve_script(self, script: dict, feedback: str) -> dict:
    """Improve an existing script based on feedback. [PLACEHOLDER]
    TODO: Implement using ScriptService.improve_script().
    """
    return script
