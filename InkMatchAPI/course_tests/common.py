from __future__ import annotations

import random
import string
from dataclasses import dataclass
from typing import Iterable
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.enums import UserRole
from app.models.sketches import Style, Tag
from app.models.user import User


client = TestClient(app)


@dataclass
class AuthBundle:
    email: str
    password: str
    token: str
    refresh_token: str
    user_id: str


class TestUsers:
    password_default = "Aa123456"

    @staticmethod
    def _rand(prefix: str) -> str:
        tail = uuid4().hex[:10]
        return f"{prefix}_{tail}"

    @staticmethod
    def _ensure_catalog_base() -> tuple[list[str], list[str]]:
        with SessionLocal() as db:
            styles = db.execute(select(Style).order_by(Style.name.asc())).scalars().all()
            tags = db.execute(select(Tag).order_by(Tag.name.asc())).scalars().all()

            while len(styles) < 3:
                row = Style(name=f"test_style_{uuid4().hex[:8]}", description="auto")
                db.add(row)
                db.flush()
                styles.append(row)

            while len(tags) < 3:
                row = Tag(name=f"test_tag_{uuid4().hex[:8]}")
                db.add(row)
                db.flush()
                tags.append(row)

            db.commit()
            return [str(s.id) for s in styles[:3]], [str(t.id) for t in tags[:3]]

    @classmethod
    def register_and_login(cls, role: str = "client", password: str | None = None) -> AuthBundle:
        pwd = password or cls.password_default
        email = f"{cls._rand(role)}@example.com"
        nickname = cls._rand("nick")
        style_ids, tag_ids = cls._ensure_catalog_base()

        payload: dict = {
            "email": email,
            "password": pwd,
            "role": role,
            "profile": {
                "nickname": nickname,
                "avatar_url": None,
                "bio": "course test user",
                "home_location_id": None,
                "default_currency": "RUB",
            },
            "preferred_style_ids": style_ids,
            "preferred_tag_ids": tag_ids,
            "preferences": None,
            "master_profile": None,
            "workplace": None,
        }

        if role == UserRole.master.value:
            payload["master_profile"] = {
                "experience_years": 5,
                "price_min": 5000,
                "price_max": 15000,
                "description": "master profile from tests",
            }
            payload["workplace"] = None

        register_resp = client.post("/api/v1/auth/register", json=payload)
        if register_resp.status_code != 201:
            raise AssertionError(f"Register failed: {register_resp.status_code} {register_resp.text}")

        login_resp = client.post(
            "/api/v1/auth/login",
            json={"login": email, "password": pwd},
        )
        if login_resp.status_code != 200:
            raise AssertionError(f"Login failed: {login_resp.status_code} {login_resp.text}")

        token_payload = login_resp.json()
        with SessionLocal() as db:
            user_row = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if not user_row:
                raise AssertionError("User lookup after login failed")

        return AuthBundle(
            email=email,
            password=pwd,
            token=token_payload["access_token"],
            refresh_token=token_payload.get("refresh_token") or "",
            user_id=str(user_row.id),
        )

    @staticmethod
    def ensure_moderator(password: str = "Aa123456") -> AuthBundle:
        email = "moderator_course_tests@example.com"

        with SessionLocal() as db:
            row = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if not row:
                row = User(
                    email=email,
                    phone=None,
                    password_hash=hash_password(password),
                    role=UserRole.moderator,
                    is_verified=True,
                )
                db.add(row)
                db.commit()
                db.refresh(row)

        login_resp = client.post(
            "/api/v1/auth/login",
            json={"login": email, "password": password},
        )
        if login_resp.status_code != 200:
            raise AssertionError(f"Moderator login failed: {login_resp.status_code} {login_resp.text}")

        token_payload = login_resp.json()
        return AuthBundle(
            email=email,
            password=password,
            token=token_payload["access_token"],
            refresh_token=token_payload.get("refresh_token") or "",
            user_id="",
        )


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def random_title(prefix: str = "test") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def random_text(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def assert_status_not_500(status_code: int) -> None:
    if status_code >= 500:
        raise AssertionError(f"Unexpected server error status: {status_code}")


def ensure_collection_id(owner_token: str, owner_id: str) -> str:
    resp = client.get(
        "/api/v1/collections",
        params={"owner_id": owner_id},
        headers=auth_headers(owner_token),
    )
    if resp.status_code != 200:
        raise AssertionError(f"Collections list failed: {resp.status_code} {resp.text}")
    rows = resp.json()
    for row in rows:
        if row.get("title") == "Mои посты":
            return row["id"]
    # fallback by creating a custom one
    created = client.post(
        "/api/v1/collections",
        json={
            "title": random_title("collection"),
            "description": "auto",
            "collection_type": "custom",
            "is_private": False,
        },
        headers=auth_headers(owner_token),
    )
    if created.status_code != 201:
        raise AssertionError(f"Collection create failed: {created.status_code} {created.text}")
    return created.json()["id"]


def first_or_none(items: Iterable[dict]) -> dict | None:
    for item in items:
        return item
    return None
