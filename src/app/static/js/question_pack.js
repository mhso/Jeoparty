var questionData = {};

function showRoundView(round) {
    let selectButtons = document.querySelectorAll(".question-pack-round-select-button");
    selectButtons.forEach((elem) => {
        elem.classList.remove("question-pack-round-selected");
    });

    selectButtons[round].classList.add("question-pack-round-selected");

    let roundWrappers = document.querySelectorAll(".question-pack-round-wrapper");
    roundWrappers.forEach((elem) => {
        elem.classList.add("d-none");
    });

    roundWrappers[round].classList.remove("d-none");
}

function dataChanged() {
    let saveBtn = document.getElementById("question-pack-save-all");
    saveBtn.disabled = false;
}

function syncQuestionData(round, category, question) {
    let questionText = document.getElementById("question-pack-modal-question").value;
    let answerText = document.getElementById("question-pack-modal-answer").value;
    let value = document.getElementById("question-pack-modal-value").value;
    let buzzTime = document.getElementById("question-pack-modal-buzztime").value;
    let isMultipleChoice = document.getElementById("question-pack-modal-multiple_choice").checked;
    let choices = document.querySelectorAll(".question-pack-modal-choice");

    let data = {
        "question": questionText,
        "answer": answerText,
        "value": value,
        "buzz_time": buzzTime,
    }
    if (isMultipleChoice) {
        data["choices"] = choices.map((choice) => choice.textContent);
    }

    let questionDataQuestions = questionData["rounds"][round]["categories"][category]["questions"];
    if (questionDataQuestions.length == question) {
        questionDataQuestions.push(data);
    }
    else {
        questionDataQuestions[question] = data;
    }
}

function addQuestion(value, round, category) {
    let roundElem = document.querySelectorAll(".question-pack-round-wrapper > div")[round];
    let categoryWrapper = roundElem.querySelectorAll(".question-pack-category-wrapper > div")[category];

    let question = categoryWrapper.querySelectorAll(".question-pack-question-wrapper").length;
    if (question == 0) {
        questionData["rounds"][round]["categories"][category]["questions"] = [];
    }

    let questionElem = document.createElement("div");
    questionElem.textContent = value;
    questionElem.classList.add("question-pack-question-wrapper");
    questionElem.onclick = function() {
        openQuestionModal(round, category, question);
    }

    categoryWrapper.appendChild(questionElem);
}

function deleteQuestion(round, category, question) {
    let roundElem = document.querySelectorAll(".question-pack-round-wrapper > div")[round];
    let categoryWrapper = roundElem.querySelectorAll(".question-pack-category-wrapper > div")[category];
    let questionElem = categoryWrapper.querySelectorAll(".question-pack-question-wrapper")[question];

    if (questionElem != null) {
        categoryWrapper.removeChild(questionElem);
        questionData["rounds"][round]["categories"][category]["questions"].splice(question, 1);
    }
}

function syncCategoryData(round, category) {
    let wrapper = document.querySelectorAll(".question-pack-category-wrapper")[category];
    let name = wrapper.querySelector(".question-pack-category-name").value;

    let questionDataCategories = questionData["rounds"][round]["categories"];
    if (questionDataCategories.length == category) {
        questionDataCategories.push({"name": name, "order": category, "questions": []});
    }
    else {
        questionDataCategories[category]["name"] = name;
        questionDataCategories[category]["order"] = category;
    }
}

function addCategory(round) {
    // Add new category for given round
    let roundWrapper = document.querySelectorAll(".question-pack-round-wrapper > div")[round];

    let category = roundWrapper.querySelectorAll(".question-pack-category-wrapper").length;
    if (category == 0) {
        questionData["rounds"][round]["categories"] = [];
        let placeholder = roundWrapper.querySelector(".question-pack-categories-placeholder");
        placeholder.classList.add("d-none");
    }

    let categoryElem = document.createElement("div");
    categoryElem.classList.add("question-pack-category-wrapper");

    let input = document.createElement("input");
    input.classList.add("question-pack-category-name");
    input.value = "New Category";

    let dataDiv = document.createElement("div");

    let addQuestionBtn = document.createElement("button");
    addQuestionBtn.textContent = "+";
    addQuestionBtn.classList.add("question-pack-add-question-btn");
    addQuestionBtn.onclick = function() {
        openQuestionModal(round, category, null);
    };

    categoryElem.appendChild(input);
    categoryElem.appendChild(dataDiv);
    categoryElem.appendChild(addQuestionBtn);

    roundWrapper.appendChild(categoryElem);

    syncCategoryData(round, category)
    dataChanged();
}

function deleteCategory(round, category) {
    let roundElem = document.querySelectorAll(".question-pack-round-wrapper > div")[round];
    let categoryElem = roundElem.querySelectorAll(".question-pack-category-wrapper")[category];

    if (categoryElem != null) {
        categoryWrapper.removeChild(categoryElem);
        questionData["rounds"][round]["categories"].splice(category, 1);
        if (questionData["rounds"][round]["categories"].length == 0) {
            let placeholder = roundWrapper.querySelector(".question-pack-categories-placeholder");
            placeholder.classList.remove("d-none");
        }
    }
}

function syncRoundData(round) {
    let wrapper = document.querySelectorAll(".question-pack-round-wrapper")[round];
    let name = wrapper.querySelector(".question-pack-round-name").value;

    let questionDataRounds = questionData["rounds"];
    if (questionDataRounds.length == round) {
        questionDataRounds.push({"name": name, "round": round, "categories": []});
    }
    else {
        questionDataRounds[round]["name"] = name;
        questionDataRounds[round]["round"] = round;
    }
}

function addRound() {
    // Add new round
    let dataWrapper = document.querySelector("#question-pack-data-wrapper > div");

    let round = dataWrapper.querySelectorAll(".question-pack-round-wrapper").length;
    if (round == 0) {
        questionData["rounds"] = [];
    }

    let roundElem = document.createElement("div");
    roundElem.classList.add("question-pack-round-wrapper");

    let input = document.createElement("input");
    input.classList.add("question-pack-round-name");
    input.value = `Round ${round + 1}`;

    let dataDiv = document.createElement("div");

    let addCategoryBtn = document.createElement("button");
    addCategoryBtn.textContent = "+";
    addCategoryBtn.classList.add("question-pack-add-category-btn");

    roundElem.appendChild(input);
    roundElem.appendChild(dataDiv);
    roundElem.appendChild(addCategoryBtn);

    dataWrapper.appendChild(roundElem);

    // Add to round selection tab
    let selectWrapper = document.querySelector("#question-pack-round-select > div");

    let switchRoundBtn = document.createElement("button");
    switchRoundBtn.textContent = `Round ${round + 1}`;
    switchRoundBtn.className = "question-pack-round-select-button question-pack-round-selected";
    switchRoundBtn.onclick = function() {
        showRoundView(round);
    };

    selectWrapper.appendChild(switchRoundBtn);

    syncRoundData(round);
    showRoundView(round);
    dataChanged();
}

function syncGeneralData() {
    let name = document.getElementById("question-pack-name").value;
    let public = document.getElementById("question-pack-public").checked;
    let finale = document.getElementById("question-pack-finale").checked;

    questionData["name"] = name;
    questionData["public"] = public;
    questionData["include_finale"] = finale;
}

function getBaseURL() {
    return window.location.protocol + "//" + window.location.hostname + ":" + window.location.port + "/jeopardy";
}

function fade(elem, out, duration) {
    elem.style.transition = null;
    elem.offsetHeight;

    popupElem.style.opacity = out ? 1 : 0;
    elem.style.transition = `opacity ${duration}s`;

    elem.offsetHeight;

    if (!out) {
        elem.classList.remove("d-none");
    }

    let opacity = out ? 0 : 1;
    elem.style.opacity = opacity;

    if (out) {
        setTimeout(function() {
            elem.classList.add("d-none");
        }, duration * 1000);
    }
}

function showPopup(text) {
    let popupElem = document.getElementById("question-pack-popup");
    popupElem.textContent = text;
    fade(popupElem, false, 1);
}

function saveData(packId) {
    let saveBtn = document.getElementById("question-pack-save-all");
    saveBtn.disabled = true;

    syncGeneralData();

    let btnRegularState = saveBtn.querySelector(".save-btn-regular");
    let btnPendingState = saveBtn.querySelector(".save-btn-pending");
    let btnSuccessState = saveBtn.querySelector(".save-btn-success");
    let btnFailState = saveBtn.querySelector(".save-btn-fail");

    fade(btnRegularState, true, 1);
    fade(btnPendingState, false, 1);

    let baseURL = getBaseURL();

    $.ajax(
        `${baseURL}/${packId}/save`,
        data=questionData,
        method="POST"
    ).always(function(response) {
        showPopup(response);
        fade(btnPendingState, true, 1);
    }).done(function() {
        fade(btnSuccessState, false, 1);
        setTimeout(function() {
            fade(btnSuccessState, true, 1);
            fade(btnRegularState, false, 1);
        }, 3000);
    }).fail(function() {
        fade(btnFailState, false, 1);
        setTimeout(function() {
            fade(btnFailState, true, 1);
            fade(btnRegularState, false, 1);
        }, 3000);
    });
}

function modalAddAnswerChoice() {
    let choicesInnerWrapper = document.querySelector("#question-pack-modal-choices > div");

    let choices = document.querySelectorAll(".question-pack-modal-choice").length;

    let choiceElem = document.createElement("input");
    choiceElem.classList.add("question-pack-modal-choice");
    choiceElem.value = `Choice ${choices + 1}`;

    choicesInnerWrapper.appendChild(choiceElem);
}

function modalSetMultipleChoice() {
    let checked = document.getElementById("question-pack-modal-multiple_choice").checked;
    let choicesWrapper = document.getElementById("question-pack-modal-choices");
    let choices = document.querySelectorAll(".question-pack-modal-choice").length;

    if (checked) {
        if (choices == 0) {
            modalAddAnswerChoice();
        }
        choicesWrapper.classList.remove("d-none");
    }
    else {
        choicesWrapper.classList.add("d-none");
    }
}

function openQuestionModal(round, category, question) {
    let modal = document.getElementById("question-pack-modal");
    let saveBtn = document.getElementById("question-pack-modal-save-btn");
    let deleteBtn = document.getElementById("question-pack-modal-delete-btn");

    let newQuestion = question == null;

    let questionInput = document.getElementById("question-pack-modal-question");
    let answerInput = document.getElementById("question-pack-modal-answer");
    let valueInput = document.getElementById("question-pack-modal-value");
    let buzzInput = document.getElementById("question-pack-modal-buzztime");
    let multipleChoiceCheck = document.getElementById("question-pack-modal-multiple_choice");
    let choicesWrapper = document.getElementById("question-pack-modal-choices");
    let choicesInnerWrapper = document.querySelector("#question-pack-modal-choices > div");

    if (newQuestion) {
        question = questionData["rounds"][round]["categories"][category]["questions"].length;

        deleteBtn.disabled = true;

        questionInput.value = "";
        answerInput.value = "";
        valueInput.value = 100 * (question + 1) * (round + 1);
        buzzInput.value = 10;
        multipleChoiceCheck.checked = false;
        choicesWrapper.classList.add("d-none");
        choicesInnerWrapper.innerHTML = "";
    }
    else {
        let data = questionData["rounds"][round]["categories"][category]["questions"][question];
        questionInput.value = data["question"];
        answerInput.value = data["answer"];
        valueInput.value = data["value"];
        buzzInput.value = data["buzz_time"]
        multipleChoiceCheck.checked = Object.hasOwn("choices");
        if (multipleChoiceCheck.checked) {
            choicesWrapper.classList.remove("d-none");
        }
        else {
            choicesWrapper.classList.add("d-none");
        }
    }

    saveBtn.onclick = function() {
        if (newQuestion) {
            addQuestion(valueInput.value, round, category);
        }

        syncQuestionData(round, category, question);
        dataChanged();
        closeQuestionModal();
    };
    
    if (!newQuestion) {
        deleteBtn.onclick = function() {
            
        }
    }

    modal.classList.remove("d-none");
}

function closeQuestionModal() {
    document.getElementById("question-pack-modal").classList.remove("d-none");
}

document.addEventListener("DOMContentLoaded", function() {
    showRoundView(0);
});