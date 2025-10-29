var questionData = {};
var questionMedia = {};
var lastSaveState = null;
var wrapperHeight = 0;
var wrapperWidth = 0;

const REGULAR_MEDIA_HEIGHT = 420
const SMALL_MEDIA_HEIGHT = 256
const MAXIMIZED_MEDIA_HEIGHT = 760

const letters = Array.from("abcdefghijklmnopqrstuvwxyz0123456789")
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

    setURLHash("round", round);
}

function dataChanged() {
    let saveBtn = document.getElementById("question-pack-save-btn");
    saveBtn.disabled = JSON.stringify(questionData) == lastSaveState
}

function parseURLHash() {
    let questionView = null;
    let roundView = null;

    if (window.location.hash) {
        const params = window.location.hash.replace("#", "").split(";");
        for (let param of params) {
            if (param.startsWith("question_")) {
                let split = param.replace("question_", "").split("-");
                if (split.length == 3) {
                    questionView = split;
                }
            }
            else if (param.startsWith("round_")) {
                roundView = Number.parseInt(param.replace("round_", ""));
            }
        }
    }

    return [questionView, roundView];
}

function setURLHash(key, value) {
    let [questionView, roundView] = parseURLHash();
    let hash = "#";
    if (key == "question") {
        if (value != null)  {
            hash = `${key}_${value}`;
        }
        if (roundView != null) {
            if (value != null) {
                hash += ";";
            }
            hash += `round_${roundView}`;
        }
    }
    else if (key == "round") {
        if (questionView) {
            hash = `question_${questionView}`;
            if (value != null) {
                hash += ";";
            }
        }
        
        if (value != null) {
            hash += `${key}_${value}`;
        }
    }

    window.location.hash = hash;
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

function getQuestionViewWrapper(roundId, categoryId, questionId) {
    return document.querySelector(`.question-pack-round-wrapper-${roundId} .question-pack-category-wrapper-${categoryId} .question-pack-question-view-${questionId}`);
}

function getUniqueFilename(filename) {
    let uniqueName = filename;
    let num = 1;
    while (Object.hasOwn(questionMedia, uniqueName)) {
        uniqueName = filename + num.toString();
        num += 1;
    }

    return uniqueName
}

function syncQuestionData(round, category, question) {
    let wrapper = getQuestionViewWrapper(round, category, question);

    let questionText = wrapper.querySelector(".question-question-header").value;
    let answerText = wrapper.querySelector(".question-answer-input").value;
    let value = wrapper.querySelector(".question-reward-span").value;
    let explanationText = wrapper.querySelector(".question-explanation-input").value;
    let doBuzzTimer = wrapper.querySelector(".question-do-buzz-countdown").checked;
    let buzzTime = wrapper.querySelector(".question-countdown-text").value;
    let isMultipleChoice = wrapper.querySelector(".question-multiple-choice-checkbox").checked;
    let choices = wrapper.querySelectorAll(".question-choice-text");
    let questionMediaInput = wrapper.querySelector(".question-question-media-input");
    let answerMediaInput = wrapper.querySelector(".question-answer-media-input");
    let tips = wrapper.querySelectorAll(".question-tip-content");

    // Set buzz time on category
    questionData["rounds"][round]["categories"][category]["buzz_time"] = doBuzzTimer ? buzzTime : 0;
    let questionDataQuestions = questionData["rounds"][round]["categories"][category]["questions"];

    let data;
    if (question < questionDataQuestions.length) {
        data = questionDataQuestions[question];
        data["question"] = questionText;
        data["answer"] = answerText;
        data["value"] = value;
    }
    else {
        data = {
            "question": questionText,
            "answer": answerText,
            "value": value,
            "extra": {},
        }
    }

    // Add multiple choice entries
    if (isMultipleChoice) {
        data["extra"]["choices"] = Array.from(choices).map((choice) => choice.value);
    }

    // Save explanation
    if (explanationText) {
        data["extra"]["explanation"] = explanationText;
    }

    // Save tips
    let tipData = Array.from(tips).map((tip) => tip.value).filter((tip) => tip != "");
    if (tipData.length > 0) {
        data["extra"]["tips"] = tipData;
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
            data["extra"][key] = getUniqueFilename(questionMediaFile.name.split(".")[0]);
            questionMedia[data["extra"][key]] = questionMediaFile;

            let name = key == "question_image" ? ".question-question-image" : ".question-question-video";
            let questionMediaPreview = wrapper.querySelector(name);

            // Save height of image/video
            data["extra"]["height"] = questionMediaPreview.height;

            // Save border color
            if (questionMediaPreview.style.borderColor) {
                data["extra"]["border"] = questionMediaPreview.style.borderColor;
            }
        }
    }
    else {
        // Save height of existing image/video
        if (Object.hasOwn(data, "extra") && (Object.hasOwn(data["extra"], "question_image") || Object.hasOwn(data["extra"], "video"))) {
            let name = Object.hasOwn(data["extra"], "question_image") ? ".question-question-image" : ".question-question-video";
            let questionMediaPreview = wrapper.querySelector(name);
            data["extra"]["height"] = questionMediaPreview.height;
            if (questionMediaPreview.style.borderColor) {
                data["extra"]["border"] = questionMediaPreview.style.borderColor;
            }
        }
    }

    // Save answer image
    if (answerMediaInput.files.length == 1) {
        let answerMediaFile = answerMediaInput.files[0];
        if (imageFileTypes.includes(answerMediaFile.type)) {
            data["extra"]["answer_image"] = getUniqueFilename(answerMediaFile.name.split(".")[0]);
            questionMedia[data["extra"]["answer_image"]] = answerMediaFile;
        }
    }

    if (questionDataQuestions.length == question) {
        questionDataQuestions.push(data);
    }
    else {
        questionDataQuestions[question] = data;
    }
}

function resizeRoundWrappers(round, orientation) {
    let wrapper = round == null ? null : document.querySelector(`.question-pack-round-wrapper-${round}`);
    let roundWrappers = document.querySelectorAll(".question-pack-round-wrapper");

    if (orientation == "width" || orientation == "both") {
        let resize = true;
        if (wrapper != null) {
            wrapper.style.width = "auto";
            if (wrapper.dataset["width"] < wrapperWidth - 15 || wrapper.dataset["width"] > wrapperWidth + 15) {
                wrapper.dataset["width"] = wrapper.getBoundingClientRect().width;
                wrapper.style.width = wrapperWidth + "px";
                resize = false;
            }
        }
        if (resize) {
            roundWrappers.forEach((elem) => {
                elem.style.width = "auto";
                elem.dataset["width"] = elem.getBoundingClientRect().width;
            });

            let maxWidth = 0;
            roundWrappers.forEach((elem) => {
                let rect = elem.getBoundingClientRect();
                if (rect.width > maxWidth) {
                    maxWidth = rect.width;
                }
            });

            wrapperWidth = maxWidth;

            roundWrappers.forEach((elem) => {
                elem.style.width = maxWidth + "px";
            });
        }
    }
    if (orientation == "height" || orientation == "both") {
        let resize = true;
        if (wrapper != null) {
            wrapper.style.height = "auto";
            if (wrapper.dataset["height"] != wrapperHeight) {
                wrapper.dataset["height"] = wrapper.getBoundingClientRect().height;
                wrapper.style.height = wrapperHeight + "px";
                resize = false;
            }
        }
        if (resize) {
            roundWrappers.forEach((elem) => {
                elem.style.height = "auto";
                elem.dataset["height"] = elem.getBoundingClientRect().height;
            });

            let maxHeight = 0;
            roundWrappers.forEach((elem) => {
                let rect = elem.getBoundingClientRect();
                if (rect.height > maxHeight) {
                    maxHeight = rect.height;
                }
            });

            wrapperHeight = maxHeight;

            roundWrappers.forEach((elem) => {
                elem.style.height = maxHeight + "px";
            });
        }
    }
}

function addQuestion(value, roundId, categoryId, questionId, wrapper) {
    if (questionId == 0) {
        questionData["rounds"][roundId]["categories"][categoryId]["questions"] = [];
    }

    let questionWrapper = document.createElement("div");
    questionWrapper.classList.add("question-pack-question-wrapper");
    questionWrapper.classList.add(`question-pack-question-wrapper-${questionId}`);
    questionWrapper.onclick = function() {
        showQuestionView(roundId, categoryId, questionId);
    }

    let deleteBtn = document.createElement("button");
    deleteBtn.className = "question-pack-delete-question-btn delete-button";
    deleteBtn.innerHTML = "&times;";
    deleteBtn.onclick = function(event) {
        deleteQuestion(event, roundId, categoryId, questionId);
        event.stopPropagation();
    };

    let questionElem = document.createElement("input");
    questionElem.value = value;
    questionElem.classList.add("question-pack-question-name");
    questionElem.classList.add(`question-pack-question-name-${questionId}`);
    questionElem.readonly = true;

    questionWrapper.appendChild(deleteBtn);
    questionWrapper.appendChild(questionElem);

    wrapper.appendChild(questionWrapper);

    resizeRoundWrappers(roundId, "height");
}

function deleteQuestion(event, roundId, categoryId, questionId) {
    event.stopPropagation();

    if (!confirm("Are you sure you want to delete this question?")) {
        return;
    }

    let roundWrapper = document.querySelector(`.question-pack-round-wrapper-${roundId} > .question-pack-round-body`);
    let categoryWrapper = roundWrapper.querySelector(`.question-pack-category-wrapper-${categoryId} > .question-pack-category-body`);
    let questionElem = categoryWrapper.querySelector(`div > .question-pack-question-wrapper-${questionId}`);

    if (questionElem != null) {
        categoryWrapper.removeChild(questionElem.parentElement);
        let dataForQuestion = questionData["rounds"][roundId]["categories"][categoryId]["questions"][questionId];
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
    resizeRoundWrappers(roundId, "height");
}

function syncCategoryData(roundId, categoryId) {
    let roundWrapper = document.querySelector(`.question-pack-round-wrapper-${roundId}`);
    let categoryWrapper = roundWrapper.querySelector(`.question-pack-category-wrapper-${categoryId}`);
    let name = categoryWrapper.querySelector(".question-pack-category-name").value;
    let includeFinale = document.getElementById("question-pack-finale").checked;
    let bgImageInput = categoryWrapper.querySelector(".question-bg-image-input");

    let questionDataCategories = questionData["rounds"][roundId]["categories"];

    let data;
    if (categoryId < questionDataCategories.length) {
        data = questionDataCategories[categoryId];
        data["name"] = name;
    }
    else {
        data = {
            "name": name,
            "order": categoryId,
            "buzz_time": defaultBuzzTime,
            "questions": [],
        }
    }

    // Save background image
    if (bgImageInput.files.length == 1) {
        let bgMediaFile = bgImageInput.files[0];
        if (imageFileTypes.includes(bgMediaFile.type)) {
            data["bg_image"] = getUniqueFilename(bgMediaFile.name.split(".")[0]);
            questionMedia[data["bg_image"]] = bgMediaFile;
        }
    }

    let defaultBuzzTime = includeFinale && roundId == questionData["rounds"].length - 1 ? 60 : 10;

    if (questionDataCategories.length == categoryId) {
        questionDataCategories.push(data);
    }
    else {
        questionDataCategories[categoryId] = data;
    }
}

function addCategory(roundId) {
    // Add new category for given round
    let roundWrapper = document.querySelector(`.question-pack-round-wrapper-${roundId}`);
    let roundBody = roundWrapper.querySelector(".question-pack-round-body");

    let category = getNextId(roundId);
    let categoryNum = roundWrapper.querySelectorAll(".question-pack-category-wrapper").length;
    if (categoryNum == 0) {
        questionData["rounds"][roundId]["categories"] = [];
        let placeholder = roundWrapper.querySelector(".question-pack-categories-placeholder");
        placeholder.classList.add("d-none");

        let addCategoryBtn = roundWrapper.querySelector(".question-pack-add-category-btn");
        addCategoryBtn.classList.remove("d-none");
    }

    let categoryElem = document.createElement("div");
    categoryElem.classList.add("question-pack-category-wrapper");
    categoryElem.classList.add(`question-pack-category-wrapper-${category}`);

    let header = document.createElement("div");
    header.className = "question-pack-category-header";

    let deleteBtn = document.createElement("button");
    deleteBtn.className = "question-pack-delete-category-btn delete-button";
    deleteBtn.innerHTML = "&times;";
    deleteBtn.onclick = function(event) {
        deleteCategory(event, roundId, category);
    }

    let input = document.createElement("input");
    input.classList.add("question-pack-category-name");
    input.onchange = function() {
        syncCategoryData(roundId, category);
        dataChanged();
    };

    header.appendChild(deleteBtn);
    header.appendChild(input);

    let dataDiv = document.createElement("div");
    dataDiv.className = "question-pack-category-body";

    let addQuestionBtn = document.createElement("button");
    addQuestionBtn.textContent = "+";
    addQuestionBtn.classList.add("question-pack-add-question-btn");
    addQuestionBtn.onclick = function() {
        createQuestionView(roundId, category);
    };

    categoryElem.appendChild(header);
    categoryElem.appendChild(dataDiv);
    categoryElem.appendChild(addQuestionBtn);

    roundBody.appendChild(categoryElem);

    input.focus();

    syncCategoryData(roundId, category)
    dataChanged();

    resizeRoundWrappers(roundId, "width");
}

function deleteCategory(event, roundId, categoryId) {
    event.stopPropagation();

    if (!confirm("Are you sure you want to delete this category and all its data?")) {
        return;
    }

    let roundElem = document.querySelector(`.question-pack-round-wrapper-${roundId} > .question-pack-round-body`);
    let categoryElem = roundElem.querySelector(`.question-pack-category-wrapper-${categoryId}`);

    if (categoryElem != null) {
        roundElem.removeChild(categoryElem);

        let dataForCategory = questionData["rounds"][roundId]["categories"][categoryId];
        
        if (Object.hasOwn(dataForCategory, "bg_image")) {
            questionMedia[dataForCategory["bg_image"]] = null;
        }

        dataForCategory["deleted"] = true;

        if (roundElem.children.length == 0) {
            let placeholder = roundWrapper.querySelector(".question-pack-categories-placeholder");
            placeholder.classList.remove("d-none");

            let addCategoryBtn = roundWrapper.querySelector(".question-pack-add-category-btn");
            addCategoryBtn.classList.add("d-none");
        }
    }

    dataChanged();
    resizeRoundWrappers(roundId, "width");
}

function syncRoundData(roundId) {
    let wrapper = document.querySelector(`.question-pack-round-wrapper-${roundId}`);
    let name = wrapper.querySelector(".question-pack-round-name").value;

    let questionDataRounds = questionData["rounds"];
    if (questionDataRounds.length == roundId) {
        questionDataRounds.push({"name": name, "round": roundId, "categories": []});
    }
    else {
        questionDataRounds[roundId]["name"] = name;
        questionDataRounds[roundId]["round"] = roundId;
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
    roundElem.dataset["height"] = "0";
    roundElem.dataset["width"] = "0";

    let headerDiv = document.createElement("div");
    headerDiv.className = "input-field";

    let label = document.createElement("label");
    label.className = "question-pack-round-name-label";
    label.for = `round-name-${round}`;
    label.textContent = "Round Name"

    let input = document.createElement("input");
    input.classList.add("question-pack-round-name");
    input.name = `round-name-${round}`
    input.value = `Round ${roundNum + 1}`;
    input.onchange = function() {
        syncRoundData(round);
        dataChanged();
    };

    headerDiv.appendChild(label);
    headerDiv.appendChild(input);

    let placeholderBtn = document.createElement("button");
    placeholderBtn.textContent = "Click here to add a category";
    placeholderBtn.classList = "question-pack-categories-placeholder";
    placeholderBtn.onclick = function() {
        addCategory(round);
    }

    let dataDiv = document.createElement("div");
    dataDiv.className = "question-pack-round-body";

    roundElem.appendChild(headerDiv);
    roundElem.appendChild(dataDiv);
    roundElem.appendChild(placeholderBtn);

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

    resizeRoundWrappers(round, "both");
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

function syncPackLanguage() {
    let language = document.getElementById("question-pack-language").value;
    questionData["language"] = language;
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
    let duration;
    if (error) {
        popup.classList.add("popup-error");
        popup.classList.remove("popup-success");
        duration = 10;
    }
    else {
        popup.classList.add("popup-success");
        popup.classList.remove("popup-error");
        duration = 6;
    }

    popup.textContent = text;
    popup.style.animationName = null;
    popup.offsetHeight;
    popup.style.animationDuration = `${duration}s`;
    popup.style.animationName = "popup-animate";

    setTimeout(function() {
        popup.classList.add("d-none");
    }, duration * 1000);
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
        if (typeof(a) == "object" && Object.hasOwn(a, "status")) {
            response = a;
        }
        else {
            response = c;
        }

        let contentType = response.getResponseHeader("Content-Type");

        let error = response.status != 200;
        if (!error) {
            showPopup("Question pack saved successfully.", false)
        }
        else if (contentType.startsWith("text/plain") || contentType.startsWith("text/raw")) {
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

function getSpecificParent(element, parentClass) {
    while (element != null && !element.classList.contains(parentClass)) {
        element = element.parentElement;
    }

    return element;
}

function setDoBuzzTime(event) {
    let wrapper = getSpecificParent(event.target, "question-view-wrapper");

    let checked = wrapper.querySelector(".question-do-buzz-countdown").checked;
    let countdownWrapper = wrapper.querySelector(".question-countdown-wrapper");

    if (checked) {
        countdownWrapper.classList.remove("d-none");
    }
    else {
        countdownWrapper.classList.add("d-none");
    }
}

function addAnswerChoice(event) {
    let wrapper = getSpecificParent(event.target, "question-view-wrapper");
    let choicesWrapper = wrapper.querySelector(".question-choices-wrapper");

    let choices = wrapper.querySelectorAll(".question-choice-entry").length;

    let choiceEntry = document.createElement("div");
    choiceEntry.className = `question-choice-${choices + 1} question-choice-entry question-editable`;

    let deleteBtn = document.createElement("button");
    deleteBtn.innerHTML = "&times";
    deleteBtn.onclick = deleteAnswerChoice

    let paragraph = document.createElement("p");

    let choiceNum = document.createElement("span");
    choiceNum.className = "question-choice-number";
    choiceNum.textContent = `${choices + 1}:`;

    let choiceText = document.createElement("input");
    choiceText.className = "question-choice-text question-editable";
    choiceText.placeholder = "Choice Text Here";

    paragraph.appendChild(choiceNum);
    paragraph.appendChild(choiceText);

    choiceEntry.appendChild(deleteBtn);
    choiceEntry.appendChild(paragraph);

    choicesWrapper.insertBefore(choiceEntry, choicesWrapper.lastElementChild);
}

function deleteAnswerChoice(event) {
    let wrapper = getSpecificParent(event.target, "question-view-wrapper");
    let choiceEntry = event.target.parentElement;
    let choicesWrapper = choiceEntry.parentElement;

    choicesWrapper.removeChild(choiceEntry);

    let choices = choicesWrapper.querySelectorAll(".question-choice-entry");
    if (choices.length == 0) {
        choicesWrapper.querySelector(".question-multiple-choice-checkbox").checked = false;
        wrapper.querySelector(".question-choices-indicator").classList.add("d-none");
    }
    else {
        choices.forEach((elem, index) => {
            let choiceNum = elem.querySelector(".question-choice-number");
            choiceNum.textContent = `${index + 1}:`
        });
    }
}

function validateAndGetMediaFile(files) {
    if (files.length != 1) {
        return null;
    }

    let file = files[0];
    if (!imageFileTypes.includes(file.type) && !videoFileTypes.includes(file.type)) {
        alert("Invalid file type.");
        return null;
    }

    return file;
}

function setBackgroundImage(event, roundId, categoryId) {
    let file = validateAndGetMediaFile(event.target.files);
    if (file != null) {
        const fileSrc = URL.createObjectURL(file);
        let roundWrapper = document.querySelector(`.question-pack-round-wrapper-${roundId} > .question-pack-round-body`);
        let categoryWrapper = roundWrapper.querySelector(`.question-pack-category-wrapper-${categoryId} > .question-pack-category-body`);
        let bgImageElements = categoryWrapper.querySelectorAll(".bg-image");
        bgImageElements.forEach(elem => {
            elem.style.backgroundImage = `url(${fileSrc})`;
        });
    }

    syncCategoryData(roundId, categoryId);
}

function openBackgroundImageInput(event) {
    let wrapper = getSpecificParent(event.target, "question-pack-question-view");
    wrapper.querySelector('.question-bg-image-input').click();
}

function getDefaultMediaHeight(wrapper) {
    let isMultipleChoice = wrapper.querySelector(".question-multiple-choice-checkbox").checked;
    if (isMultipleChoice) {
        return SMALL_MEDIA_HEIGHT;
    }

    return REGULAR_MEDIA_HEIGHT;
}

function resizeMedia(wrapper) {
    let newHeight = getDefaultMediaHeight(wrapper);

    let questionImage = wrapper.querySelector(".question-question-image");
    if (questionImage != null) {
        questionImage.style.height = newHeight + "px";
    }

    let video = wrapper.querySelector(".question-question-video");
    if (video != null) {
        video.style.height = newHeight + "px";
    }

    let answerImage = wrapper.querySelector(".question-answer-image");
    if (answerImage != null) {
        answerImage.style.height = newHeight + "px";
    }
}

function setMultipleChoice(event) {
    let wrapper = getSpecificParent(event.target, "question-view-wrapper");

    let checked = wrapper.querySelector(".question-multiple-choice-checkbox").checked;
    let choicesWrapper = wrapper.querySelector(".question-choices-wrapper");
    let choicesIndicator = wrapper.querySelector(".question-choices-indicator");
    let choices = wrapper.querySelectorAll(".question-choice-entry").length;

    if (checked) {
        if (choices == 0) {
            addAnswerChoice(event);
        }
        choicesIndicator.classList.remove("d-none");
        choicesWrapper.classList.remove("d-none");
    }
    else {
        choicesWrapper.classList.add("d-none");
        choicesIndicator.classList.add("d-none");
    }

    resizeMedia(wrapper);
}

function showMediaPreview(wrapper, file, mediaKey) {
    let previewWrapper = wrapper.querySelector(".drag-target-preview-wrapper");
    let header = wrapper.querySelector(".drag-target-tooltip");

    previewWrapper.innerHTML = "";
 
    let mediaElem;
    if (imageFileTypes.includes(file.type)) {
        mediaElem = document.createElement("img");
        mediaElem.className = `question-${mediaKey}-image question-editable`;
    }
    else {
        let video = document.createElement("video");
        mediaElem = document.createElement("source");

        video.className = "question-question-video question-editable";
        mediaElem.type = file.type;
    }

    const fileSrc = URL.createObjectURL(file);
    mediaElem.src = fileSrc;
    let outerWrapper = getSpecificParent(wrapper, "question-view-wrapper");
    mediaElem.style.height = getDefaultMediaHeight(outerWrapper) + "px";

    wrapper.classList.remove("target-empty");

    previewWrapper.appendChild(mediaElem);

    let mediaButtons = wrapper.querySelectorAll(".media-control-btn");
    mediaButtons.forEach((elem) => {
        elem.classList.remove("d-none");
    });

    previewWrapper.classList.remove("d-none");
    header.classList.add("d-none");
}

function openMediaInput(event) {
    if (event.target.classList.contains("media-control-btn")) {
        return;
    }

    let target = getSpecificParent(event.target, "media-drag-target");
    let input = target.querySelector(".drag-input");
    input.click();
}

function mediaFileSelected(event, mediaKey) {
    let file = validateAndGetMediaFile(event.target.files);

    if (file != null) {
        showMediaPreview(event.target.parentElement, file, mediaKey);
    }
    else {
        event.target.files = new FileList();
    }
}

function getFileExtension(fileType) {
    if (fileType == "image/jpeg" || fileType == "image/jpg") {
        return "jpg";
    }
    if (fileType == "image/apng" || fileType == "image/png") {
        return "png";
    }
    
    let validTypes = Array.from(imageFileTypes).concat(videoFileTypes);
    for (let validType of validTypes) {
        if (fileType == validType) {
            if (fileType == "image/jpeg" || fileType == "image/pjpeg") {
                return "jpg";
            }
            if (fileType == "image/apng") {
                return "png";
            }

            return fileType.replace("image/", "");
        }
    }

    return null;
}

function getRandomFilename(contentType) {
    let filename = "";
    for (let i = 0; i < 16; i++) {
        let index = Math.floor(Math.random() * letters.length);
        filename += letters[index];
    }
    const fileExt = getFileExtension(contentType);

    if (fileExt == null) {
        console.warn("File extension is null for", contentType);
        return null;
    }

    return filename + "." + fileExt;
}

function handleURLDataTransfers(event) {
    return new Promise((resolve, reject) => {
        let processedItems = 0;

        function rejectIfDone() {
            processedItems += 1;
            if (processedItems == event.dataTransfer.items.length) {
                reject();
            }
        }

        function processURL(dataURL) {
            return new Promise((resolve, reject) => {
                const client = new XMLHttpRequest();
    
                let url = `${getBaseURL()}/jeoparty/pack/fetch?url=${encodeURI(dataURL)}`
    
                client.open("GET", url, true);
                client.responseType = "blob";
                client.send();
    
                // Download the image/video and see if the content type is appropriate
                client.onreadystatechange = function() {
                    if(this.readyState == this.DONE) {    
                        if (this.status != 200) {
                            reject();
                            return;
                        }
    
                        const contentType = client.getResponseHeader("Content-Type");
                        const filename = getRandomFilename(contentType);
    
                        if (filename == null) {
                            console.warn("File extension is null for", contentType);
                            reject();
                            return;
                        }
    
                        let file = new File([this.response], filename, {type: contentType});
    
                        dataTransfer = new DataTransfer();
                        dataTransfer.items.add(file);
                        const fileList = dataTransfer.files;
    
                        let validatedFile = validateAndGetMediaFile(fileList);
                        if (validatedFile != null) {
                            resolve(fileList);
                        }
                    }
                }
            });
        }

        for (const item of event.dataTransfer.items) {
            item.getAsString((s) => console.log(item.kind, item.type, s));
    
            if (item.kind != "string") {
                rejectIfDone();
                continue;
            }
    
            const isHtml = item.type.match(/^text\/html/);
            const isURL = item.type.match(/^text\/uri-list/);

            if (isHtml || isURL) {
                item.getAsString((data) => {
                    let dataURL = null;
                    if (isHtml) {
                        let div = document.createElement("div");
                        div.innerHTML = data;
                        let imgElem = div.querySelector("a > img");
                        if (imgElem != null) {
                            dataURL = imgElem.src;
                        }
                    }
                    else {
                        dataURL = data;
                    }

                    if (dataURL == null) {
                        rejectIfDone();
                        return;
                    }

                    processURL(dataURL).then((result) => {
                        resolve(result);
                    }, rejectIfDone);
                });
            }
        }
    });
}

function mediaDragDropped(event, mediaKey) {
    event.preventDefault();
    
    let wrapper = getSpecificParent(event.target, "media-drag-target");
    wrapper.classList.remove("media-drag-hover");

    let loadingWrapper = wrapper.querySelector(".drag-target-loading");
    loadingWrapper.classList.remove("d-none");

    let input = wrapper.querySelector(".drag-input");
    let file = validateAndGetMediaFile(event.dataTransfer.files);
    if (file != null) {
        // If we dragged a file, set it directly and return
        input.files = event.dataTransfer.files;
        loadingWrapper.classList.add("d-none");
        showMediaPreview(wrapper, file, mediaKey);
        return;
    }

    // Otherwise, check to see if we dragged an image/video from a URL
    handleURLDataTransfers(event, wrapper, mediaKey).then((fileList) => {
        input.files = fileList;
        loadingWrapper.classList.add("d-none");
        showMediaPreview(wrapper, fileList[0], mediaKey);
    }, () => {
        loadingWrapper.classList.add("d-none");
        if (preview.classList.contains("d-none")) {
            header.classList.remove("d-none");
        }
        alert("Invalid file type.");
    });
}

function mediaDragEnter(event) {
    let wrapper = getSpecificParent(event.target, "media-drag-target");

    let header = wrapper.querySelector(".drag-target-tooltip");
    header.classList.add("d-none");

    wrapper.classList.add("media-drag-hover");
}

function mediaDragLeave(event) {
    let wrapper = getSpecificParent(event.target, "media-drag-target");

    let header = wrapper.querySelector(".drag-target-tooltip");
    let preview = wrapper.querySelector(".drag-target-preview-wrapper");
    if (preview.classList.contains("d-none")) {
        header.classList.remove("d-none");
    }

    wrapper.classList.remove("media-drag-hover");
}

function getMedia(wrapper) {
    return wrapper.querySelector(".question-media");
}

function _maximizeMedia(wrapper, media, maximize=true) {
    let questionHeader = wrapper.querySelector(".question-question-header");
    let categoryHeader = wrapper.querySelector(".question-category-header");

    let height;
    if (maximize && !media.classList.contains("media-maximized")) {
        // Maximize media
        media.classList.add("media-maximized");
        height = MAXIMIZED_MEDIA_HEIGHT;
        questionHeader.classList.add("d-none");
        categoryHeader.classList.add("d-none");
    }
    else if (!maximize && media.classList.contains("media-maximized")) {
        // Minimize media
        media.classList.remove("media-maximized");
        height = REGULAR_MEDIA_HEIGHT;
        questionHeader.classList.remove("d-none");
        categoryHeader.classList.remove("d-none");
    }
    else {
        return;
    }

    media.style.height = height + "px";

    let answerImage = wrapper.querySelector(".question-answer-image");
    if (answerImage != null) {
        answerImage.style.height = height + "px";
    }
}

function maximizeMedia(event) {
    event.stopPropagation();

    let target = event.target;

    let outerWrapper = getSpecificParent(event.target, "question-view-wrapper");
    let wrapper = getSpecificParent(target, "media-drag-target");
    let media = getMedia(wrapper);

    if (media == null) {
        return;
    }

    _maximizeMedia(outerWrapper, media, !media.classList.contains("media-maximized"));

    if (!target.classList.contains("media-maximize-btn")) {
        target = target.parentElement;
    }

    let minimizeIcon = target.querySelector(".media-minimize-icon");
    let maximizeIcon = target.querySelector(".media-maximize-icon");

    if (minimizeIcon.classList.contains("d-none")) {
        minimizeIcon.classList.remove("d-none");
        maximizeIcon.classList.add("d-none");
    }
    else {
        minimizeIcon.classList.add("d-none");
        maximizeIcon.classList.remove("d-none");
    }
}

function deleteMedia(event) {
    event.stopPropagation();

    let outerWrapper = getSpecificParent(event.target, "question-view-wrapper");
    let wrapper = getSpecificParent(event.target, "media-drag-target");
    wrapper.classList.add("target-empty");

    let media = getMedia(wrapper);
    if (media != null && media.classList.contains("media-maximized")) { 
        _maximizeMedia(outerWrapper, media, false);
    }

    let previewWrapper = wrapper.querySelector(".drag-target-preview-wrapper");
    previewWrapper.innerHTML = "";
    previewWrapper.classList.add("d-none");

    let toolTip = wrapper.querySelector(".drag-target-tooltip");
    toolTip.classList.remove("d-none");

    let mediaInput = wrapper.querySelector(".drag-input");
    mediaInput.value = "";

    let mediaButtons = wrapper.querySelectorAll(".media-control-btn");
    mediaButtons.forEach((elem) => {
        elem.classList.add("d-none");
    });
}

function setMediaBorderColor(event) {
    event.stopPropagation();

    let wrapper = getSpecificParent(event.target, "media-drag-target");
    let media = getMedia(wrapper);
    media.classList.add("image-border");

    media.style.borderColor = event.target.value;
}

function showQuestionView(roundId, categoryId, questionId, show=true) {
    let frame = questionId == null ? null : getQuestionViewWrapper(roundId, categoryId, questionId);

    if (frame == null) {
        return;
    }

    if (show) {
        frame.classList.remove("d-none");

        setURLHash("question", `${roundId}-${categoryId}-${questionId}`);

        frame.querySelectorAll(".input-resizer").forEach((e) => {
            let jqElem = $(e);
            let jqParent = $(e.parentElement);

            let val = jqParent.find('.resize-target').val();
            if (!val) {
                val = jqParent.find('.resize-target').attr("placeholder");
            }
            jqElem.text(val);
            jqParent.find('.resize-target').width(jqElem.width() * 1.25 + 10);
        });
    }
    else {
        frame.classList.add("d-none");
        setURLHash("question", null);
    }
}

function orderQuestions(roundId, categoryId) {
    let roundWrapper = document.querySelector(`.question-pack-round-wrapper-${roundId} > .question-pack-round-body`);
    let categoryWrapper = roundWrapper.querySelector(`.question-pack-category-wrapper-${categoryId} > .question-pack-category-body`);

    let sortedElements = Array.from(categoryWrapper.children).sort(
        function(a, b) {
            let va = a.querySelector(".question-pack-question-name").value;
            let vb = b.querySelector(".question-pack-question-name").value;

            return va < vb ? -1 : va > vb ? 1 : 0;
        }
    )

    sortedElements.forEach((elem) => {
        categoryWrapper.appendChild(elem);
    })
}

function saveQuestion(roundId, categoryId, questionId) {
    const newQuestion = questionId == questionData["rounds"][roundId]["categories"][categoryId]["questions"].length;
    let viewWrapper = getQuestionViewWrapper(roundId, categoryId, questionId);
    let valueInput = viewWrapper.querySelector(".question-reward-span");

    if (newQuestion) {
        addQuestion(valueInput.value, roundId, categoryId, questionId, viewWrapper.parentElement);
    }
    else {
        let roundWrapper = document.querySelector(`.question-pack-round-wrapper-${roundId} > .question-pack-round-body`);
        let categoryWrapper = roundWrapper.querySelector(`.question-pack-category-wrapper-${categoryId} > .question-pack-category-body`);
        let questionElem = categoryWrapper.querySelector(`.question-pack-question-name-${questionId}`);

        questionElem.value = valueInput.value;
    }

    orderQuestions(roundId, categoryId);

    // Sync data and close view
    syncQuestionData(roundId, categoryId, questionId);
    dataChanged();
    showQuestionView(roundId, categoryId, questionId, false);
}

function createQuestionView(roundId, categoryId) {
    let questionId = getNextId(roundId, categoryId);

    let outerWrapper = document.createElement("div");

    let placeholder = document.querySelector(".question-pack-question-view-placeholder");
    let wrapper = placeholder.cloneNode(true);

    // Set question ID on the outer wrapper
    wrapper.classList.remove("question-pack-question-view-placeholder");
    wrapper.classList.add(`question-pack-question-view-${questionId}`);

    let bgImageElem = wrapper.querySelector(".bg-image");
    let categoryData = questionData["rounds"][roundId]["categories"][categoryId];
    if (Object.hasOwn(categoryData, "bg_image")) {
        bgImageElem.style.backgroundImage = `url(/static/${categoryData["bg_image"]})`;
    }

    let roundWrapper = document.querySelector(`.question-pack-round-wrapper-${roundId}`);
    let categoryWrapper = roundWrapper.querySelector(`.question-pack-category-wrapper-${categoryId} > .question-pack-category-body`);
    let questionWrappers = categoryWrapper.querySelectorAll(".question-pack-question-wrapper");
    let roundIndex = getElementIndex("question-pack-round-wrapper", roundId);

    // Set category name
    let categoryHeader = wrapper.querySelector(".question-category-span");
    categoryHeader.textContent = questionData["rounds"][roundId]["categories"][categoryId]["name"];

    // Set value of question
    let valueInput = wrapper.querySelector(".question-reward-span");
    let baseValue = 100 * (roundIndex + 1);
    let questionValue = baseValue;
    questionWrappers.forEach((elem, index) => {
        let value = elem.querySelector(".question-pack-question-name").value;
        if (value != baseValue * (index + 1)) {
            return;
        }

        questionValue += baseValue;
    });

    valueInput.value = questionValue;

    // Set buzz time
    let countdownText = wrapper.querySelector(".question-countdown-text");
    countdownText.value = questionData["rounds"][roundId]["categories"][categoryId]["buzz_time"];

    // Add onclick event to exit button
    let exitBtn = wrapper.querySelector(".question-pack-question-view-exit");
    exitBtn.onclick = function() {
        saveQuestion(roundId, categoryId, questionId);
    }

    // Add onchange event to background image input
    let bgImageInput = wrapper.querySelector(".question-bg-image-input");
    bgImageInput.onchange = function(event) {
        setBackgroundImage(event, roundId, categoryId);
    }

    outerWrapper.appendChild(wrapper);
    categoryWrapper.appendChild(outerWrapper);

    showQuestionView(roundId, categoryId, questionId);
}

$.ready(function() {
    $(function() {
        let resizers = $(".input-resizer");
    
        resizers.each((e) => $(e).text($(e.parentElement).find('.resize-target').val()));
        resizers.each((e) => $(e.parentElement).find('.resize-target').width($(e).width() * 1.25 + 10));
    }).on("input", function(event) {
        if (!event.target.classList.contains("input-resizer")) {
            return;
        }
    
        let e = $(event.target);
        let resizeTarget = $(event.target.nextElementSibling);
        e.text(resizeTarget.val());
        resizeTarget.width(e.width() * 1.25 + 10);
    });
});

document.addEventListener("DOMContentLoaded", function() {
    let mediaWrappers = document.querySelectorAll(".question-view-wrapper");
    mediaWrappers.forEach((elem) => {
        let media = getMedia(elem);
        if (media != null) {
            let prevHeight = Number.parseInt(window.getComputedStyle(media).height.replace("px", ""));

            if (prevHeight > REGULAR_MEDIA_HEIGHT) {
                _maximizeMedia(elem, media);
            }
        }
    });

    let roundWrappers = document.querySelectorAll(".question-pack-round-wrapper");
    roundWrappers.forEach((elem) => {
        let rect = elem.getBoundingClientRect();
        elem.dataset["width"] = rect.width;
        elem.dataset["height"] = rect.height;
    });

    let [questionView, roundView] = parseURLHash();

    roundWrappers.forEach((_, i) => {
        showRoundView(i);
        resizeRoundWrappers(i, "both");
    });

    showRoundView(roundView || 0);
    if (questionView != null) {
        showQuestionView(questionView[0], questionView[1], questionView[2], true);
    }
});