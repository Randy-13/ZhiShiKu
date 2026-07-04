from fastapi import FastAPI
from fastapi.testclient import TestClient

import app as legacy_app
from src.main import create_app


def test_create_app_returns_fastapi_instance():
    created = create_app()

    assert isinstance(created, FastAPI)


def test_create_app_exposes_existing_health_endpoint():
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_legacy_app_directly_serves_workspace_routes():
    client = TestClient(legacy_app.app)

    for route in ["/collect", "/learn", "/mine", "/create", "/library", "/settings", "/docs"]:
        response = client.get(route)
        assert response.status_code == 200
        assert '<div id="root"></div>' in response.text
        assert '/frontend/assets/' in response.text
