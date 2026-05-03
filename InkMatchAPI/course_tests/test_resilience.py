import io
import unittest

from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.sketches import Style
from app.models.user import User
from course_tests.common import TestUsers, auth_headers, client, random_title


class ResilienceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.user = TestUsers.register_and_login(role="client")

    def test_duplicate_registration_returns_conflict_and_no_duplicates(self):
        style_ids, tag_ids = TestUsers._ensure_catalog_base()
        email = f"dup_{random_title('mail')}@example.com"

        payload = {
            "email": email,
            "password": "Aa123456",
            "role": "client",
            "profile": {
                "nickname": random_title("nick"),
                "avatar_url": None,
                "bio": "dup test",
                "home_location_id": None,
                "default_currency": "RUB",
            },
            "preferred_style_ids": style_ids,
            "preferred_tag_ids": tag_ids,
            "preferences": None,
            "master_profile": None,
            "workplace": None,
        }

        first = client.post("/api/v1/auth/register", json=payload)
        second = client.post("/api/v1/auth/register", json=payload)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)

        with SessionLocal() as db:
            count = db.execute(select(User).where(User.email == email)).scalars().all()
        self.assertEqual(len(count), 1)

    def test_collection_title_validation(self):
        resp = client.post(
            "/api/v1/collections",
            headers=auth_headers(self.user.token),
            json={
                "title": " ",
                "description": "empty title should fail",
                "collection_type": "custom",
                "is_private": False,
            },
        )
        self.assertEqual(resp.status_code, 400)

    def test_media_upload_invalid_type_returns_400(self):
        files = {"file": ("malicious.txt", io.BytesIO(b"not-image"), "text/plain")}
        resp = client.post(
            "/api/v1/sketches/upload-media",
            headers=auth_headers(self.user.token),
            files=files,
        )
        self.assertEqual(resp.status_code, 400)

    def test_atomic_rollback_on_error(self):
        unique_name = f"rollback_{random_title('style')}"

        with SessionLocal() as db:
            before = db.execute(select(Style).where(Style.name == unique_name)).scalars().all()
            self.assertEqual(len(before), 0)

        with SessionLocal() as db:
            try:
                with db.begin():
                    db.add(Style(name=unique_name, description="before-error"))
                    raise RuntimeError("force rollback")
            except RuntimeError:
                pass

        with SessionLocal() as db:
            after = db.execute(select(Style).where(Style.name == unique_name)).scalars().all()
            self.assertEqual(len(after), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
