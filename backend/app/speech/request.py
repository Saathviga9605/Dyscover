from pydantic import BaseModel, Field

from .schemas import ReadingTask, Transcript


class ReadingAnalysisRequest(BaseModel):
    task: ReadingTask
    transcript: Transcript | None = None
    duration_ms: int | None = Field(default=None, ge=0)
