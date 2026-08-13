from pydantic import BaseModel


class StepBase(BaseModel):
    type: str
    sleep: float = 0.3
