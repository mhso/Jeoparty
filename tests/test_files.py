import os

from jinja2.environment import Environment
from jinja2.loaders import BaseLoader
from jinja2.exceptions import TemplateNotFound

class TemplateLoader(BaseLoader):
    def __init__(self):
        self.path = "src/jeoparty/app/templates"
        super().__init__()

    def get_source(self, environment, template):
        path = os.path.join(self.path, template)
        if not os.path.exists(path):
            raise TemplateNotFound(template)

        mtime = os.path.getmtime(path)
        with open(path) as f:
            source = f.read()

        return source, path, lambda: mtime == os.path.getmtime(path)

def url_for(endpoint, filename: str | None = None, _external: bool = True, **kwargs):
    final_endpoint = f"/{endpoint}"
    for v in kwargs.values():
        final_endpoint += f"/{v}"

    if filename is not None:
        final_endpoint += f"/{filename}"

    if _external:
        final_endpoint = f"127.0.0.1:5006/{final_endpoint}"

    return final_endpoint

def render_template(template_name, locale_data, **kwargs):
    page_key = template_name.split(".")[0]

    page_data = locale_data["pages"].get(page_key, {})
    page_data.update(locale_data["pages"].get("global", {}))
    kwargs["_locale"] = page_data

    jinja_env = Environment(loader=TemplateLoader())
    template = jinja_env.get_template(template_name)
    template.globals["url_for"] = url_for
    return template.render(**kwargs)

def find_files(html):
    pass

def test_pages(locales):
    global_vars = {
        "title": "Quiz Hour"
    }

    pages = {
        "presenter/endscreen.html": {
            **global_vars,

        },
        "presenter/finale.html": {},
        "presenter/lobby.html": {
            **global_vars,
            "join_url": "https://localhost/jeoparty/quiz_hour",
        },
        "presenter/question.html": {},
        "presenter/selection.html": {},
    }

    for lang in locales:
        for page in pages:
            html = render_template(page, locales[lang], **pages[page])
            files = find_files(html)
