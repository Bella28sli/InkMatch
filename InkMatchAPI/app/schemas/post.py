from pydantic import BaseModel, Field


class FeedPostOut(BaseModel):
    id: str
    author_id: str
    author_nickname: str
    image_url: str | None = None
    title: str | None = None
    like_amount: int
    comment_count: int


class PostDetailOut(BaseModel):
    id: str
    author_id: str
    author_nickname: str
    title: str | None = None
    description: str | None = None
    styles: list[dict[str, str]] = []
    tags: list[dict[str, str]] = []
    media_urls: list[str]
    like_amount: int
    comment_count: int
    is_liked: bool
    is_saved: bool


class PostLikeOut(BaseModel):
    is_liked: bool
    like_amount: int


class PostSaveOut(BaseModel):
    is_saved: bool


class PostCommentOut(BaseModel):
    id: str
    author_user_id: str
    author_nickname: str
    parent_comment_id: str | None = None
    body: str
    created_at: str


class PostCommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    parent_comment_id: str | None = None
