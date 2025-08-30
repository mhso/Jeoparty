var questionData = {};

function showRoundView(index) {
    let selectButtons = document.querySelectorAll(".question-pack-round-select-button");
    selectButtons.forEach((elem) => {
        elem.classList.remove("question-pack-round-selected");
    });

    selectButtons[index].classList.add("question-pack-round-selected");

    let roundWrappers = document.querySelectorAll(".question-pack-round-wrapper");
    roundWrappers.forEach((elem) => {
        elem.classList.add("d-none");
    });

    roundWrappers[index].classList.remove("d-none");
}

function dataChanged() {
    let saveBtn = document.getElementById("question-pack-save-all");
    saveBtn.disabled = false;
}

function saveData() {
    
}

function addQuestion() {
    let modal = document.getElementById("question-pack-modal");

    dataChanged();
}

function addTier() {
    // Add tier across all rounds
    dataChanged();
}

function addCategory() {
    // Add category across all rounds
    dataChanged();
}

function addRound() {
    // Add categories and tiers to new round
    dataChanged();
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

function openQuestionModal(round, category, tier) {
    let modal = document.getElementById("question-pack-modal");
    let saveBtn = document.getElementById("question-pack-modal-save-btn");

    let questionInput = document.getElementById("question-pack-modal-question");
    let answerInput = document.getElementById("question-pack-modal-answer");
    let multipleChoiceCheck = document.getElementById("question-pack-modal-multiple_choice");
    let choicesWrapper = document.getElementById("question-pack-modal-choices");
    let choicesInnerWrapper = document.querySelector("#question-pack-modal-choices > div");

    if (tier == null) {
        tier = questionData["rounds"][round][category]["tiers"]
        modal.dataset["questionId"] = null;

        questionInput.value = "";
        answerInput.value = "";
        multipleChoiceCheck.checked = false;
        choicesWrapper.classList.add("d-none");
        choicesInnerWrapper.innerHTML = "";

        saveBtn.onclick = function() {
            
        };
    }
    else {
        modal.dataset["questionId"] = data["question_id"];

        questionInput.value = data["question"];
        answerInput.value = data["answer"];
    }

    modal.classList.remove("d-none");

    if (newQuestion) {
        // Add question to list after modal is closed
    }
}

function closeQuestionModal() {
    document.getElementById("question-pack-modal").classList.remove("d-none");
}

function deleteQuestion() {
    let questionId = document.getElementById("question-pack-modal").dataset["questionId"];
}

document.addEventListener("DOMContentLoaded", function() {
    showRoundView();
});