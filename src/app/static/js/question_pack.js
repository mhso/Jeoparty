var questionData = {};
var questionMedia = {};
var lastSaveState = null;

const imageFileTypes = [
    "image/apng",
    "image/gif",
    "image/jpeg",
    "image/jpg",
    "image/pjpeg",
    "image/png",
    "image/webp",
];

const videoFileTypes = [
    "video/webm",
    "video/mp4",
];

function isMediaValidType(file) {
    if (imageFileTypes.includes(file.type)) {
        return true;
    }
    else if (videoFileTypes.includes(file.type)) {
        return true;
    }

    return null;
}

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
    let doBuzzTimer = document.getElementById("question-pack-modal-do-buzz-timer").checked;
    let buzzTime = document.getElementById("question-pack-modal-buzztime").value;
    let isMultipleChoice = document.getElementById("question-pack-modal-multiple_choice").checked;
    let choices = document.querySelectorAll(".question-pack-modal-choice");
    let questionMediaInput = document.getElementById("question-pack-modal-question-media-input");
    let answerMediaInput = document.getElementById("question-pack-modal-answer-media-input");

    
    // Set buzz time on category
    questionData["rounds"][round]["categories"][category]["buzz_time"] = doBuzzTimer ? buzzTime : 0;
    
    let data = {
        "question": questionText,
        "answer": answerText,
        "value": value,
    }

    // Add multiple choice entries
    if (isMultipleChoice) {
        data["choices"] = choices.map((choice) => choice.textContent);
    }

    // Save question image or video
    if (questionMediaInput.files.length == 1) {
        let questionMediaFile = questionMediaInput.files[0];
        let key = null;
        if (!isMediaValidType(questionMediaFile)) {
            return;
        }
        if (imageFileTypes.includes(questionMediaFile.type)) {
            key = "question_image";
        }
        else if (videoFileTypes.includes(questionMediaFile.type)) {
            key = "video";
        }
    
        if (key != null) {
            data[key] = questionMediaFile.name.split(".")[0];
            questionMedia[data[key]] = questionMediaFile;
        }
    }

    // Save answer image
    if (answerMediaInput.files.length == 1) {
        let answerMediaFile = answerMediaInput.files[0];
        if (imageFileTypes.includes(questionMediaFile.type)) {
            data["answer_image"] = answerMediaFile.name.split(".")[0];
            questionMedia[data["answer_image"]] = answerMediaFile;
        }
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
    if (!confirm("Are you sure you want to delete this question?")) {
        return;
    }

    let roundElem = document.querySelector(`.question-pack-round-wrapper-${round} > .question-pack-round-body`);
    let categoryWrapper = roundElem.querySelector(`.question-pack-category-wrapper-${category} > .question-pack-category-body`);
    let questionElem = categoryWrapper.querySelector(`.question-pack-question-wrapper-${question}`);

    if (questionElem != null) {
        categoryWrapper.removeChild(questionElem);
        let dataForQuestion = questionData["rounds"][round]["categories"][category]["questions"][question];
        if (Object.hasOwn(dataForQuestion, "question_image") && Object.hasOwn(questionMedia, dataForQuestion["question_image"])) {
            questionMedia[dataForQuestion["question_image"]] = null;
        }
        else if (Object.hasOwn(dataForQuestion, "video") && Object.hasOwn(questionMedia, dataForQuestion["video"])) {
            questionMedia[dataForQuestion["video"]] = null;
        }

        if (Object.hasOwn(dataForQuestion, "answer_image") && Object.hasOwn(questionMedia, dataForQuestion["answer_image"])) {
            questionMedia[dataForQuestion["answer_image"]] = null;
        }

        dataForQuestion["deleted"] = true;
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
    if (!confirm("Are you sure you want to delete this category and all its data?")) {
        return;
    }

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

    if (!confirm("Are you sure you want to delete this round and all its data?")) {
        return;
    }

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
    return window.location.protocol + "//" + window.location.hostname + ":" + window.location.port;
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

    let formData = new FormData();
    Object.entries(questionMedia).forEach(([k, v]) => {
        if (v != null) {
            formData.append(k, v);
        }
    });

    formData.append("data", jsonData);

    $.ajax(`${baseURL}/jeoparty/pack/${packId}/save`, 
        {
            data: formData,
            method: "POST",
            contentType: false,
            processData: false,
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

function modalSetDoBuzzTime() {
    let checked = document.getElementById("question-pack-modal-do-buzz-timer").checked;
    let buzzTimeInput = document.getElementById("question-pack-modal-buzztime");

    buzzTimeInput.disabled = !checked;
}

function modalAddAnswerChoice() {
    let choicesInnerWrapper = document.querySelector("#question-pack-modal-choices-data");

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

function modalShowMediaPreview(wrapper, fileSrc=null, fileType=null, mediaElem=null) {
    let previewWrapper = wrapper.querySelector(".modal-drag-target-preview-wrapper");
    let header = wrapper.querySelector(".modal-drag-target-header");

    previewWrapper.innerHTML = "";

    if (mediaElem == null) {    
        if (imageFileTypes.includes(fileType)) {
            mediaElem = document.createElement("img");
            mediaElem.className = ".modal-drag-target-image";
        }
        else {
            let video = document.createElement("video");
            mediaElem = document.createElement("source");

            video.className = ".modal-drag-target-video";
            mediaElem.type = fileType;
        }
    
        mediaElem.src = fileSrc;
    }
    else {
        mediaElem.classList.remove("d-none");
    }

    mediaElem.classList.add("modal-drag-target-preview");

    previewWrapper.appendChild(mediaElem);

    previewWrapper.classList.remove("d-none");
    header.classList.add("d-none");
}

function openMediaInput(event) {
    let target = event.target;
    while (!target.classList.contains("media-drag-target")) {
        target = target.parentElement;
    }

    let input = target.querySelector(".modal-drag-input");
    input.click();
}

function validateAndGetFile(files, wrapper) {
    if (files.length != 1) {
        return null;
    }

    let file = files[0];
    if (!isMediaValidType(file)) {
        alert("Invalid file type.");
        return null;
    }

    modalShowMediaPreview(wrapper, URL.createObjectURL(file), file.type);

    return file;
}

function modalMediaFileSelected(event, mediaKey) {
    let input = event.target.querySelector(".modal-drag-input");
    let file = validateAndGetFile(input.files, event.target.parentElement, mediaKey);

    if (file == null) {
        input.files = [];
    }
}

function modalMediaDragDropped(event, mediaKey) {
    let input = event.target.querySelector(".modal-drag-input");
    let file = validateAndGetFile(event.dataTransfer.files, event.target.parentElement, mediaKey);
    if (file == null) {
        return;
    }

    input.files = [file];
}

function modalMediaDragEnter(event) {
    let header = event.target.querySelector(".modal-drag-target-header");
    header.classList.add("d-none");
}

function modalMediaDragLeave(event) {
    let header = event.target.querySelector(".modal-drag-target-header");
    let preview = event.target.querySelector(".modal-drag-target-preview-wrapper");
    if (preview.classList.contains("d-none")) {
        header.classList.remove("d-none");
    }
}

function openQuestionModal(roundId, categoryId, questionId) {
    let modal = document.getElementById("question-pack-modal-wrapper");
    let saveBtn = document.getElementById("question-pack-modal-save-btn");
    let deleteBtn = document.getElementById("question-pack-modal-delete-btn");

    let newQuestion = questionId == null;

    let actionHeader = document.getElementById("question-pack-modal-action");
    let categoryHeader = document.getElementById("question-pack-modal-category");
    let questionInput = document.getElementById("question-pack-modal-question");
    let answerInput = document.getElementById("question-pack-modal-answer");
    let valueInput = document.getElementById("question-pack-modal-value");
    let buzzTimerCheck = document.getElementById("question-pack-modal-do-buzz-timer");
    let buzzInput = document.getElementById("question-pack-modal-buzztime");
    let multipleChoiceCheck = document.getElementById("question-pack-modal-multiple_choice");
    let choicesWrapper = document.getElementById("question-pack-modal-choices");
    let choicesInnerWrapper = document.querySelector("#question-pack-modal-choices-data");
    let questionMediaWrapper = document.querySelector("#question-pack-modal-question-media-wrapper");

    categoryHeader.textContent = questionData["rounds"][roundId]["categories"][categoryId]["name"];

    if (newQuestion) {
        questionId = questionData["rounds"][roundId]["categories"][categoryId]["questions"].length;

        actionHeader.textContent = "Add question to"
        questionInput.value = "";
        answerInput.value = "";

        let roundWrapper = document.querySelector(`.question-pack-round-wrapper-${roundId}`);
        let categoryWrapper = roundWrapper.querySelector(`.question-pack-category-wrapper-${categoryId}`);
        let questionIndex = categoryWrapper.querySelectorAll(".question-pack-question-wrapper").length;
        let roundIndex = getElementIndex("question-pack-round-wrapper", roundId);
        valueInput.value = 100 * (questionIndex + 1) * (roundIndex + 1);
        buzzInput.value = 10;
        buzzTimerCheck.checked = true;
        multipleChoiceCheck.checked = false;
        choicesWrapper.classList.add("d-none");
        choicesInnerWrapper.innerHTML = "";

        deleteBtn.classList.add("d-none");
    }
    else {
        let dataForCategory = questionData["rounds"][roundId]["categories"][categoryId];
        let dataForQuestion = dataForCategory["questions"][questionId];
        
        actionHeader.textContent = "Edit question for"
        questionInput.value = dataForQuestion["question"];
        answerInput.value = dataForQuestion["answer"];
        valueInput.value = dataForQuestion["value"];
        if (dataForCategory["buzz_time"] > 0) {
            buzzInput.value = dataForCategory["buzz_time"];
            buzzTimerCheck.checked = true;
        }
        else {
            buzzInput.value = "";
            buzzInput.disabled = true;
            buzzTimerCheck.checked = false;
        }

        multipleChoiceCheck.checked = Object.hasOwn(dataForQuestion.extra, "choices");
        if (multipleChoiceCheck.checked) {
            choicesWrapper.classList.remove("d-none");
        }
        else {
            choicesWrapper.classList.add("d-none");
        }

        if (Object.hasOwn(dataForQuestion.extra, "question_image") || Object.hasOwn(dataForQuestion.extra, "video")) {
            let mediaElem = null;
            if (Object.hasOwn(dataForQuestion.extra, "question_image")) {
                mediaElem = document.querySelector(`.question-pack-round-wrapper-${roundId} .question-pack-category-wrapper-${categoryId} .question-pack-question-image-${questionId}`);
            }
            else {
                mediaElem = document.querySelector(`.question-pack-round-wrapper-${roundId} .question-pack-category-wrapper-${categoryId} .question-pack-question-video-${questionId}`);
            }

            modalShowMediaPreview(questionMediaWrapper, null, null, mediaElem.cloneNode(true));
        }

        deleteBtn.classList.remove("d-none");
    }

    saveBtn.onclick = function() {
        if (newQuestion) {
            addQuestion(valueInput.value, roundId, categoryId);
        }

        syncQuestionData(roundId, categoryId, questionId);
        dataChanged();
        closeQuestionModal();
    };
    
    if (!newQuestion) {
        deleteBtn.onclick = function() {
            deleteQuestion(roundId, categoryId, questionId);
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