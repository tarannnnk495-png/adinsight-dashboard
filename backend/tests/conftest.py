import os
import requests
import pytest


def _load_base_url() -> str:
    env_url = os.environ.get("REACT_APP_BACKEND_URL")
    if env_url:
        return env_url.rstrip("/")

    frontend_env = "/app/frontend/.env"
    if os.path.exists(frontend_env):
        with open(frontend_env, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")

    pytest.skip("REACT_APP_BACKEND_URL is not configured")


BASE_URL = _load_base_url()


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    session.timeout = 60
    return session
