import io
import os
from typing import Any, Literal

import pytest
import requests
from requests.cookies import RequestsCookieJar

from jeoparty.api.config import get_question_pack_data_path
from tests.config import PRESENTER_USER_ID, PRESENTER_USERNAME, PRESENTER_PASSWORD

BASE_URL = "http://localhost:5006/jeoparty/api"

def make_request(
    method: Literal["GET", "POST"],
    endpoint: str,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    cookies: dict[str, Any] | RequestsCookieJar | None = None,
    files: dict[str, Any] | None = None,
):
    return requests.request(method, f"{BASE_URL}/{endpoint}", params=params, data=data, json=json, cookies=cookies, files=files)

def test_auth(database):
    # Test login failure with missing data
    data = {"user": PRESENTER_USERNAME}
    response = make_request("POST", "login", json=data)

    assert response.status_code == 400
    assert response.json() == {"response": "Could not login: Username or Password was not given."}
    assert "jeoparty_token" not in response.cookies

    # Test login failure with wrong password
    data = {"user": PRESENTER_USERNAME, "pass": "wrong_pass"}
    response = make_request("POST", "login", json=data)

    assert response.status_code == 401
    assert response.json() == {"response": "Could not login: Username or Password does not match."}
    assert "jeoparty_token" not in response.cookies

    # Test successful login
    data = {"user": PRESENTER_USERNAME, "pass": PRESENTER_PASSWORD}
    response = make_request("POST", "login", json=data)
    cookies = response.cookies

    assert response.status_code == 200
    assert response.json() == {"user_id": PRESENTER_USER_ID, "user_name": PRESENTER_USERNAME}
    assert "jeoparty_token" in cookies

    # Test 'me' endpoint
    response = make_request("GET", "me", cookies=cookies)

    assert response.status_code == 200
    assert response.json() == {"user_id": PRESENTER_USER_ID, "user_name": PRESENTER_USERNAME}

    # Test 'logout' endpoint
    response = make_request("POST", "logout", cookies=cookies)

    assert response.status_code == 200
    assert response.json() == {"response": "You have been successfully logged out."}

def _login():
    data = {"user": PRESENTER_USERNAME, "pass": PRESENTER_PASSWORD}
    response = make_request("POST", "login", json=data)
    assert response.status_code == 200

    return response.cookies

# Mirrors what the HTML form sends: checkboxes are 'on' when checked and omitted otherwise
_VALID_PACK_DATA = {
    "name": "New Pack",
    "include_finale": "on",
    "language": "danish",
    "theme_id": "none",
}

def test_dashboard_create_pack(database):
    packs_before = len(database.get_question_packs_for_user(PRESENTER_USER_ID))

    # Test failure when not logged in
    response = make_request("POST", "packs", data=_VALID_PACK_DATA)

    assert response.status_code == 401
    assert response.json() == {"response": "You are authorized to access this. Please log in first."}

    cookies = _login()

    # Test failure with invalid pack names
    invalid_names = [
        (None, "'Name' - Field required"),
        ("ab", "'Name' should have at least 3 characters"),
        ("a" * 65, "'Name' should have at most 64 characters"),
        ("Bad <Pack>", "'Name' contains invalid characters"),
    ]
    for name, error in invalid_names:
        data = dict(_VALID_PACK_DATA)
        if name is None:
            del data["name"]
        else:
            data["name"] = name

        response = make_request("POST", "packs", data=data, cookies=cookies)

        assert response.status_code == 400, name
        assert response.json() == {"response": f"Error when creating question pack: {error}"}

    # Test failure with invalid boolean value
    data = {**_VALID_PACK_DATA, "public": "maybe"}
    response = make_request("POST", "packs", data=data, cookies=cookies)

    assert response.status_code == 400
    assert response.json() == {
        "response": "Error when creating question pack: 'Public' - Input should be a valid boolean, unable to interpret input"
    }

    # Test failure with invalid language
    data = {**_VALID_PACK_DATA, "language": "klingon"}
    response = make_request("POST", "packs", data=data, cookies=cookies)
    
    assert response.status_code == 400
    assert response.json() == {
        "response": "Error when creating question pack: 'language' - Input is not a valid choice"
    }

    # Test failure with nonexistent theme
    data = {**_VALID_PACK_DATA, "theme_id": "nonexistent_theme"}
    response = make_request("POST", "packs", data=data, cookies=cookies)

    assert response.status_code == 400
    assert response.json() == {
        "response": "Error when creating question pack: 'theme_id' - Input does not refer to a valid theme"
    }

    # Test failure with invalid lobby music file type
    files = {"music": ("song.txt", io.BytesIO(b"not music"))}
    response = make_request("POST", "packs", data=_VALID_PACK_DATA, cookies=cookies, files=files)

    assert response.status_code == 400
    assert response.json() == {
        "response": "Could not validate question file 'song.txt': File is not a valid type (must be one of: ['mp3', 'wav'])"
    }

    # None of the failed requests should have created a pack
    assert len(database.get_question_packs_for_user(PRESENTER_USER_ID)) == packs_before

    # Test success without theme_id
    data = {k: v for k, v in _VALID_PACK_DATA.items() if k != "theme_id"}
    response = make_request("POST", "packs", data=data, cookies=cookies)

    assert response.status_code == 200

    pack_json = response.json()

    assert pack_json["name"] == "New Pack"
    assert pack_json["public"] is False
    assert pack_json["include_finale"] is True
    assert pack_json["language"] == "danish"
    assert pack_json["lobby_music"] is None
    assert pack_json["created_by"] == PRESENTER_USER_ID

    # Test successful case without lobby music
    response = make_request("POST", "packs", data=_VALID_PACK_DATA, cookies=cookies)

    assert response.status_code == 200

    pack_json = response.json()

    assert pack_json["name"] == "New Pack"
    assert pack_json["public"] is False
    assert pack_json["include_finale"] is True
    assert pack_json["language"] == "danish"
    assert pack_json["lobby_music"] is None
    assert pack_json["created_by"] == PRESENTER_USER_ID

    pack_model = database.get_question_packs_for_user(PRESENTER_USER_ID, pack_json["id"])

    assert pack_model is not None
    assert pack_model.theme_id is None
    assert pack_model.dump() == pack_json
    assert os.path.isdir(get_question_pack_data_path(pack_json["id"]))

    # Test successful case with lobby music and public pack
    data = {**_VALID_PACK_DATA, "name": "Musical Pack", "public": "on"}
    files = {"music": ("song.mp3", io.BytesIO(b"fake mp3 data"))}
    response = make_request("POST", "packs", data=data, cookies=cookies, files=files)

    assert response.status_code == 200

    pack_json = response.json()
    music_path = os.path.join(get_question_pack_data_path(pack_json["id"]), "lobby_music.mp3")

    assert pack_json["name"] == "Musical Pack"
    assert pack_json["public"] is True
    assert pack_json["lobby_music"] == f"{get_question_pack_data_path(pack_json['id'], False)}/lobby_music.mp3"
    assert os.path.isfile(music_path)

    with open(music_path, "rb") as fp:
        assert fp.read() == b"fake mp3 data"

    assert len(database.get_question_packs_for_user(PRESENTER_USER_ID)) == packs_before + 3
