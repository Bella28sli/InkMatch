import unittest
from uuid import UUID

from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.models.enums import ModerationQueueEntityType, UserRole
from app.models.moderation import ModerationQueueItem
from app.schemas.auth import RegisterIn
from course_tests.common import TestUsers, auth_headers, client, random_title


class BusinessLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.moderator = TestUsers.ensure_moderator()

    def test_master_registration_creates_base_collections(self):
        master = TestUsers.register_and_login(role="master")

        resp = client.get(
            "/api/v1/collections",
            params={"owner_id": master.user_id, "section": "master"},
            headers=auth_headers(master.token),
        )
        self.assertEqual(resp.status_code, 200)
        items = resp.json()
        kinds = {item["collection_type"] for item in items}
        self.assertTrue({"portfolio", "process", "materials", "find_us"}.issubset(kinds))

    def test_client_registration_creates_system_collections(self):
        user = TestUsers.register_and_login(role="client")
        resp = client.get(
            "/api/v1/collections",
            params={"owner_id": user.user_id},
            headers=auth_headers(user.token),
        )
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()
        self.assertTrue(any(row["collection_type"] == "likes" for row in rows))
        self.assertTrue(any(row["is_system"] and row["is_private"] for row in rows))
        self.assertTrue(any(row["is_system"] and not row["is_private"] for row in rows))

    def test_create_sketch_adds_queue_item(self):
        user = TestUsers.register_and_login(role="client")
        payload = {
            "content_type": "sketch",
            "feed_visibility": "public",
            "title": random_title("sketch"),
            "description": "created in automated test",
            "media_urls": ["http://127.0.0.1:8000/uploads/seed_demo/abstract.jpg"],
            "collection_id": None,
        }
        create_resp = client.post(
            "/api/v1/sketches",
            headers=auth_headers(user.token),
            json=payload,
        )
        self.assertEqual(create_resp.status_code, 201)
        sketch_id = create_resp.json()["id"]

        with SessionLocal() as db:
            queue_row = db.execute(
                select(ModerationQueueItem).where(
                    ModerationQueueItem.entity_type == ModerationQueueEntityType.new_post,
                    ModerationQueueItem.entity_id == UUID(sketch_id),
                )
            ).scalar_one_or_none()
            self.assertIsNotNone(queue_row)


class ValidationTests(unittest.TestCase):
    def test_password_policy_requires_upper_and_lower(self):
        style_ids, tag_ids = TestUsers._ensure_catalog_base()
        with self.assertRaises(ValueError):
            RegisterIn(
                email="validation_test@example.com",
                password="alllowercase1",
                role=UserRole.client.value,
                profile={
                    "nickname": "validator",
                    "avatar_url": None,
                    "bio": None,
                    "home_location_id": None,
                    "default_currency": "RUB",
                },
                preferred_style_ids=style_ids,
                preferred_tag_ids=tag_ids,
                preferences=None,
                master_profile=None,
                workplace=None,
            )


class MigrationTests(unittest.TestCase):
    def test_required_tables_exist(self):
        table_names = [
            "users",
            "profiles",
            "collections",
            "sketches",
            "inkmatch_requests",
            "inkmatches",
            "chats",
            "messages",
            "moderation_queue_items",
            "complaints",
            "notifications",
        ]

        with SessionLocal() as db:
            for table_name in table_names:
                result = db.execute(
                    text("SELECT to_regclass(:table_name)"),
                    {"table_name": table_name},
                ).scalar_one_or_none()
                self.assertEqual(result, table_name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
