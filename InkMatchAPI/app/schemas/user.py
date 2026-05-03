from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: str
    email: EmailStr
    phone: str | None = None
    role: str

    class Config:
        from_attributes = True
