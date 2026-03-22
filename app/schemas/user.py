from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class UserOut(BaseModel):
    id: UUID
    email: str
    name: str
    role: str
    status: str
    language: str
    theme: str
    model_config = {"from_attributes": True}

class UserStatusUpdate(BaseModel):
    status: str
