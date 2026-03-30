from pydantic import BaseModel


class FeedbackResponse(BaseModel):
    status: str
