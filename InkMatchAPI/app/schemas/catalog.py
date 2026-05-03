from pydantic import BaseModel, Field


class StyleIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=255)


class StyleOut(BaseModel):
    id: str
    name: str
    description: str | None = None


class TagIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class TagOut(BaseModel):
    id: str
    name: str
