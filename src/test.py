import json
from sqlalchemy import text

from jeoparty.api.database import Database
from jeoparty.api.orm.models import Game, GameQuestion

database = Database()

with database as session:
    updated = []
    for q_id, extra in session.execute(text("SELECT id, extra FROM questions")):
        if extra:
            extra_dict = json.loads(extra)
            if "volme" in extra_dict:
                extra_dict["volume"] = extra_dict["volme"]
                del extra_dict["volme"]

            updated.append({"id": q_id, "extra": json.dumps(extra_dict)})

    session.execute(text("UPDATE questions SET extra = :extra WHERE id = :id"), updated)
    session.commit()
