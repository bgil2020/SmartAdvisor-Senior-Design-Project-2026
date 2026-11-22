from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from backend.api import SpaStaticFiles, configured_cors_origins


def test_cors_configuration_allows_only_exact_configured_origin():
    allowed = "https://smartadvisor.example"
    probe = FastAPI()
    probe.add_middleware(
        CORSMiddleware,
        allow_origins=configured_cors_origins(f" {allowed}, "),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @probe.get("/probe")
    def read_probe():
        return {"ok": True}

    client = TestClient(probe)
    accepted = client.options(
        "/probe",
        headers={"Origin": allowed, "Access-Control-Request-Method": "GET"},
    )
    rejected = client.options(
        "/probe",
        headers={"Origin": "https://preview.smartadvisor.example", "Access-Control-Request-Method": "GET"},
    )

    assert accepted.status_code == 200
    assert accepted.headers["access-control-allow-origin"] == allowed
    assert "access-control-allow-origin" not in rejected.headers


def test_spa_fallback_preserves_assets_and_api_precedence(tmp_path: Path):
    (tmp_path / "index.html").write_text('<div id="root"></div>', encoding="utf-8")
    (tmp_path / "asset.js").write_text("window.ready = true", encoding="utf-8")
    probe = FastAPI()

    @probe.get("/courses")
    def courses():
        return {"count": 1}

    probe.mount("/", SpaStaticFiles(directory=tmp_path, html=True), name="frontend")
    client = TestClient(probe)

    assert client.get("/forms").text == '<div id="root"></div>'
    assert client.get("/chatbot").text == '<div id="root"></div>'
    assert client.get("/asset.js").text == "window.ready = true"
    assert client.get("/courses").json() == {"count": 1}
    unknown_api = client.get("/api/unknown-release-probe")
    assert unknown_api.status_code == 404
    assert unknown_api.headers["content-type"].startswith("application/json")
    assert client.get("/missing.js").status_code == 404


def test_vercel_configuration_has_spa_fallback():
    config = (Path(__file__).parents[1] / "frontend" / "vercel.json").read_text(encoding="utf-8")
    assert '"source": "/(.*)"' in config
    assert '"destination": "/index.html"' in config


def test_dockerfile_normalizes_linux_entrypoint_line_endings():
    dockerfile = (Path(__file__).parents[1] / "Dockerfile").read_text(encoding="utf-8")
    assert "sed -i 's/\\r$//' /app/scripts/container-entrypoint.sh" in dockerfile
    assert "! grep -q \"$(printf '\\r')\" /app/scripts/container-entrypoint.sh" in dockerfile
