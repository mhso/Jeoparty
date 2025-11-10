// Create socket bound to a namespace for a specific game ID.
// 'GAME_ID' is defined before this JS file is imported
const socket = io(`/${GAME_ID}`, {"transports": ["websocket", "polling"], "rememberUpgrade": true});
socket.on("connect_error", function(err) {
    console.error("Socket connection error:", err);
});

const TIME_FOR_ANSWERING = 6;
const TIME_FOR_DOUBLE_ANSWER = 10;
const TIME_FOR_WAGERING = 60;
const TIME_FOR_FINAL_ANSWER = 40;
const TIME_BEFORE_FIRST_TIP = 4;
const TIME_BEFORE_EXTRA_TIPS = 4;
const IMG_MAX_HEIGHT = 420;
const PRESENTER_ACTION_KEY = "Space"

var countdownInterval = null;
var countdownPaused = false;
var localeStrings;
var activeStage;
var activeAnswer;
var activeValue = null;
var answeringPlayer = null;
var activePlayers = {};
var questionAnswered = false;
var buzzInTime = 10;
var isDailyDouble = false;
var activePowerUp = null;
var hijackBonus = false;
var freezeTimeout = null;

let playerTurn = null;
var playerIds = [];
var playerNames = {};
var playerScores = {};
let playerColors = {};
let playersBuzzedIn = [];

function canPlayersBuzzIn() {
    return activeStage == "question" && !isDailyDouble;
}

function getBaseURL() {
    return window.location.protocol + "//" + window.location.hostname + ":" + window.location.port;
}

function getPresenterURL() {
    return `${getBaseURL()}/jeoparty/presenter`
}

function getSelectionURL() {
    return `${getPresenterURL()}/${GAME_ID}/selection`;
}

function getQuestionURL() {
    return `${getPresenterURL()}/${GAME_ID}/question`;
}

function getFinaleURL() {
    return `${getPresenterURL()}/${GAME_ID}/finale`;
}

function getEndscreenURL() {
    return `${getPresenterURL()}/${GAME_ID}/endscreen`;
}

function goToPage(url) {
    if (socket) {
        socket.close();
    }
    window.location.href = url;
}

function playCorrectSound() {
    let sound = document.getElementById("question-sound-correct");
    sound.play();
}

function playWrongSound() {
    let sounds = document.getElementsByClassName("question-sound-wrong");
    for (let i = 0; i < sounds.length; i++) {
        let sound = sounds.item(i);
        if (!sound.classList.contains("played")) {
            sound.play();
            sound.classList.add("played");
            return;
        }
    }
}

function placeAnswerImageIfPresent() {
    let img = document.getElementById("question-answer-image");

    function imgLoaded() {
        let width = img.getBoundingClientRect().width / 2;
        img.style.left = `calc(50% - ${width}px)`;
    }

    if (img != null) {
        if (img.complete) {
            imgLoaded();
        }
        else {
            img.addEventListener("load", imgLoaded)
        }
    }
}

function revealAnswerImageIfPresent() {
    let elem = document.getElementById("question-answer-image");
    if (elem != null) {
        elem.style.setProperty("display", "block");
        elem.style.setProperty("opacity", 1);
    }
}

function listenForBuzzIn() {
    if (Object.keys(activePlayers).length != 0) {
        socket.emit("enable_buzz", JSON.stringify(activePlayers));
    }
}

function disableBuzzIn() {
    socket.emit("disable_buzz");
}

function enablePowerUp(playerId, powerId) {
    socket.emit("enable_powerup", playerId, powerId);
}

function disablePowerUp(playerId=null, powerId=null) {
    socket.emit("disable_powerup", playerId, powerId);
}

function hideFreezeAnimation() {
    let freezeWrapper = document.querySelector(".question-countdown-frozen");
    freezeWrapper.style.transition = "opacity 2s";
    freezeWrapper.style.opacity = 0;
    setTimeout(function() {
        freezeWrapper.classList.add("d-none");
    }, 1000);
}

function undoAnswer(playerId, currAnswer=null) {
    console.log("Triggering undo for", playerId);
    let wrong = document.getElementById("question-answer-correct").classList.contains("d-none");

    let wrongElem = document.getElementById("question-answer-wrong");
    if (!wrongElem.classList.contains("d-none")) {
        wrongElem.classList.add("d-none");
        wrongElem.style.setProperty("opacity", 0);
    }

    stopCountdown();

    if (currAnswer != null) {
        activeAnswer = currAnswer;

        enabl
    }

    let value;
    if (wrong) {
        value = activeValue;
    }
    else {
        value = -activeValue;
    }

    socket.emit("undo_answer", playerId, value);
    updatePlayerScore(playerId, value);

    answeringPlayer = playerId;

    afterBuzzIn(playerId);
}

function isCtrlZHeld(event) {
    return event.ctrlKey && event.key == "z";
}

function afterQuestion() {
    const currAnswer = activeAnswer;
    const currPlayer = answeringPlayer;

    activeAnswer = null;
    hideTips();

    window.onkeydown = function(e) {
        // Undo answer if presenter pressed wrong button
        if (isCtrlZHeld(e)) {
            undoAnswer(currPlayer, currAnswer);
        }

        else if (e.code == PRESENTER_ACTION_KEY) {
            goToPage(getSelectionURL());
        }
    }
}

function afterAnswer() {
    // Reset who is answering
    answeringPlayer = null;
    setPlayerTurn(null, false);

    let buzzFeed = document.getElementById("question-game-feed");
    buzzFeed.classList.add("d-none");
    buzzFeed.getElementsByTagName("ul").item(0).innerHTML = "";

    if (activeAnswer == null) {
        // Question has been answered or time ran out
        if (!isDailyDouble) {
            disableBuzzIn();
        }
        return;
    }

    let videoElem = document.querySelector(".question-question-video");

    let delay = 4000;

    // Immediately allow other players to buzz in
    if (videoElem != null && !videoElem.ended) {
        videoElem.onended = afterShowQuestion;

        // Let players interrupt the video and buzz in early
        listenForBuzzIn();

        setTimeout(function() {
            // Resume playing video after a delay if no one has buzzed in
            if (answeringPlayer == null && activeAnswer != null) {
                hideAnswerIndicator();
                videoElem.play();
                videoElem.onended = afterShowQuestion;
            }
        }, delay);
    }
    else {
        questionAsked(delay);
    }
}

function updatePlayerScore(playerId, delta) {
    playerScores[playerId] += delta;
    let playerEntry = document.querySelector(`.footer-contestant-${playerId}`);
    let scoreElem = playerEntry.querySelector(".footer-contestant-entry-score");

    scoreElem.textContent = `${playerScores[playerId]} ${localeStrings["points"]}`;
}

function updatePlayerBuzzStats(playerId, hit) {
    let playerEntry = document.querySelector(`.footer-contestant-${playerId}`);
    let name = hit ? ".footer-contestant-entry-hits" : ".footer-contestant-entry-misses"
    let statElem = playerEntry.querySelector(name);

    let newValue = Number.parseInt(statElem.textContent) + 1;
    statElem.textContent = newValue.toString();
}

function correctAnswer() {
    // Disable all power-ups after question has been answered correctly
    disablePowerUp();
    activePowerUp = null;

    let elem = document.getElementById("question-answer-correct");

    let valueElem = elem.getElementsByClassName("question-answer-value").item(0);

    // Reduce the value of the question if tips are shown
    let shownTips = document.getElementsByClassName("tip-shown").length;
    activeValue *= (1 / 2 ** shownTips);

    // Reduce the value of the question by how few multiple choice answer are left
    let wrongAnswers = document.getElementsByClassName("question-answered-wrong").length;
    activeValue *= (1 / 2 ** wrongAnswers);

    if (hijackBonus) {
        activeValue *= 2;
    }

    activeValue = Math.ceil(activeValue);

    valueElem.textContent = `+${activeValue} ${localeStrings["points"]}`;

    revealAnswerImageIfPresent();

    elem.classList.remove("d-none");
    setTimeout(function() {
        elem.style.setProperty("opacity", 1);
        playCorrectSound();
    }, 100);

    // Add value to player score
    updatePlayerScore(answeringPlayer, activeValue);
    updatePlayerBuzzStats(answeringPlayer, true);

    if (playerTurn != answeringPlayer) {
        // Set player as having the turn, if they didn't already
        setPlayerTurn(answeringPlayer, true);
    }

    // Send update to server
    socket.emit("correct_answer", answeringPlayer, activeValue);

    // Move on to next question
    afterQuestion();
    afterAnswer();
}

function wrongAnswer(reason, questionOver=false) {
    // Add undo handler if presenter pressed wrong button
    const currPlayer = answeringPlayer;
    window.onkeydown = function(e) {
        if (isCtrlZHeld(e)) {
            undoAnswer(currPlayer);
        }
    }

    let outOfTime = questionOver && answeringPlayer == null;

    if (outOfTime) {
        // Disable all power-ups if time ran out
        disablePowerUp();
        activePowerUp = null;
    }

    let elem = document.getElementById("question-answer-wrong");
    let valueElem = elem.getElementsByClassName("question-answer-value").item(0);

    let reasonElem = document.getElementById("question-wrong-reason-text");
    reasonElem.textContent = reason;

    elem.classList.remove("d-none");
    setTimeout(function() {
        elem.style.setProperty("opacity", 1);
        playWrongSound();
    }, 100);

    if (answeringPlayer != null) {
        if (freezeTimeout != null) {
            clearTimeout(freezeTimeout);
            hideFreezeAnimation();
        }

        // Deduct points from player if someone buzzed in
        valueElem.textContent = `-${activeValue} ${localeStrings["points"]}`;
        updatePlayerScore(answeringPlayer, -activeValue);
        updatePlayerBuzzStats(answeringPlayer, false);

        // Send update to server
        socket.emit("wrong_answer", answeringPlayer, activeValue);

        // Disable the use of 'freeze' power up, enable the use of 'rewind'
        activePowerUp = null;
        enablePowerUp(answeringPlayer, "rewind");
    }

    if (Object.values(activePlayers).every(v => !v) || outOfTime) {
        // No players are eligible to answer, go to next question
        if (outOfTime) {
            valueElem.textContent = "";
        }

        revealAnswerImageIfPresent();

        let answerElem = document.getElementById("question-actual-answer");
        answerElem.classList.remove("d-none");

        afterQuestion();
    }
    afterAnswer();
}

function hideAnswerIndicator() {
    let correctElem = document.getElementById("question-answer-correct");
    if (!correctElem.classList.contains("d-none")) {
        correctElem.classList.add("d-none");
        correctElem.style.setProperty("opacity", 0);
    }

    let wrongElem = document.getElementById("question-answer-wrong");
    if (!wrongElem.classList.contains("d-none")) {
        wrongElem.classList.add("d-none");
        wrongElem.style.setProperty("opacity", 0);
    }
}

function keyIsNumeric(key, min, max) {
    let keys = Array.apply(null, Array(max - min + 1)).map(function (x, i) { return "" + (i + min); });
    return keys.includes(key);
}

function stopCountdown() {
    clearInterval(countdownInterval);
    countdownInterval = null;
    countdownPaused = false;

    let countdownElem = document.querySelector(".question-countdown-wrapper");
    if (!countdownElem.classList.contains("d-none")) {
        countdownElem.classList.add("d-none");
        countdownElem.style.opacity = 0;
    }
}

function pauseCountdown(paused) {
    if (countdownInterval != null) {
        countdownPaused = paused;
    }
}

function isQuestionMultipleChoice() {
    return document.getElementsByClassName("question-choice-entry").length > 0;
}

function answerQuestion(event) {
    if (keyIsNumeric(event.key, 1, 4)) {
        if (isQuestionMultipleChoice()) {
            // Highlight element as having been selected as the answer.
            const delay = 2500
            const elem = document.querySelector(".question-choice-" + event.key);
            const answerElem = elem.querySelector(".question-choice-text");
            elem.classList.add("question-answering");

            const timeoutId = setTimeout(function() {
                elem.classList.remove("question-answering");
                
                if (answerElem.textContent === activeAnswer) {
                    elem.classList.add("question-answered-correct");
                    correctAnswer();
                }
                else {
                    elem.classList.add("question-answered-wrong");
                    wrongAnswer(localeStrings["wrong_answer_given"], false);
                }
            }, delay);

            window.onkeydown = function(e) {
                if (isCtrlZHeld(e)) {
                    clearTimeout(timeoutId);

                    if (
                        elem.classList.contains("question-answered-correct")
                        || elem.classList.contains("question-answered-wrong")
                    ) {
                        return;
                    }

                    // Answer the question again after an undo
                    elem.classList.remove("question-answering");
                    window.onkeydown = answerQuestion
                }
            }
        }
        else {
            if (event.key == 1) {
                correctAnswer();
            }
            else {
                wrongAnswer(localeStrings["wrong_answer_given"], false);
            }
        }
    }
}

function setCountdownText(countdownText, seconds, maxSecs) {
    countdownText.textContent = (maxSecs - seconds);
}

function setCountdownBar(countdownBar, milis, green, red, maxMilis) {
    let width = (milis / maxMilis) * 100;
    countdownBar.style.width = width + "%";
    countdownBar.style.backgroundColor = "rgb(" + red.toFixed(0) + ", " + green.toFixed(0) + ", 0)";
}

function startCountdown(duration, callback=null) {
    let countdownWrapper = document.querySelector(".question-countdown-wrapper");
    if (countdownWrapper.classList.contains("d-none")) {
        countdownWrapper.classList.remove("d-none");
    }
    countdownWrapper.style.opacity = 1;
    let countdownBar = document.querySelector(".question-countdown-filled");
    let countdownText = document.querySelector(".question-countdown-text");

    let green = 255
    let red = 136;

    let secs = 0;
    let iteration = 0;
    let delay = 50;

    let totalSteps = (duration * 1000) / delay;
    let colorDelta = (green + red) / totalSteps;

    setCountdownText(countdownText, secs, duration);
    setCountdownBar(countdownBar, (secs * 1000) + (iteration * delay), green, red, duration * 1000);

    countdownPaused = false;

    countdownInterval = setInterval(function() {
        if (countdownPaused) {
            return;
        }

        iteration += 1;
        if (iteration * delay == 1000) {
            iteration = 0;
            secs += 1;
            setCountdownText(countdownText, secs, duration);
        }
        if (red < 255) {
            red += colorDelta;
        }
        else if (green > 0) {
            green -= colorDelta;
        }

        setCountdownBar(countdownBar, (secs * 1000) + (iteration * delay), green, red, duration * 1000);

        if (secs >= duration) {
            stopCountdown();
            if (callback != null) {
                callback();
            }
            else {
                wrongAnswer(localeStrings["wrong_answer_time"], true);
            }
        }
    }, delay);
}

function pauseVideo() {
    let videoElem = document.querySelector(".question-question-video");
    if (videoElem != null) {
        videoElem.onended = null;
        videoElem.pause();
    }
}

function startAnswerCountdown(duration) {
    startCountdown(duration, () => wrongAnswer(localeStrings["wrong_answer_time"], true));

    // Disable 'freeze' power-up one second before time expires
    freezeTimeout = setTimeout(function() {
        freezeTimeout = null;
        disablePowerUp(answeringPlayer, "freeze");
        hideFreezeAnimation();
    }, (duration - 1) * 1000);

    // Action key has to be pressed before an answer can be given (for safety)
    window.onkeydown = function(e) {
        if (e.code == PRESENTER_ACTION_KEY) {
            // Disable 'hijack' power-up for all and 'freeze' for the answering player
            // after an answer has been given
            disablePowerUp(null, "hijack");
            disablePowerUp(answeringPlayer, "freeze");

            // Pause video if one is playing
            pauseVideo();

            // Clear countdown
            stopCountdown();

            window.onkeydown = function(e) {
                answerQuestion(e);
            }
        }
    }
}

function addToGameFeed(text) {
    let wrapper = document.getElementById("question-game-feed");
    wrapper.classList.remove("d-none");

    let listParent = wrapper.getElementsByTagName("ul").item(0);

    let listElem = document.createElement("li");
    listElem.innerHTML = text;

    listParent.appendChild(listElem);
}

function addBuzzToFeed(playerId, timeTaken) {
    if (playersBuzzedIn.includes(playerId)) {
        return;
    }

    const buzzStr1 = localeStrings["game_feed_buzz_1"];
    const buzzStr2 = localeStrings["game_feed_buzz_2"];

    let name = playerNames[playerId];
    let color = playerColors[playerId];
    addToGameFeed(`<span style="color: ${color}; font-weight: 800">${name}</span> ${buzzStr1} ${timeTaken} ${buzzStr2}`);
}

function addPowerUseToFeed(playerId, powerId) {
    const powerStr1 = localeStrings["game_feed_power_1"];
    const powerStr2 = localeStrings["game_feed_power_2"];

    let name = playerNames[playerId];
    let color = playerColors[playerId];
    addToGameFeed(`<span color='${color}'>${name}</span> ${powerStr1} <strong>${powerId}</strong> ${powerStr2}!`);
}

function afterBuzzIn(playerId) {
    // Pause video if one is playing
    pauseVideo();

    // Clear buzz-in countdown.
    stopCountdown();

    // Clear previous anwer indicator (if it was shown)
    hideAnswerIndicator();

    // Show who was fastest at buzzing in
    setPlayerTurn(playerId, false);

    // Start new countdown for answering after small delay
    setTimeout(function() {
        startAnswerCountdown(TIME_FOR_ANSWERING);

        // Enable 'freeze' for player who buzzed
        enablePowerUp(playerId, "freeze");
    }, 500);
}

function playerBuzzedFirst(playerId) {
    if (activePowerUp != null && activePowerUp != "hijack") {
        return;
    }

    playersBuzzedIn.push(playerId);

    if (!activePlayers[playerId] || (answeringPlayer != null && activePowerUp != "hijack")) {
        return;
    }

    // Buzzer has been hit, let the player answer.
    answeringPlayer = playerId;
    activePlayers[playerId] = false;
    document.getElementById("question-buzzer-sound").play();
    setTimeout(function() {
        let playerSound = document.getElementById(`question-buzzer-${playerId}`);
        if (playerSound != null) {
            playerSound.play();
        }
    }, 600);

    afterBuzzIn(playerId);
}

function showPowerUpVideo(powerId) {
    return new Promise((resolve) => {
        let wrapper = document.getElementById("question-power-up-splash");
        wrapper.classList.remove("d-none");

        let video = document.getElementById(`question-power-up-video-${powerId}`);
        video.classList.remove("d-none");

        video.onended = function() {
            wrapper.classList.add("d-none");
            video.classList.add("d-none");
            resolve();
        };

        video.play();
    });
}

function onFreezeUsed() {
    clearInterval(freezeTimeout);
    pauseCountdown(true);
}

function afterFreezeUsed() {
    const opacity = 0.9;

    const fadeInDuration = 2;

    let freezeWrapper = document.querySelector(".question-countdown-frozen");
    freezeWrapper.classList.remove("d-none");
    freezeWrapper.style.transition = `opacity ${fadeInDuration}s`;
    freezeWrapper.style.opacity = opacity;

    setTimeout(function() {
        const duration = 38;
    
        freezeWrapper.offsetHeight; // Trigger reflow
        freezeWrapper.style.transition = `opacity ${duration}s`;
        freezeWrapper.style.opacity = 0;
    
        setTimeout(function() {
            if (answeringPlayer != null) {
                freezeWrapper.classList.add("d-none");
                pauseCountdown(false);
            }
        }, duration * 1000)
    }, fadeInDuration * 1000);

}

function onRewindUsed(playerId) {
    stopCountdown();

    // Refund the score the player lost on the previous answer
    socket.emit("rewind_used", playerId, activeValue); 
    answeringPlayer = playerId;
    updatePlayerScore(answeringPlayer, activeValue);
}

function afterRewindUsed() {
    afterBuzzIn(answeringPlayer);
}

function onHijackUsed() {
    pauseCountdown(true);

    // If question has not been asked yet, hijack gives bonus points
    hijackBonus = Object.keys(activePlayers).length == 0

    if (!hijackBonus && answeringPlayer != null) {
        stopCountdown();
    }
}

function afterHijackUsed(playerId) {
    activePlayers = {};

    playerIds.forEach((id) => {
        activePlayers[id] = false;
    });

    activePlayers[playerId] = true;

    if (!hijackBonus && answeringPlayer != null) {
        answeringPlayer = playerId;
        afterBuzzIn(playerId);
    }
    else {
        setPlayerTurn(playerId, false);
    }

    pauseCountdown(false);
}

function powerUpUsed(playerId, powerId) {
    activePowerUp = powerId;

    console.log(`Player ${playerNames[playerId]} used power '${powerId}'`);

    callback = null;
    if (powerId == "freeze") {
        onFreezeUsed();
        callback = afterFreezeUsed;
    }
    else if (powerId == "rewind") {
        onRewindUsed(playerId);
        callback = afterRewindUsed;
    }
    else {
        onHijackUsed();
        callback = () => afterHijackUsed(playerId);
    }

    addPowerUseToFeed(playerId, powerId);
    showPowerUpVideo(powerId, playerId).then(() => {
        if (callback) callback();
    });
    
    let powerIcon = document.querySelector(
        `.footer-contestant-${playerId} .footer-contestant-power-${powerId} > .footer-contestant-entry-power-used`
    );
    powerIcon.classList.remove("d-none");
}

function hideTips() {
    let tipElems = document.getElementsByClassName("question-tip-wrapper");
    for (let i = 0; i < tipElems.length; i++) {
        tipElems.item(i).classList.add("d-none");
    }
}

function showTip(index) {
    let tipElems = document.getElementsByClassName("question-tip-wrapper");
    if (index >= tipElems.length) {
        return;
    }

    delay = index == 0 ? TIME_BEFORE_FIRST_TIP : TIME_BEFORE_EXTRA_TIPS;
    setTimeout(function() {
        if (activeAnswer == null) {
            // Question is over, don't show tip
            return;
        }
        if (answeringPlayer != null) {
            // Player is answering, don't show more tips while they answer
            showTip(index);
            return
        }
    
        let tipElem = tipElems.item(index);
        tipElem.style.setProperty("opacity", 1);
        tipElem.classList.add("tip-shown");

        showTip(index + 1);
    }, delay * 1000);
}

function questionAsked(countdownDelay) {
    setTimeout(function() {
        if (!activeAnswer) {
            return;
        }

        if (answeringPlayer == null && canPlayersBuzzIn()) {
            hideAnswerIndicator();
            showTip(0);
            if (buzzInTime == 0) {
                // Question has no timer, contestants can take their time
                window.onkeydown = function(e) {
                    if (e.code == PRESENTER_ACTION_KEY) {
                        wrongAnswer(localeStrings["wrong_answer_cowards"], true);
                    }
                };
            }
            else {
                startCountdown(buzzInTime);
            }
        }
        else if (isDailyDouble || activePowerUp == "hijack") {
            let timeToAnswer = isDailyDouble ? TIME_FOR_DOUBLE_ANSWER : buzzInTime;
            startAnswerCountdown(timeToAnswer);
        }
        else if (activeStage == "finale_question") {
            // Go to finale screen after countdown is finished if it's round 3
            document.getElementById("question-finale-suspense").play();
            let url = getFinaleURL();
    
            startCountdown(TIME_FOR_FINAL_ANSWER, () => goToPage(url));

            // Allow us to override the countdown if people are done answering
            setTimeout(function() {
                window.onkeydown = function(e) {
                    if (e.code == PRESENTER_ACTION_KEY) {
                        stopCountdown();
                        goToPage(url);
                    }
                }
            }, 2000);
        }
    }, countdownDelay);

    if (canPlayersBuzzIn()) {
        // Enable participants to buzz in if we are in regular rounds
        listenForBuzzIn();
    }
    else if (isDailyDouble) {
        answeringPlayer = playerTurn;
        setPlayerTurn(answeringPlayer, false);
    }
}

function showAnswerChoice(index) {
    let choiceElem = document.querySelectorAll(".question-choice-entry")[index];
    choiceElem.style.opacity = 1;

    if (index == 3) {
        questionAsked(500);
    }
    else {
        window.onkeydown = function(e) {
            if (e.code == PRESENTER_ACTION_KEY) {
                showAnswerChoice(index + 1);
            }
        }
    }
}

function afterShowQuestion() {
    if (isQuestionMultipleChoice()) {
        window.onkeydown = function(e) {
            if (e.code == PRESENTER_ACTION_KEY) {
                showAnswerChoice(0);
            }
        }
    }
    else {
        questionAsked(500);
    }
}

function showImageOrVideo(elem) {
    if (elem.offsetHeight > IMG_MAX_HEIGHT) {
        document.querySelector(".question-category-header").style.display = "none";
        document.querySelector(".question-question-header").style.display = "none";
    }
    elem.style.opacity = 1;
}

function showQuestion() {
    if (Object.keys(activePlayers).length == 0) {
        playerIds.forEach((id) => {
            activePlayers[id] = !isDailyDouble;
        });
    }

    // Show the question, if it exists
    let questionElem = document.querySelector(".question-question-header");
    if (questionElem != null) {
        questionElem.style.opacity = 1;
    }

    let questionImage = document.querySelector(".question-question-image");
    let answerImage = document.querySelector(".question-answer-image");
    let videoElem = document.querySelector(".question-question-video");

    if (answerImage != null || videoElem != null) {
        // If there is an answer image, first show the question, then show
        // the image after pressing action key again. Otherwise show image instantly
        window.onkeydown = function(e) {
            if (e.code == PRESENTER_ACTION_KEY) {
                if (questionImage != null) {
                    showImageOrVideo(questionImage);
                    afterShowQuestion();
                }
                else {
                    showImageOrVideo(videoElem);
                    videoElem.play();
                    videoElem.onended = afterShowQuestion;

                    if (canPlayersBuzzIn()) {
                        // Let players interrupt the video and buzz in early
                        listenForBuzzIn();
                    }
                }
            }
        }
    }
    else {
        // If there is no answer image, either show answer choices if question
        // is multiple choice, otherwise show question image/video
        if (isQuestionMultipleChoice()) {
            if (questionImage != null) {
                showImageOrVideo(questionImage);
            }
            afterShowQuestion();
        }
        else {
            if (questionImage != null) {
                showImageOrVideo(questionImage);
            }
            window.onkeydown = function(e) {
                if (e.code == PRESENTER_ACTION_KEY) {
                    afterShowQuestion();
                }
            }
        }
    }
}

function afterDailyDoubleWager(amount) {
    let wrapper = document.getElementById("question-wager-wrapper");
    if (wrapper.classList.contains("d-none")) {
        return;
    }
    activeValue = amount;
    wrapper.classList.add("d-none");
    showQuestion();
}

function scaleAnswerChoices() {
    let choiceElems = document.getElementsByClassName("quiz-answer-entry");
    for (let i = 0; i < choiceElems.length; i++) {
        let wrapper = choiceElems.item(i)
        let textElem = wrapper.getElementsByTagName("p").item(0);
        if (textElem.offsetHeight > wrapper.offsetHeight * 0.75) {
            wrapper.style.fontSize = "16px";
            if (textElem.offsetHeight > wrapper.offsetHeight * 0.75) {
                wrapper.style.paddingTop = "4px";
            }
            else {
                wrapper.style.paddingTop = "16px";
            }
        }
    }
}

function initialize(playerData, stage, localeData, answer=null, value=null, buzzTime=10, dailyDouble=false) {
    playerData.forEach((data) => {
        let playerId = data["id"];
        playerIds.push(playerId);
        playerScores[playerId] = data["score"];
        playerNames[playerId] = data["name"];
        playerColors[playerId]= data["color"];

        if (data["has_turn"]) {
            playerTurn = data["id"];
        }
    });

    localeStrings = localeData;
    activeStage = stage;
    activeAnswer = answer;
    activeValue = value;
    buzzInTime = buzzTime;
    isDailyDouble = dailyDouble;
}

function goToQuestion(div, questionId, isDouble) {
    if (div.classList.contains("inactive")) {
        return;
    }

    if (div.tagName == "SPAN") {
        div = div.parentElement;
    }
    else if (div.classList.contains("selection-category-entry")) {
        return;
    }

    div.style.zIndex = 999;

    if (isDouble) {
        div.getElementsByTagName("span").item(0).textContent = "Daily Double!";
        div.style.animationName = "dailyDouble";
    }

    let bbox = div.getBoundingClientRect();
    let distX = (window.innerWidth / 2) - (bbox.x + bbox.width / 2);
    let distY = (window.innerHeight / 2) - (bbox.y + bbox.height / 2);

    div.style.transition = "all 2.5s";
    div.style.transform = `translate(${distX}px, ${distY}px) scale(11)`;

    socket.emit("mark_question_active", questionId, function() {
        setTimeout(() => {
            goToPage(getQuestionURL());
        }, 2600);
    });

}

function goToSelectedCategory() {
    let boxes = document.getElementsByClassName("selection-question-box");
    for (let i = 0; i < boxes.length; i++) {
        let box = boxes.item(i);
        if (box.classList.contains("selected")) {
            box.classList.remove("selected");
            box.click();
            break;
        }
    }
}

function tabulateCategorySelection(key, cols) {
    // Find currently selected category box, if any
    let boxes = document.getElementsByClassName("selection-question-box");
    let selectedBox = null;
    let selectedIndex = 0;
    for (let i = 0; i < boxes.length; i++) {
        let box = boxes.item(i);
        if (box.classList.contains("selected")) {
            selectedBox = box;
            selectedIndex = i;
            break
        }
    }

    // Choose the next selected box based on input
    const rows = 5;
    let maxIndex = (cols + 1) * rows - 1;
    if (key == "ArrowRight") {
        selectedIndex = selectedBox == null ? 0 : selectedIndex + cols;
        if (selectedIndex > maxIndex) {
            selectedIndex = selectedIndex - maxIndex - 1;
        }
    }
    else if (key == "ArrowLeft") {
        selectedIndex = selectedBox == null ? cols * rows : selectedIndex - cols;
        if (selectedIndex < 0) {
            selectedIndex = maxIndex + selectedIndex + 1;
        }
    }
    else if (key == "ArrowUp") {
        selectedIndex = selectedBox == null ? cols : Math.max(selectedIndex - 1, 0);
    }
    else if (key == "ArrowDown") {
        selectedIndex = selectedBox == null ? 0 : Math.min(selectedIndex + 1, maxIndex);
    }

    if (selectedBox != null) {
        selectedBox.classList.remove("selected");
    }

    boxes.item(selectedIndex).classList.add("selected");
}

function setContestantTextColors() {
    let contestantEntries = document.getElementsByClassName("footer-contestant-entry");
    for (let i = 0; i < contestantEntries.length; i++) {
        let bgColor = contestantEntries.item(i).style.backgroundColor;
        let split = bgColor.replace("rgb(", "").replace(")", "").split(",");

        let red = parseInt(split[0]).toString(16);  
        let green = parseInt(split[1]).toString(16);
        let blue = parseInt(split[2]).toString(16); 

        let fgColor = red * 0.299 + green * 0.587 + blue * 0.114 > 160 ? "black" : "white";
        contestantEntries.item(i).style.color = fgColor;
    }
}

function setPlayerTurn(playerId, save) {
    let playerEntries = document.querySelectorAll(".footer-contestant-entry");
    playerEntries.forEach((entry) => {
        if (entry.classList.contains("active-contestant-entry")) {
            entry.classList.remove("active-contestant-entry");
        }
    });

    if (playerId != null) {
        let playerEntry = document.querySelector(`.footer-contestant-${playerId}`);
        playerEntry.classList.add("active-contestant-entry");
    }

    if (save) {
        playerTurn = playerId;
    }
}

function chooseStartingPlayer(callback) {
    let playerEntries = document.getElementsByClassName("footer-contestant-entry");
    let minIters = 20;
    let maxIters = 32;
    let iters = minIters + (maxIters - minIters) * Math.random();
    let minWait = 30;
    let maxWait = 400;

    function showStartPlayerCandidate(iter) {
        let wait = minWait + (maxWait - minWait) * (iter / iters);

        setTimeout(() => {
            let player = iter % playerEntries.length;
            let playerId = playerIds[player];

            setPlayerTurn(playerId, false);

            if (iter < iters) {
                showStartPlayerCandidate(iter + 1);
            }
            else {
                callback(playerId);
            }
        }, wait);
    }

    showStartPlayerCandidate(0);
}

function beginJeopardy() {
    goToPage(getSelectionURL());
}

function addContestantDiv(id, name, avatar, color) {
    let wrapper = document.getElementById("menu-contestants");
    let placeholder = document.getElementById("menu-no-contestants-placeholder");
    if (placeholder != null) {
        wrapper.removeChild(placeholder);
    }

    let divId = "player_" + id;
    let existingDiv = document.getElementById(divId);
    let div = existingDiv != null ? existingDiv : document.createElement("div");

    div.id = divId;
    div.className = "menu-contestant-entry";
    div.style.border = "2px solid " + color;

    if (existingDiv == null) {
        let avatarElem = document.createElement("img");
        avatarElem.className = "menu-contestant-avatar";
        avatarElem.style.border = "2px solid " + color;
        avatarElem.src = `${getBaseURL()}/static/${avatar}`;
    
        let nameElem = document.createElement("div");
        nameElem.className = "menu-contestant-name";
        nameElem.textContent = name;
    
        div.appendChild(avatarElem);
        div.appendChild(nameElem);

        wrapper.appendChild(div);
    }
    else {
        let nameElem = div.querySelector(".menu-contestant-name");
        nameElem.textContent = name;
 
        let avatarElem = div.querySelector(".menu-contestant-avatar");
        avatarElem.src = `${getBaseURL()}/static/${avatar}`;
    }
}

function setPlayerReady(playerId) {
    console.log("Setting ready state for player:", playerId);

    let playerEntry = document.querySelector(`.footer-contestant-${playerId}`);

    if (playerEntry) {
        let readyIcon = playerEntry.querySelector(".footer-contestant-entry-ready");
        readyIcon.style.display = "block";
    }
}

function showFinaleCategory() {
    window.onkeydown = function(e) {
        if (e.code == PRESENTER_ACTION_KEY) {
            let header1 = document.getElementById("selection-finale-header1");
            header1.style.setProperty("opacity", 1);

            setTimeout(function() {
                let header2 = document.getElementById("selection-finale-header2");
                header2.style.setProperty("opacity", 1);

                let header3 = document.getElementById("selection-finale-header3");
                header3.style.setProperty("opacity", 1);
            }, 2000);

            setTimeout(function() {
                socket.emit("enable_finale_wager");
                document.getElementById("selection-jeopardy-theme").play();

                window.onkeydown = function(e) {
                    if (e.code == PRESENTER_ACTION_KEY) {
                        goToPage(getQuestionURL());
                    }
                }
            }, 3000);
        }
    }
}

function showFinaleResult() {
    let wagerDescElems = document.getElementsByClassName("finale-result-desc");
    let wagerInputElems = document.getElementsByClassName("finale-wager-amount");

    function showNextResult(player) {
        if (player == 0) {
            document.getElementById("finale-results-wrapper").style.opacity = 1;
        }

        if (player == playerIds.length) {
            let teaserElem = document.getElementById("endscreen-teaser");
            teaserElem.style.opacity = 1;

            setTimeout(function() {
                goToPage(getEndscreenURL());
            }, 2000);
        }
        else {
            let playerElem = document.getElementsByClassName("finale-result-name").item(player);
            let playerId = playerIds[player];
            playerElem.style.color = "#" + playerColors[playerId];
            playerElem.style.opacity = 1;
    
            window.onkeydown = function(e) {
                let descElem = wagerDescElems.item(player);
                let amountRaw = wagerInputElems.item(player).textContent;
                let amount = 0;
                if (amountRaw != "nothing") {
                    amount = parseInt(amountRaw);
                }

                if (e.key == 1 || e.key == 2) {
                    descElem.style.opacity = 1;
                    let className = null;
                    let desc = null;

                    if (amount == 0) { // Current player did not answer
                        className = "wager-answer-skipped";
                        desc = localeStrings["answer_skipped"];
                    }
                    else if (e.key == 1) { // Current player answered correctly
                        className = "wager-answer-correct";
                        desc = `${localeStrings["and"]} <strong>${localeStrings["answer_correct"]} ${amount} ${localeStrings["points"]}</strong>!`;
                        socket.emit("finale_answer_correct", playerId, amount);
                    }
                    else if (e.key == 2) { // Current player answered incorrectly
                        className = "wager-answer-wrong";
                        desc = `${localeStrings["and"]} <strong>${localeStrings["answer_wrong"]} ${amount} ${localeStrings["points"]}</strong>!`;
                        socket.emit("finale_answer_wrong", playerId, amount);
                    }

                    descElem.classList.add(className);
                    descElem.innerHTML = desc;
                }
                else if (e.code == PRESENTER_ACTION_KEY) {
                    showNextResult(player + 1);
                }
            }
        }
    }

    window.onkeydown = function(e) {
        if (e.code == PRESENTER_ACTION_KEY) {
            showNextResult(0);
        }
    }

    let answerElem = document.getElementById("finale-answer");
    answerElem.style.opacity = 1;
}

function startWinnerParty() {
    window.onkeydown = function(e) {
        if (e.code == PRESENTER_ACTION_KEY) {
            document.getElementById("endscreen-confetti-video").play();
            document.getElementById("endscreen-music").play();
            let overlay = document.getElementById("endscreen-techno-overlay");

            overlay.classList.remove("d-none");

            let colors = ["#1dd8265e", "#1d74d85e", "#c90f0f69", "#deb5115c"];
            let colorIndex = 0;

            let initialDelay = 320;
            let intervalDelay = 472;

            setTimeout(() => {
                overlay.style.backgroundColor = colors[colorIndex];
                colorIndex += 1;

                setInterval(() => {
                    overlay.style.backgroundColor = colors[colorIndex];
    
                    colorIndex += 1;
    
                    if (colorIndex == colors.length) {
                        colorIndex = 0;
                    }
                }, intervalDelay);
            }, initialDelay);
        }
    }
}

function setVolume() {
    for (let volume = 1; volume <= 10; volume++) {
        let className = "volume-" + volume;
        let elems = document.getElementsByClassName(className);
        for (let i = 0; i < elems.length; i++) {
            elems.item(i).volume = parseFloat("0." + volume);
        }
    }

    let questionVideo = document.querySelector(".question-question-video");
    if (questionVideo != null && questionVideo.dataset.volume != null) {
        questionVideo.volume = Number.parseFloat(questionVideo.datase.volume);
    }
}

function champOPGG() {
    let tableRows = document.querySelector(".content > table").getElementsByTagName("tr");
    let playedDict = {};

    for (let i = 0; i < tableRows.length; i++) {
        let row = tableRows.item(i);
        let tdEntries = row.getElementsByTagName("td");
        if (tdEntries.length == 0) {
            continue;
        }

        let champName = tdEntries.item(1).getElementsByClassName("summoner-name").item(0).children[0].textContent;

        let playedEntry = tdEntries.item(2);
        let winRatioElem = playedEntry.getElementsByClassName("win-ratio");
        if (winRatioElem.length == 0) {
            playedDict[champName.replace('"', "").replace('"', "").trim()] = parseInt(playedEntry.textContent.replace("Played", ""));
        }
        else {
            let played = 0;
            let left = winRatioElem.item(0).getElementsByClassName("winratio-graph__text left");
            if (left.length != 0) {
                played += parseInt(left.item(0).textContent.replace("W", ""));
            }
            let right = winRatioElem.item(0).getElementsByClassName("winratio-graph__text right");
            if (right.length != 0) {
                played += parseInt(right.item(0).textContent.replace("L", ""));
            }

            playedDict[champName] = played;
        }
    }

    return playedDict;
}

function mergeOPGG(stats) {
    let playedDict = champOPGG();
    for (var champ in playedDict) { stats[champ] = playedDict[champ] + (stats[champ] || 0); }
    return stats;
}
