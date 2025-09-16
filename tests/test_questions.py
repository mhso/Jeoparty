def test_questions_well_formed(config):
    def get_base_path(filename):
        return f"{config.static_folder}/img/jeopardy/{filename}"

    def get_question_path(filename):
        return f"{config.static_folder}/img/jeopardy/{JEOPARDY_ITERATION}/{filename}"

    with open(f"{config.static_folder}/data/jeopardy_questions_{JEOPARDY_ITERATION}.json", "r", encoding="utf-8") as fp:
        all_question_data = json.load(fp)

    mandatory_category_keys = set(["name", "order", "background", "tiers"])
    optional_category_keys = set(["buzz_time"])
    mandatory_tiers_keys = set(["value", "questions"])
    mandatory_question_keys = set(["question", "answer"])
    optional_question_keys = set(
        [
            "choices",
            "image",
            "explanation",
            "answer_image",
            "video",
            "tips",
            "height",
            "border",
            "volume"
        ]
    )

    for index, category in enumerate(all_question_data):
        category_data = all_question_data[category]

        for key in mandatory_category_keys:
            assert key in category_data, "Mandatory category key missing"

        assert len(set(category_data.keys()) - (mandatory_category_keys.union(optional_category_keys))) == 0, "Wrong category keys"

        assert os.path.exists(get_base_path(category_data["background"])), "Background missing"

        tiers = all_question_data[category]["tiers"] if index < 6 else [all_question_data[category]["tiers"][-1]]

        for tier_data in tiers:
            assert set(tier_data.keys()) == mandatory_tiers_keys, "Wrong tier keys"

            expected_num_questions = JEOPARDY_REGULAR_ROUNDS if index < 6 else 1
            assert len(tier_data["questions"]) == expected_num_questions

            for question_data in tier_data["questions"]:
                for key in mandatory_question_keys:
                    assert key in question_data, "Mandatory question key missing"

                assert len(set(question_data.keys()) - (mandatory_question_keys.union(optional_question_keys))) == 0, "Wrong question keys"

                for key in ("image", "answer_image", "video"):
                    if key in question_data:
                        assert os.path.exists(get_question_path(question_data[key])), "Question image/video missing"
                        assert "height" in question_data

                if "choices" in question_data:
                    choices = question_data["choices"]
                    assert isinstance(choices, list) and len(choices) == 4, "Wrong amount of choices for multiple choice"
                    assert question_data["answer"] in choices, "Answer is not in the list of choices"

    with open(f"{config.static_folder}/data/jeopardy_used_{JEOPARDY_ITERATION}.json", "r", encoding="utf-8") as fp:
        used_data = json.load(fp)

    question_keys = set(all_question_data.keys())
    used_keys = set(used_data.keys())

    assert question_keys == used_keys, "Used questions don't match"
