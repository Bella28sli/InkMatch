from pydantic import BaseModel


class TasteSliceOut(BaseModel):
    label: str
    count: int
    share_percent: float


class PopularityPointOut(BaseModel):
    date: str
    likes: int
    views: int
    comments: int


class ActivityStatsOut(BaseModel):
    range_days: int
    role: str
    taste_styles: list[TasteSliceOut]
    taste_tags: list[TasteSliceOut]
    time_minutes: int
    sessions: int
    active_days: int
    popularity: list[PopularityPointOut]
    extra: dict[str, float]
