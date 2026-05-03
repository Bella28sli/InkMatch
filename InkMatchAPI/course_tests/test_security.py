import unittest

from sqlalchemy import select

from app.core.security import verify_password
from app.db.session import SessionLocal
from app.models.user import User
from course_tests.common import TestUsers, assert_status_not_500, auth_headers, client


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.user = TestUsers.register_and_login(role="client")
        cls.moderator = TestUsers.ensure_moderator()

    def test_passwords_are_hashed(self):
        with SessionLocal() as db:
            row = db.execute(select(User).where(User.email == self.user.email)).scalar_one()
            self.assertNotEqual(row.password_hash, self.user.password)
            self.assertTrue(verify_password(self.user.password, row.password_hash))

    def test_sql_injection_login_fails(self):
        payload = {"login": "' OR 1=1 --", "password": "' OR 1=1 --"}
        resp = client.post("/api/v1/auth/login", json=payload)
        self.assertIn(resp.status_code, {401, 403})

    def test_sql_injection_in_feed_query_no_server_error(self):
        injection = "' union select * from users --"
        resp = client.get(
            "/api/v1/posts/feed",
            headers=auth_headers(self.user.token),
            params={"q": injection, "limit": 5},
        )
        assert_status_not_500(resp.status_code)

    def test_client_cannot_access_moderation_queue(self):
        resp = client.get("/api/v1/moderation/queue", headers=auth_headers(self.user.token))
        self.assertEqual(resp.status_code, 403)

    def test_moderator_can_access_moderation_queue(self):
        resp = client.get("/api/v1/moderation/queue", headers=auth_headers(self.moderator.token))
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_protected_endpoint_requires_auth(self):
        resp = client.get("/api/v1/posts/feed")
        self.assertIn(resp.status_code, {401, 403})


if __name__ == "__main__":
    unittest.main(verbosity=2)
