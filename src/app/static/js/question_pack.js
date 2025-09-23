var questionData = {};
var questionMedia = {};
var lastSaveState = null;

const REGULAR_MEDIA_HEIGHT = 420
const SMALL_MEDIA_HEIGHT = 256
const MAXIMIZED_MEDIA_HEIGHT = 760

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

function getQuestionViewWrapper(roundId, categoryId, questionId) {
    return document.querySelector(`.question-pack-round-wrapper-${roundId} .question-pack-category-wrapper-${categoryId} .question-pack-question-view-${questionId}`);
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
            data["extra"][key] = questionMediaFile.name.split(".")[0];
            questionMedia[data["extra"][key]] = questionMediaFile;

            // Save height of image/video
            let name = key == "question_image" ? ".question-question-image" : ".question-question-video";
            let questionMediaPreview = wrapper.querySelector(name);
            data["extra"]["height"] = questionMediaPreview.height;
        }
    }

    // Save answer image
    if (answerMediaInput.files.length == 1) {
        let answerMediaFile = answerMediaInput.files[0];
        if (imageFileTypes.includes(answerMediaFile.type)) {
            data["extra"]["answer_image"] = answerMediaFile.name.split(".")[0];
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

function addQuestion(value, round, category) {
    let roundElem = document.querySelector(`.question-pack-round-wrapper-${round} > .question-pack-round-body`);
    let categoryWrapper = roundElem.querySelector(`.question-pack-category-wrapper-${category} > .question-pack-category-body`);

    let question = getNextId(round, category);
    if (question == 0) {
        questionData["rounds"][round]["categories"][category]["questions"] = [];
    }

    let questionWrapper = document.createElement("div");
    questionWrapper.classList.add("question-pack-question-wrapper");
    questionWrapper.classList.add(`question-pack-question-wrapper-${question}`);
    questionWrapper.onclick = function() {
        showQuestionView(round, category, question);
    }

    let deleteBtn = document.createElement("button");
    deleteBtn.className = "question-pack-delete-question-btn delete-button";
    deleteBtn.innerHTML = "&times;";
    deleteBtn.onclick = function(event) {
        deleteQuestion(event, round, category, question);
    };

    let questionElem = document.createElement("input");
    questionElem.value = value;
    questionElem.classList.add("question-pack-question-name");
    questionElem.readonly = true;

    questionWrapper.appendChild(deleteBtn);
    questionWrapper.appendChild(questionElem);

    categoryWrapper.appendChild(questionWrapper);
}

function deleteQuestion(event, round, category, question) {
    event.stopPropagation();

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
        questionDataCategories.push({"name": name, "order": category, "buzz_time": 10, "questions": []});
    }
    else {
        questionDataCategories[category]["name"] = name;
        questionDataCategories[category]["order"] = category;
    }
}

function addCategory(round) {
    // Add new category for given round
    let roundWrapper = document.querySelector(`.question-pack-round-wrapper-${round}`);
    let roundBody = roundWrapper.querySelector(".question-pack-round-body");

    let category = getNextId(round);
    let categoryNum = roundWrapper.querySelectorAll(".question-pack-category-wrapper").length;
    if (categoryNum == 0) {
        questionData["rounds"][round]["categories"] = [];
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
        deleteCategory(event, round, category);
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
    dataDiv.className = "question-pack-category-body";

    let addQuestionBtn = document.createElement("button");
    addQuestionBtn.textContent = "+";
    addQuestionBtn.classList.add("question-pack-add-question-btn");
    addQuestionBtn.onclick = function() {
        createQuestionView(round, category);
    };

    categoryElem.appendChild(header);
    categoryElem.appendChild(dataDiv);
    categoryElem.appendChild(addQuestionBtn);

    roundBody.appendChild(categoryElem);

    syncCategoryData(round, category)
    dataChanged();
}

function deleteCategory(event, round, category) {
    event.stopPropagation();

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

            let addCategoryBtn = roundWrapper.querySelector(".question-pack-add-category-btn");
            addCategoryBtn.classList.add("d-none");
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
        if (typeof(a) == "object" && Object.hasOwn(a, "status")) {
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
    choiceText.value = "Choice Text Here";

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

function showMediaPreview(wrapper, fileSrc, fileType, mediaKey) {
    let previewWrapper = wrapper.querySelector(".drag-target-preview-wrapper");
    let header = wrapper.querySelector(".drag-target-tooltip");

    previewWrapper.innerHTML = "";
 
    let mediaElem;
    if (imageFileTypes.includes(fileType)) {
        mediaElem = document.createElement("img");
        mediaElem.className = `.question-${mediaKey}-image question-editable`;
    }
    else {
        let video = document.createElement("video");
        mediaElem = document.createElement("source");

        video.className = ".question-question-video question-editable";
        mediaElem.type = fileType;
    }

    mediaElem.src = fileSrc;
    let outerWrapper = getSpecificParent(wrapper, "question-view-wrapper");
    mediaElem.style.height = getDefaultMediaHeight(outerWrapper) + "px";

    wrapper.classList.remove("target-empty");

    previewWrapper.appendChild(mediaElem);

    let deleteBtn = wrapper.querySelector(".media-delete-btn");
    deleteBtn.classList.remove("d-none");

    let maximizeBtn = wrapper.querySelector(".media-maximize-btn");
    maximizeBtn.classList.remove("d-none");

    previewWrapper.classList.remove("d-none");
    header.classList.add("d-none");
}

function openMediaInput(event) {
    let target = getSpecificParent(event.target, "media-drag-target");
    let input = target.querySelector(".drag-input");
    input.click();
}

function validateAndGetFile(files, wrapper, mediaKey) {
    if (files.length != 1) {
        return null;
    }

    let file = files[0];
    if (mediaKey == "image" && !imageFileTypes.includes(file.type) || mediaKey == "video" && !videoFileTypes.includes(file.type)) {
        alert("Invalid file type.");
        return null;
    }

    showMediaPreview(wrapper, URL.createObjectURL(file), file.type, mediaKey);

    return file;
}

function mediaFileSelected(event, mediaKey) {
    let file = validateAndGetFile(event.target.files, event.target.parentElement, mediaKey);

    if (file == null) {
        event.target.files = [];
    }
}

function mediaDragDropped(event, mediaKey) {
    let input = event.target.querySelector(".drag-input");
    let file = validateAndGetFile(event.dataTransfer.files, event.target.parentElement, mediaKey);
    if (file == null) {
        return;
    }

    input.files = [file];
}

function mediaDragEnter(event) {
    let header = event.target.querySelector(".drag-target-tooltip");
    header.classList.add("d-none");
}

function mediaDragLeave(event) {
    let header = event.target.querySelector(".drag-target-tooltip");
    let preview = event.target.querySelector(".drag-target-preview-wrapper");
    if (preview.classList.contains("d-none")) {
        header.classList.remove("d-none");
    }
}

function getMedia(wrapper) {
    let media = wrapper.querySelector(".question-question-video");

    if (media == null) {
        media = wrapper.querySelector(".question-question-image");
    }

    return media;
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

    let wrapper = getSpecificParent(target, "question-view-wrapper");
    let media = getMedia(wrapper);

    if (media == null) {
        return;
    }

    _maximizeMedia(wrapper, media, !media.classList.contains("media-maximized"));

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

    let wrapper = outerWrapper.querySelector(".media-drag-target");
    wrapper.classList.add("target-empty");

    let media = getMedia(outerWrapper);
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

    let maximizeBtn = wrapper.querySelector(".media-maximize-btn");
    maximizeBtn.classList.add("d-none");
    event.target.classList.add("d-none");
}

function showQuestionView(roundId, categoryId, questionId, show=true) {
    let frame = questionId == null ? null : getQuestionViewWrapper(roundId, categoryId, questionId);

    if (show) {
        frame.classList.remove("d-none");

        window.location.hash = `#question_${roundId}-${categoryId}-${questionId}`;

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
        window.location.hash = "";
    }
}

function saveQuestion(roundId, categoryId, questionId) {
    const newQuestion = questionId == questionData["rounds"][roundId]["categories"][categoryId]["questions"].length;
    let wrapper = getQuestionViewWrapper(roundId, categoryId, questionId);
    let valueInput = wrapper.querySelector(".question-reward-span");

    if (newQuestion) {
        addQuestion(valueInput.value, roundId, categoryId);
    }

    // Sync data and close view
    syncQuestionData(roundId, categoryId, questionId);
    dataChanged();
    showQuestionView(roundId, categoryId, questionId, false);
}

function createQuestionView(roundId, categoryId) {
    let questionId = questionData["rounds"][roundId]["categories"][categoryId]["questions"].length;

    let placeholder = document.querySelector(".question-pack-question-view-placeholder");
    let wrapper = placeholder.cloneNode(true);

    // Set question ID on the outer wrapper
    wrapper.classList.remove("question-pack-question-view-placeholder");
    wrapper.classList.add(`question-pack-question-view-${questionId}`);

    let roundWrapper = document.querySelector(`.question-pack-round-wrapper-${roundId}`);
    let categoryWrapper = roundWrapper.querySelector(`.question-pack-category-wrapper-${categoryId}`);
    let questionIndex = categoryWrapper.querySelectorAll(".question-pack-question-wrapper").length;
    let roundIndex = getElementIndex("question-pack-round-wrapper", roundId);

    // Set category name
    let categoryHeader = wrapper.querySelector(".question-category-span");
    categoryHeader.textContent = questionData["rounds"][roundId]["categories"][categoryId]["name"];

    // Set value of question
    let valueInput = wrapper.querySelector(".question-reward-span");
    valueInput.value = 100 * (questionIndex + 1) * (roundIndex + 1);

    // Set buzz time
    let countdownText = wrapper.querySelector(".question-countdown-text");
    countdownText.value = questionData["rounds"][roundId]["categories"][categoryId]["buzz_time"];

    // Add onclick event to exit button
    let exitBtn = wrapper.querySelector(".question-pack-question-view-exit");
    exitBtn.onclick = function() {
        saveQuestion(roundId, categoryId, questionId);
    }

    categoryWrapper.appendChild(wrapper);

    showQuestionView(roundId, categoryId, questionId);
}

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

    showRoundView(0);
    if (window.location.hash) {
        if (!window.location.hash.startsWith("#question_")) {
            return;
        }

        let split = window.location.hash.replace("#question_", "").split("-");
        if (split.length == 3) {
            showQuestionView(split[0], split[1], split[2], true);
        }
    }
});