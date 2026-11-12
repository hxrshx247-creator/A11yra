"""Measure the seeded audit endpoint with ten local requests from two callers."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median, quantiles
from time import perf_counter
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import DOCX_MIME
from app.main import app


def benchmark():
    sample = Path(__file__).resolve().parents[1] / "fixtures" / "pilot-syllabus.docx"
    contents = sample.read_bytes()
    with TestClient(app) as client:
        credentials = {"email": f"benchmark-{uuid4()}@example.test", "password": uuid4().hex}
        csrf = client.get("/api/auth/csrf").json()["csrf_token"]
        client.headers["X-CSRF-Token"] = csrf
        client.post("/api/auth/signup", json=credentials).raise_for_status()
        profile = client.post("/api/auth/login", json=credentials).raise_for_status().json()
        client.headers["X-CSRF-Token"] = client.cookies["a11yra_csrf"]
        workspace = profile["workspaces"][0]["id"]
        base = f"/api/workspaces/{workspace}"
        client.post(f"{base}/billing/demo", json={"plan": "institution"}).raise_for_status()
        key = client.post(f"{base}/keys", json={"name": "Benchmark"}).raise_for_status().json()["key"]
        file = ("pilot-syllabus.docx", contents, DOCX_MIME)

        def audit(_):
            start = perf_counter()
            response = client.post("/api/public/v1/audit", files={"file": file},
                                   headers={"Authorization": f"Bearer {key}"})
            response.raise_for_status()
            assert response.json()["progress"]["passed"] == 2
            return (perf_counter() - start) * 1000

        start = perf_counter()
        with ThreadPoolExecutor(max_workers=2) as workers:
            times = list(workers.map(audit, range(10)))
        elapsed = perf_counter() - start
        client.request("DELETE", "/api/auth/account",
                       json={"confirm": True, "password": credentials["password"]}).raise_for_status()
    print(f"{len(times)}/10 successful, {len(contents)} bytes per input, "
          f"median {median(times):.1f} ms, p95 {quantiles(times, n=20, method='inclusive')[-1]:.1f} ms, "
          f"batch {elapsed:.3f} s ({len(times) / elapsed:.1f} requests/sec)")


if __name__ == "__main__":
    import os
    from tempfile import TemporaryDirectory

    with TemporaryDirectory(prefix="a11yra-benchmark-") as directory:
        temp = Path(directory)
        os.environ.update(A11YRA_ENV="dev", A11YRA_DATA_DIR=str(temp / "data"),
                          DATABASE_URL=f"sqlite:///{(temp / 'benchmark.db').as_posix()}",
                          STRIPE_TEST_ENABLED="0", SMTP_HOST="")
        benchmark()
