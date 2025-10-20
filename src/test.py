# import json

# from jeoparty.api.database import Database
# from jeoparty.api.orm.models import Game, GameQuestion

# database = Database()

# with database as session:
#     game_data = database.get_game_from_id("abf97d33-c55d-473e-aee8-724c0ceeb455")
#     game_questions = [
#         GameQuestion(
#             game_id=game_data.id,
#             question_id=question.id,
#         ) 
#         for question in database.get_question_packs_for_user(game_data.created_by, game_data.pack_id, True).get_all_questions()
#     ]
#     session.add_all(game_questions)

#     session.commit()
#     #print(json.dumps(game_data.dump(included_relations=[Game.pack])))

import requests

url = "https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Fimages.prismic.io%2Frivalryglhf%2Fd003516c-b032-4856-87c9-bdfa42b2d1cd_Elder%2BDragon%2BLoL.jpg%3Fauto%3Dcompress%2Cformat%26rect%3D0%2C35%2C1920%2C1008%26w%3D1200%26h%3D630&f=1&nofb=1&ipt=4381b1460d1beaac8b1ef6686309654f5cf3150d366577f0bb2518e21b75bea5"

response = requests.options(url)

print(response.status_code)
print(response.headers)

exit(0)

response = requests.get(url)

headers = {}
mime_type = None
if (content_type := response.headers.get("Content-Type")):
    headers["Content-Type"] = content_type
    mime_type = content_type

print(headers)
print(mime_type)
