from typing import Any

import requests

from tests.config import PRESENTER_USERNAME, PRESENTER_PASSWORD

BASE_URL = "http://localhost:5006/jeoparty/api"

def make_request(endpoint: str, data: dict[str, Any] | None = None, json: dict[str, Any] | None = None):
    return requests.post(f"{BASE_URL}/{endpoint}", data, json)


def test_auth(database):
    data = {"user": PRESENTER_USERNAME, "pass": PRESENTER_PASSWORD}
    response = make_request("login", data)

    print(response.json())
    print(response.status_code)
