import unittest

from sqlalchemy import text

from app.db.session import SessionLocal
from course_tests.common import TestUsers, assert_status_not_500, auth_headers, client


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.user = TestUsers.register_and_login(role="client")
        cls.moderator = TestUsers.ensure_moderator()

    def test_db_and_openapi(self):
        with SessionLocal() as db:
            ping = db.execute(text("select 1")).scalar_one()
        self.assertEqual(ping, 1)

        resp = client.get("/openapi.json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("paths", resp.json())

    def test_api_feed_returns_list(self):
        resp = client.get(
            "/api/v1/posts/feed",
            headers=auth_headers(self.user.token),
            params={"limit": 5, "offset": 0},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_catalogs_styles_and_tags(self):
        styles = client.get("/api/v1/catalogs/styles", headers=auth_headers(self.user.token))
        tags = client.get("/api/v1/catalogs/tags", headers=auth_headers(self.user.token))

        self.assertEqual(styles.status_code, 200)
        self.assertEqual(tags.status_code, 200)
        self.assertGreaterEqual(len(styles.json()), 3)
        self.assertGreaterEqual(len(tags.json()), 3)

    def test_moderation_export_csv_xlsx(self):
        csv_resp = client.get(
            "/api/v1/moderation/stats/export.csv",
            headers=auth_headers(self.moderator.token),
        )
        xlsx_resp = client.get(
            "/api/v1/moderation/stats/export.xlsx",
            headers=auth_headers(self.moderator.token),
        )

        self.assertEqual(csv_resp.status_code, 200)
        self.assertIn("metric", csv_resp.text)

        self.assertEqual(xlsx_resp.status_code, 200)
        self.assertGreater(len(xlsx_resp.content), 100)

    def test_unknown_api_route_not_500(self):
        resp = client.get("/api/v1/unknown-route")
        assert_status_not_500(resp.status_code)
        self.assertIn(resp.status_code, {401, 404, 405})


if __name__ == "__main__":
    unittest.main(verbosity=2)
