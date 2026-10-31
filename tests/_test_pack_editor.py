"""
Drives PackEditorView against a mocked API. The save mock reproduces how
update_question_pack (api/database.py) treats ids, deletes and new-id positions.
"""
import base64
import json
import re
import sys

from playwright.sync_api import sync_playwright, expect

BASE = "http://localhost:5173"
PACK_ID = "pack1"
SHOTS = sys.argv[1]
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

PACK = {
    "id": PACK_ID, "name": "Test Pack", "public": False, "include_finale": False,
    "language": "english", "theme_id": None, "lobby_music": None, "lobby_volume": None,
    "created_by": "u1", "created_at": "2026-01-01 10:00:00", "changed_at": "2026-01-01 10:00:00",
    "rounds": [
        {"id": "r1", "pack_id": PACK_ID, "name": "Jeoparty!", "round": 1, "categories": [
            {"id": "c1", "round_id": "r1", "name": "Geography", "order": 0, "buzz_time": 10, "bg_image": None,
             "questions": [
                 {"id": "q1", "category_id": "c1", "question": "Capital of France?", "answer": "Paris", "value": 100, "extra": {}},
                 {"id": "q2", "category_id": "c1", "question": "Capital of Spain?", "answer": "Madrid", "value": 200,
                  "extra": {"question_image": "data/packs/pack1/img.png", "height": "default"}},
                 {"id": "q3", "category_id": "c1", "question": "Capital of Italy?", "answer": "Rome", "value": 300,
                  "extra": {"choices": ["Rome", "Milan"]}},
             ]},
        ]},
        # The GET shim's placeholder finale round: no id.
        {"pack_id": PACK_ID, "name": "Triple Jeoparty!", "round": 2, "categories": []},
    ],
}

KNOWN_IDS = {"r1", "c1", "q1", "q2", "q3"}
saves = []
counter = [0]
failures = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def new_id(prefix):
    counter[0] += 1
    new = f"db-{prefix}{counter[0]}"
    KNOWN_IDS.add(new)
    return new


def simulate_save(data):
    """update_question_pack's id handling, including its error on unknown ids."""
    ids = []
    for ri, r in enumerate(data["rounds"]):
        if r.get("deleted"):
            continue
        if "id" in r:
            assert r["id"] in KNOWN_IDS, f"unknown round id {r['id']}"
            rid = r["id"]
        else:
            rid = new_id("r")
            ids.append({"round": ri, "id": rid})
        cats = [c for c in r["categories"] if not c.get("deleted")]
        for ci, c in enumerate(cats):
            if "id" in c:
                assert c["id"] in KNOWN_IDS, f"unknown category id {c['id']}"
                cid = c["id"]
            else:
                cid = new_id("c")
                ids.append({"round": ri, "category": ci, "id": cid, "round_id": rid})
            qs = [q for q in c["questions"] if not q.get("deleted")]
            for qi, q in enumerate(qs):
                if "id" in q:
                    assert q["id"] in KNOWN_IDS, f"unknown question id {q['id']}"
                else:
                    ids.append({"round": ri, "category": ci, "question": qi, "id": new_id("q"),
                                "round_id": rid, "category_id": cid})
    return ids


def parse_multipart(body: bytes):
    text = body.decode("latin-1")
    data = re.search(r'name="data"\r\n\r\n(.*?)\r\n--', text, re.S).group(1)
    files = re.findall(r'name="([^"]+)"; filename="([^"]+)"', text)
    return json.loads(data.encode("latin-1").decode("utf-8")), files


def handle_api(route):
    url = route.request.url
    method = route.request.method
    if url.endswith("/api/me"):
        return route.fulfill(json={"user_id": "u1", "user_name": "tester"})
    if url.endswith("/api/themes"):
        return route.fulfill(json=[{"id": "t1", "name": "Jul", "public": True, "language": "danish",
                                    "bg_image": None, "logo": None, "overlays": []}])
    if url.endswith(f"/api/packs/{PACK_ID}") and method == "GET":
        return route.fulfill(json=json.loads(json.dumps(PACK)))
    if "/api/pack/fetch" in url:
        return route.fulfill(body=PNG, headers={"Content-Type": "image/png"})
    if url.endswith(f"/api/pack/{PACK_ID}/save") and method == "POST":
        data, files = parse_multipart(route.request.post_data_buffer)
        saves.append((data, files))
        try:
            ids = simulate_save(data)
        except AssertionError as exc:
            return route.fulfill(status=500, json={"response": f"mock backend: {exc}"})
        return route.fulfill(json={"response": "Question pack saved successfully.", "ids": ids})
    print("UNHANDLED", method, url)
    return route.fulfill(status=404, json={"response": "not found"})


def all_ids(data):
    for r in data["rounds"]:
        yield r.get("id")
        for c in r["categories"]:
            yield c.get("id")
            for q in c["questions"]:
                yield q.get("id")


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=__import__("glob").glob("/home/mikkel/.cache/ms-playwright/chromium-1208/chrome-linux*/chrome")[0])
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.route("**/jeoparty/api/**", handle_api)
    page.route("**/jeoparty/static/**", lambda r: r.fulfill(body=PNG, headers={"Content-Type": "image/png"}))

    page.goto(f"{BASE}/jeoparty/pack/{PACK_ID}")
    expect(page.locator("#question-pack-name")).to_have_value("Test Pack")
    page.screenshot(path=f"{SHOTS}/01_loaded.png", full_page=True)

    tabs = page.locator(".question-pack-round-select-button")
    check(tabs.nth(0).is_visible() and not tabs.nth(1).is_visible(), "finale tab hidden when include_finale is off")
    save_btn = page.locator("#question-pack-save-btn")
    check(save_btn.is_disabled(), "save disabled on a clean pack")

    # -- add a round, copy categories, add a question with an uploaded image --
    page.click(".question-pack-add-round-btn")
    check(tabs.count() == 3 and "Round 2" in tabs.nth(1).inner_text(), "new round inserted before finale slot")
    check(save_btn.is_enabled(), "save enabled once dirty")
    round2 = page.locator(".question-pack-round-wrapper").nth(1)
    round2.locator(".question-pack-categories-copy").click()
    check(round2.locator(".question-pack-category-name").input_value() == "Geography", "copied category header")

    round2.locator(".question-pack-add-question-btn").click()
    editor = page.locator(".question-pack-question-view")
    expect(editor).to_be_visible()
    check(editor.locator("input.question-reward-span").input_value() == "200", "new round-2 question defaults to 200")
    editor.locator("textarea.question-question-header").fill("Largest ocean?")
    editor.locator(".question-answer-input").fill("Pacific")
    editor.locator(".media-drag-target").first.locator("input.drag-input").set_input_files(
        files=[{"name": "my photo.png", "mimeType": "image/png", "buffer": PNG}])
    expect(editor.locator("img.question-question-image")).to_be_visible()
    page.screenshot(path=f"{SHOTS}/02_editor.png")
    editor.locator(".question-pack-question-view-save").click()
    expect(editor).to_have_count(0)
    check(round2.locator(".question-pack-question-value").all_inner_texts() == ["200"], "question card added to board")

    # -- round 1: preview, delete, multiple choice rename, drag reorder --
    tabs.nth(0).click()
    round1 = page.locator(".question-pack-round-wrapper").nth(0)
    round1.locator(".question-pack-question-wrapper").nth(0).hover()
    check("Capital of France?" in round1.locator(".question-pack-question-preview").inner_text(), "hover preview")
    round1.locator(".question-pack-delete-question-btn").nth(0).click()
    check(round1.locator(".question-pack-question-value").all_inner_texts() == ["200", "300"], "q1 deleted")

    round1.locator(".question-pack-question-wrapper").nth(1).click()  # q3, multiple choice
    expect(editor).to_be_visible()
    choice = editor.locator(".question-choice-text").nth(0)
    choice.fill("Roma")
    check(editor.locator(".question-answer-selection").input_value() == "Roma", "renaming answer choice renames answer")
    editor.locator(".question-add-choice").click()
    editor.locator(".question-choice-text").nth(2).fill("Naples")
    page.screenshot(path=f"{SHOTS}/03_choices.png")
    editor.locator(".question-pack-question-view-save").click()
    expect(editor).to_have_count(0)

    # Drag q3 (300) above q2 (200): the questions swap value slots.
    round1.locator(".question-pack-question-wrapper").nth(1).drag_to(
        round1.locator(".question-first-dropzone"))
    round1.locator(".question-pack-question-wrapper").nth(0).hover()
    check("Capital of Italy?" in round1.locator(".question-pack-question-preview").inner_text(),
          "drag reorder moved q3 to the top slot")
    check(round1.locator(".question-pack-question-value").all_inner_texts() == ["200", "300"], "value slots kept")

    # -- finale --
    page.check("#question-pack-finale")
    check(tabs.nth(2).is_visible(), "finale tab shown when enabled")
    tabs.nth(2).click()
    finale = page.locator(".question-pack-round-wrapper").nth(2)
    finale.locator(".question-pack-categories-placeholder").click()
    check(page.evaluate("document.activeElement.classList.contains('question-pack-category-name')"),
          "new category name focused")
    finale.locator(".question-pack-category-name").fill("Final")
    finale.locator(".question-pack-add-question-btn").click()
    check(editor.locator("input.question-reward-span").input_value() == "300", "finale value = max board value")
    check(editor.locator(".question-do-buzz-countdown").count() == 0, "no buzz timer for finale")
    editor.locator("textarea.question-question-header").fill("Final question?")
    editor.locator(".question-answer-input").fill("Answer")
    editor.locator(".question-pack-question-view-save").click()
    check(finale.locator(".question-pack-add-question-btn").count() == 0, "finale takes one question")
    page.screenshot(path=f"{SHOTS}/04_finale.png", full_page=True)

    # -- save #1 --
    save_btn.click()
    expect(save_btn).to_be_disabled(timeout=5000)
    page.wait_for_timeout(300)
    check(len(saves) == 1, "one save request")
    data, files = saves[0]
    check(not any(i and i.startswith("new-") for i in all_ids(data)), "no temporary ids sent")
    check(len(data["rounds"]) == 3 and [r["round"] for r in data["rounds"]] == [1, 2, 3], "rounds numbered 1..3")
    c1 = data["rounds"][0]["categories"][0]
    deleted = [q["id"] for q in c1["questions"] if q.get("deleted")]
    check(deleted == ["q1"], "deleted question sent as tombstone")
    q3 = next(q for q in c1["questions"] if q.get("id") == "q3")
    check(q3["answer"] == "Roma" and q3["extra"]["choices"] == ["Roma", "Milan", "Naples"] and q3["value"] == 200,
          "edited multiple choice question")
    new_q = data["rounds"][1]["categories"][0]["questions"][0]
    img = new_q["extra"].get("question_image", "")
    check(re.fullmatch(r"[a-z0-9]{16}\.png", img) is not None and new_q["extra"].get("height") == "default",
          f"staged image renamed + height set ({img})")
    check([f for f in files] == [(img, img)], f"only referenced file uploaded ({files})")
    check(data["rounds"][2]["categories"][0]["questions"][0]["value"] == 300, "finale value sent")
    check(errors == [], f"no console errors ({errors})")

    # Ids and media paths written back
    round2.wait_for(state="attached")
    tabs.nth(1).click()
    round2.locator(".question-pack-question-wrapper").nth(0).click()
    page.wait_for_timeout(100)
    check(re.search(r"question_db-q\d+", page.url) is not None, f"new question got its db id ({page.url})")
    src = editor.locator("img.question-question-image").get_attribute("src")
    check(src == f"/jeoparty/static/data/packs/{PACK_ID}/{img}", f"staged path resolved after save ({src})")

    # -- client-side validation inside the editor --
    editor.locator("textarea.question-question-header").fill("")
    editor.locator(".question-pack-question-view-save").click()
    check(editor.locator(".question-pack-editor-error").is_visible(), "editor shows validation error")
    check("error-highlight" in editor.locator("textarea.question-question-header").get_attribute("class"),
          "question field highlighted")
    page.screenshot(path=f"{SHOTS}/05_validation.png")
    dialogs.clear()
    page.keyboard.press("Escape")
    check(dialogs and "Discard" in dialogs[0], "escape asks before discarding edits")
    expect(editor).to_have_count(0)

    # -- pack-level validation: no request goes out --
    page.fill("#question-pack-name", "x")
    save_btn.click()
    page.wait_for_timeout(300)
    check(len(saves) == 1, "invalid pack name blocks the request")
    check("error-highlight" in page.locator("#question-pack-name").get_attribute("class"), "pack name highlighted")
    check(page.locator("#question-pack-popup.popup-error").is_visible(), "error popup visible")
    page.screenshot(path=f"{SHOTS}/06_pack_error.png")
    page.fill("#question-pack-name", "Test Pack")

    # -- delete + recreate the finale question: id is reused, no tombstone --
    tabs.nth(2).click()
    finale_q_id = saves[0] and None
    finale.locator(".question-pack-delete-question-btn").click()
    finale.locator(".question-pack-add-question-btn").click()
    editor.locator("textarea.question-question-header").fill("Another final?")
    editor.locator(".question-answer-input").fill("Yes")
    editor.locator(".question-pack-question-view-save").click()

    # -- dropping an image URL from another tab goes through the fetch proxy --
    tabs.nth(0).click()
    round1.locator(".question-pack-question-wrapper").nth(1).click()  # q2
    answer_target = editor.locator(".media-drag-target").nth(1)
    answer_target.evaluate("""el => {
        const dt = new DataTransfer();
        dt.setData('text/html', '<a href="x"><img src="https://example.com/cat.png"></a>');
        el.dispatchEvent(new DragEvent('dragenter', {dataTransfer: dt, bubbles: true}));
        el.dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true, cancelable: true}));
    }""")
    expect(editor.locator("img.question-answer-image")).to_be_visible()
    editor.locator(".question-pack-question-view-save").click()

    save_btn.click()
    expect(save_btn).to_be_disabled(timeout=5000)
    page.wait_for_timeout(300)
    check(len(saves) == 2, "second save request")
    data2, files2 = saves[1]
    fin = data2["rounds"][2]["categories"][0]["questions"]
    check(len(fin) == 1 and not fin[0].get("deleted") and fin[0].get("id", "").startswith("db-q"),
          f"finale question reused its id ({fin})")
    q2 = next(q for q in data2["rounds"][0]["categories"][0]["questions"] if q.get("id") == "q2")
    ans = q2["extra"].get("answer_image", "")
    check(len(files2) == 1 and files2[0][0] == ans, f"dropped URL image uploaded ({files2}, {ans})")
    check(not any(q.get("deleted") for q in data2["rounds"][0]["categories"][0]["questions"]),
          "tombstones cleared after the first save")

    # -- delete a db round --
    tabs.nth(1).click()
    tabs.nth(1).locator("div").click()
    check(tabs.count() == 2, "round deleted")
    save_btn.click()
    expect(save_btn).to_be_disabled(timeout=5000)
    page.wait_for_timeout(300)
    data3, _ = saves[2]
    check([r.get("deleted", False) for r in data3["rounds"]] == [False, False, True], "deleted round sent last")
    check([r["round"] for r in data3["rounds"][:2]] == [1, 2], "remaining rounds renumbered")

    check(errors == [], f"no console errors ({errors})")
    page.screenshot(path=f"{SHOTS}/07_final.png", full_page=True)
    browser.close()

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
