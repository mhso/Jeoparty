var questionData = {};
var lastSaveState = null;

function showRoundView(round) {
    let selectButtons = document.querySelectorAll(".question-pack-round-select-button");
    selectButtons.forEach((elem) => {
        elem.classList.remove("question-pack-round-selected");
    });

    document.querySelector(`.question-pack-round-select-button-${round}`).classList.add("question-pack-round-selected");

    let roundWrappers = document.querySelectorAll(".question-pack-round-wrapper");
    roundWrappers.forEach((elem) => {
        elem.classList.add("d-none");
    });

    document.querySelector(`.question-pack-round-wrapper-${round}`).classList.remove("d-none");
}

function dataChanged() {
    let saveBtn = document.getElementById("question-pack-save-btn");
    saveBtn.disabled = JSON.stringify(questionData) == lastSaveState
}

function getNextId(round=null, category=null) {
    if (round == null) {
        return questionData["rounds"].length;
    }

    let roundData = questionData["rounds"][round];
    if (category == null) {
        return roundData["categories"].length;
    }

    return roundData["categories"][category]["questions"].length;
}

function getElementId(prefix, index) {
    let elem = document.querySelectorAll(`.${prefix}`)[index];
    for (let i = 0; i < elem.classList.length; i++) {
        if (elem.classList[i].startsWith(`${prefix}-`)) {
            return Number.parseInt(elem.classList[i].replace(`${prefix}-`, ""));
        }
    }

    return null;
}

function getElementIndex(prefix, id) {
    let elem = document.querySelector(`.${prefix}-${id}`);
    if (elem == null) {
        return null;
    }

    let parent = elem.parentElement;
    for (let i = 0; i < parent.children.length; i++) {
        if (parent.children[i] == elem) {
            return i;
        }
    }
    return null;
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
    let roundElem = document.querySelector(`.question-pack-round-wrapper-${round} > .question-pack-round-body`);
    let categoryWrapper = roundElem.querySelector(`.question-pack-category-wrapper-${category} > .question-pack-category-body`);

    let question = getNextId(round, category);
    if (question == 0) {
        questionData["rounds"][round]["categories"][category]["questions"] = [];
    }

    let questionElem = document.createElement("input");
    questionElem.value = value;
    questionElem.classList.add("question-pack-question-wrapper");
    questionElem.classList.add(`question-pack-question-wrapper-${question}`);
    questionElem.readonly = true;
    questionElem.onclick = function() {
        openQuestionModal(round, category, question);
    }

    categoryWrapper.appendChild(questionElem);
}

function deleteQuestion(round, category, question) {
    let roundElem = document.querySelector(`.question-pack-round-wrapper-${round} > .question-pack-round-body`);
    let categoryWrapper = roundElem.querySelector(`.question-pack-category-wrapper-${category} > .question-pack-category-body`);
    let questionElem = categoryWrapper.querySelector(`.question-pack-question-wrapper-${question}`);

    if (questionElem != null) {
        categoryWrapper.removeChild(questionElem);
        questionData["rounds"][round]["categories"][category]["questions"][question]["deleted"] = true;
    }

    dataChanged();
}

function syncCategoryData(round, category) {
    let wrapper = document.querySelector(`.question-pack-category-wrapper-${category}`);
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
    let roundWrapper = document.querySelector(`.question-pack-round-wrapper-${round}`);

    let category = getNextId(round);
    let categoryNum = roundWrapper.querySelectorAll(".question-pack-category-wrapper").length;
    if (categoryNum == 0) {
        questionData["rounds"][round]["categories"] = [];
        let placeholder = roundWrapper.querySelector(".question-pack-categories-placeholder");
        placeholder.classList.add("d-none");
    }

    let categoryElem = document.createElement("div");
    categoryElem.classList.add("question-pack-category-wrapper");
    categoryElem.classList.add(`question-pack-category-wrapper-${category}`);

    let header = document.createElement("div");
    header.className = "question-pack-category-header";

    let deleteBtn = document.createElement("button");
    deleteBtn.className = "question-pack-delete-category-btn";
    deleteBtn.innerHTML = "&times;";
    deleteBtn.onclick = function() {
        deleteCategory(round, category);
    }

    let input = document.createElement("input");
    input.classList.add("question-pack-category-name");
    input.onchange = function() {
        syncCategoryData(round, category);
        dataChanged();
    };
    input.value = "New Category";

    header.appendChild(deleteBtn);
    header.appendChild(input);

    let dataDiv = document.createElement("div");

    let addQuestionBtn = document.createElement("button");
    addQuestionBtn.textContent = "+";
    addQuestionBtn.classList.add("question-pack-add-question-btn");
    addQuestionBtn.onclick = function() {
        openQuestionModal(round, category, null);
    };

    categoryElem.appendChild(header);
    categoryElem.appendChild(dataDiv);
    categoryElem.appendChild(addQuestionBtn);

    roundWrapper.querySelector("div").appendChild(categoryElem);

    syncCategoryData(round, category)
    dataChanged();
}

function deleteCategory(round, category) {
    let roundElem = document.querySelector(`.question-pack-round-wrapper-${round} > div`);
    let categoryElem = roundElem.querySelector(`.question-pack-category-wrapper-${category}`);

    if (categoryElem != null) {
        roundElem.removeChild(categoryElem);
        questionData["rounds"][round]["categories"][category]["deleted"] = true;
        if (questionData["rounds"][round]["categories"].length == 0) {
            let placeholder = roundWrapper.querySelector(".question-pack-categories-placeholder");
            placeholder.classList.remove("d-none");
        }
    }

    dataChanged();
}

function syncRoundData(round) {
    let wrapper = document.querySelector(`.question-pack-round-wrapper-${round}`);
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
    let dataWrapper = document.querySelector("#question-pack-data-body");

    let round = getNextId();
    let roundNum = dataWrapper.querySelectorAll(".question-pack-round-wrapper").length - 1;

    if (round == 0) {
        questionData["rounds"] = [];
    }

    let roundElem = document.createElement("div");
    roundElem.classList.add("question-pack-round-wrapper");
    roundElem.classList.add(`question-pack-round-wrapper-${round}`);

    let input = document.createElement("input");
    input.classList.add("question-pack-round-name");
    input.onchange = function() {
        syncRoundData(round);
        dataChanged();
    };
    input.value = `Round ${roundNum + 1}`;

    let placeholderDiv = document.createElement("div");
    placeholderDiv.textContent = "Add a category below to get started!";
    placeholderDiv.classList = "question-pack-categories-placeholder";

    let dataDiv = document.createElement("div");

    let addCategoryBtn = document.createElement("button");
    addCategoryBtn.textContent = "+";
    addCategoryBtn.classList.add("question-pack-add-category-btn");
    addCategoryBtn.onclick = function() {
        addCategory(round);
    }

    roundElem.appendChild(input);
    roundElem.appendChild(dataDiv);
    roundElem.appendChild(placeholderDiv);
    roundElem.appendChild(addCategoryBtn);

    dataWrapper.insertBefore(roundElem, dataWrapper.lastElementChild);

    // Add to round selection tab
    let selectWrapper = document.querySelector("#question-pack-data-header > div");

    let switchRoundBtn = document.createElement("button");
    switchRoundBtn.className = `question-pack-round-select-button question-pack-round-select-button-${round} question-pack-round-selected`;
    switchRoundBtn.onclick = function() {
        showRoundView(round);
    };

    let switchRoundText = document.createElement("span");
    switchRoundText.textContent = `Round ${roundNum + 1}`;
    switchRoundBtn.appendChild(switchRoundText);

    let deleteRoundBtn = document.createElement("div");
    deleteRoundBtn.innerHTML = "&times;";
    deleteRoundBtn.onclick = function(event) {
        deleteRound(event, round);
    };
    switchRoundBtn.appendChild(deleteRoundBtn);

    selectWrapper.insertBefore(switchRoundBtn, selectWrapper.lastElementChild);

    syncRoundData(round);
    showRoundView(round);
    dataChanged();
}

function deleteRound(event, round) {
    event.stopPropagation();

    if (questionData["rounds"].length == 1) {
        return;
    }

    let headerWrapper = document.querySelector("#question-pack-data-header > div");
    let bodyWrapper = document.querySelector("#question-pack-data-body");

    let selectElems = document.querySelectorAll(".question-pack-round-select-button");
    let selectElem = document.querySelector(`.question-pack-round-select-button-${round}`);
    let roundElem = document.querySelector(`.question-pack-round-wrapper-${round}`)

    let roundSelected = selectElem.classList.contains("question-pack-round-selected");

    if (roundElem != null) {
        let elemIndex = 0;
        selectElems.forEach((elem, index) => {
            if (elem == selectElem) {
                elemIndex = index;
                return;
            }
        });

        headerWrapper.removeChild(selectElem);
        bodyWrapper.removeChild(roundElem);

        if (roundSelected) {
            let switchToRound = elemIndex < selectElem.length - 1 ? elemIndex + 1 : elemIndex;
            showRoundView(getElementId("question-pack-round-wrapper", switchToRound));
        }

        questionData["rounds"][round]["deleted"] = true;

        // Shift all rounds after the deleted one back by one
        for (let i = elemIndex; i < selectElems.length - 1; i++) {
            selectElems[i].getElementsByTagName("span").item(0).textContent = `Round ${i}`;
        }

        dataChanged();
    }
}

function toggleFinale() {
    let enabled = document.getElementById("question-pack-finale").checked;
    let finaleSelect = document.querySelector(".question-pack-round-select-finale");

    if (enabled) {
        finaleSelect.classList.remove("d-none");
    }
    else {
        finaleSelect.classList.add("d-none");
        if (finaleSelect.classList.contains("question-pack-round-selected")) {
            let lastRound = document.querySelectorAll(".question-pack-round-select-button").length - 2;
            showRoundView(lastRound);
        }
    }
}

function syncPackName() {
    let name = document.getElementById("question-pack-name").value;
    questionData["name"] = name;
}

function syncPackPublic() {
    let public = document.getElementById("question-pack-public").checked;
    questionData["public"] = public;
}

function syncPackFinale() {
    let finale = document.getElementById("question-pack-finale").checked;
    questionData["include_finale"] = finale;
}

function getBaseURL() {
    return window.location.protocol + "//" + window.location.hostname + ":" + window.location.port + "/jeoparty";
}

function fade(elem, out, duration) {
    elem.style.transition = null;
    elem.offsetHeight;

    elem.style.opacity = out ? 1 : 0;
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

function showPopup(text, error) {
    let popup = document.getElementById("question-pack-popup");
    popup.classList.remove("d-none");
    if (error) {
        popup.classList.add("popup-error");
        popup.classList.remove("popup-success");
    }
    else {
        popup.classList.add("popup-success");
        popup.classList.remove("popup-error");
    }

    popup.textContent = text;
    popup.style.animationName = null;
    popup.offsetHeight;
    popup.style.animationName = "popup-animate";

    setTimeout(function() {
        popup.classList.add("d-none");
    }, 5000);
}

function saveData(packId) {
    let saveBtn = document.getElementById("question-pack-save-btn");
    saveBtn.disabled = true;

    let btnRegularState = saveBtn.querySelector(".save-btn-regular");
    let btnPendingState = saveBtn.querySelector(".save-btn-pending");
    let btnSuccessState = saveBtn.querySelector(".save-btn-success");
    let btnFailState = saveBtn.querySelector(".save-btn-fail");

    fade(btnRegularState, true, 1);
    fade(btnPendingState, false, 1);

    let baseURL = getBaseURL();
    let jsonData = JSON.stringify(questionData);

    $.ajax(`${baseURL}/pack/${packId}/save`, 
        {
            data: jsonData,
            method: "POST",
            contentType: "application/json",
            content: "application/json"
        }
    ).always(function(a, b, c) {
        let response;
        if (typeof(a) == "object" && Object.hasOwn("status")) {
            response = a;
        }
        else {
            response = c;
        }

        let error = response.status != 200;
        if (!error) {
            showPopup("Question pack saved successfully.", false)
        }
        else if (response.getResponseHeader("content-type") == "text/plain") {
            showPopup(response.responseText, error);
        }
        else if (response.status == 404) {
            showPopup("The question pack was not found on the server or you do not have access to it.", true);
        }
        else if (response.status == 500) {
            showPopup("Internal server error", true);
        }
        else {
            showPopup("An error happened, try again later.", true);
        }

        fade(btnPendingState, true, 1);
    }).done(function() {
        lastSaveState = jsonData;

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
    let modal = document.getElementById("question-pack-modal-wrapper");
    let saveBtn = document.getElementById("question-pack-modal-save-btn");
    let deleteBtn = document.getElementById("question-pack-modal-delete-btn");

    let newQuestion = question == null;

    let actionHeader = document.getElementById("question-pack-modal-action");
    let categoryHeader = document.getElementById("question-pack-modal-category");
    let questionInput = document.getElementById("question-pack-modal-question");
    let answerInput = document.getElementById("question-pack-modal-answer");
    let valueInput = document.getElementById("question-pack-modal-value");
    let buzzInput = document.getElementById("question-pack-modal-buzztime");
    let multipleChoiceCheck = document.getElementById("question-pack-modal-multiple_choice");
    let choicesWrapper = document.getElementById("question-pack-modal-choices");
    let choicesInnerWrapper = document.querySelector("#question-pack-modal-choices > div");

    categoryHeader.textContent = questionData["rounds"][round]["categories"][category]["name"];

    if (newQuestion) {
        question = questionData["rounds"][round]["categories"][category]["questions"].length;

        actionHeader.textContent = "Add question to"
        questionInput.value = "";
        answerInput.value = "";

        let roundWrapper = document.querySelector(`.question-pack-round-wrapper-${round}`);
        let categoryWrapper = roundWrapper.querySelector(`.question-pack-category-wrapper-${category}`);
        let questionIndex = categoryWrapper.querySelectorAll(".question-pack-question-wrapper").length;
        let roundIndex = getElementIndex("question-pack-round-wrapper", round);
        valueInput.value = 100 * (questionIndex + 1) * (roundIndex + 1);
        buzzInput.value = 10;
        multipleChoiceCheck.checked = false;
        choicesWrapper.classList.add("d-none");
        choicesInnerWrapper.innerHTML = "";

        deleteBtn.classList.add("d-none");
    }
    else {
        let data = questionData["rounds"][round]["categories"][category]["questions"][question];
    
        actionHeader.textContent = "Edit question for"
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

        deleteBtn.classList.remove("d-none");
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
            deleteQuestion(round, category, question);
            closeQuestionModal();
        }
    }

    modal.classList.remove("d-none");
}

function closeQuestionModal() {
    document.getElementById("question-pack-modal-wrapper").classList.add("d-none");
}

document.addEventListener("DOMContentLoaded", function() {
    showRoundView(0);
});