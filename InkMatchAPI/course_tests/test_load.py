import csv
import json
import statistics
import time
import unittest
from pathlib import Path

from course_tests.common import TestUsers, auth_headers, client


class LoadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.user = TestUsers.register_and_login(role="client")

    def test_api_under_batch_load(self):
        endpoints = [
            ("/api/v1/posts/feed", {"limit": 10, "offset": 0}),
            ("/api/v1/catalogs/styles", None),
            ("/api/v1/profiles/masters", {"limit": 10, "offset": 0}),
            ("/api/v1/collections", {"owner_id": self.user.user_id}),
            ("/api/v1/notifications", {"limit": 20, "offset": 0}),
        ]

        iterations = 30
        latencies_ms: list[float] = []
        endpoint_metrics: dict[str, list[float]] = {endpoint: [] for endpoint, _ in endpoints}
        total_requests = 0
        started_all = time.perf_counter()

        for _ in range(iterations):
            for endpoint, params in endpoints:
                started = time.perf_counter()
                resp = client.get(endpoint, headers=auth_headers(self.user.token), params=params)
                elapsed = (time.perf_counter() - started) * 1000
                latencies_ms.append(elapsed)
                endpoint_metrics[endpoint].append(elapsed)
                total_requests += 1

                self.assertLess(resp.status_code, 500, f"500 on {endpoint}")

        total_time = time.perf_counter() - started_all
        avg = statistics.fmean(latencies_ms)
        p95 = sorted(latencies_ms)[int(len(latencies_ms) * 0.95) - 1]
        req_per_second = total_requests / total_time if total_time > 0 else 0.0

        self.assertGreater(total_requests, 0)
        self.assertLess(avg, 1500.0)
        self.assertLess(p95, 2500.0)

        reports_dir = Path(__file__).resolve().parent / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        summary_path = reports_dir / "load_metrics_summary.json"
        summary_payload = {
            "total_requests": total_requests,
            "total_time_sec": round(total_time, 3),
            "requests_per_second": round(req_per_second, 3),
            "avg_ms": round(avg, 3),
            "p95_ms": round(p95, 3),
            "max_ms": round(max(latencies_ms), 3),
            "per_endpoint": {
                endpoint: {
                    "count": len(values),
                    "avg_ms": round(statistics.fmean(values), 3),
                    "p95_ms": round(sorted(values)[int(len(values) * 0.95) - 1], 3),
                    "max_ms": round(max(values), 3),
                }
                for endpoint, values in endpoint_metrics.items()
            },
        }
        summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        csv_path = reports_dir / "load_metrics_per_endpoint.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["endpoint", "count", "avg_ms", "p95_ms", "max_ms"])
            for endpoint, values in endpoint_metrics.items():
                writer.writerow(
                    [
                        endpoint,
                        len(values),
                        round(statistics.fmean(values), 3),
                        round(sorted(values)[int(len(values) * 0.95) - 1], 3),
                        round(max(values), 3),
                    ]
                )

        print(
            f"\nLOAD SUMMARY: total={total_requests}, avg_ms={avg:.2f}, "
            f"p95_ms={p95:.2f}, max_ms={max(latencies_ms):.2f}, rps={req_per_second:.2f}"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
