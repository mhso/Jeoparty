import json
import os

from jeoparty.api.enums import Language
from jeoparty.api.config import Config

def _get_locale_filename(language: Language):
    return f"{Config.RESOURCES_FOLDER}/locales/{language.value}.json"

def test_available_languages():
    for language in Language:
        filename = _get_locale_filename(language)
        assert os.path.exists(filename)

def test_entries():
    locale_data = []
    for language in Language:
        filename = _get_locale_filename(language)
        with open(filename, "r", encoding="utf-8") as fp:
            data = json.load(fp)
            locale_data.append(data)

    # Test that they keys in 'pages' are the same across languages
    page_keys = []
    for data in locale_data:
        page_keys.append(set(data["pages"].keys()))

    for prev_index, keys in enumerate(page_keys[1:]):
        prev_keys = page_keys[prev_index]
        
        assert prev_keys == keys

    # Test that the keys in all pages are the same across languages
    for page in page_keys[0]:
        for prev_index, data in enumerate(locale_data[1:]):
            prev_data = locale_data[prev_index]
            assert set(data["pages"][page].keys()) == set(prev_data["pages"][page].keys())
