// Create socket bound to a namespace for a specific game ID.
// 'GAME_ID' is defined before this JS file is imported
const CONN_ATTEMPTS = 3;
var socket;
for (let i = 0; i < CONN_ATTEMPTS; i++) {
    try {
        socket = io(`/${GAME_ID}`, {"transports": ["websocket", "polling"], "rememberUpgrade": true, "timeout": 5000});
        socket.on("connect_error", function(err) {
            console.error("Presenter socket connection error:", err);
            if (socket.active) {
                console.log("Socket will reconnect...");
            }
            else {
                console.log("Socket is DEAD!!!");
            }
        });
        break;
    }
    catch (err) {
        console.log(`PRESENTER --- ERROR #${i} WHEN CONNECTING TO SOCKET IO!`);
        console.log(err);
    }
}

const TIME_FOR_FINAL_ANSWER = 40;
const TIME_BEFORE_FIRST_TIP = 4;
const TIME_BEFORE_EXTRA_TIPS = 4;
const TIME_TO_REWIND_AFTER_QUESTION = 4;
const TIME_FOR_FREEZE = 40;
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
var answerTime = 6;
var buzzInTime = 10;
var isDailyDouble = false;
var activePowerUp = null;
var hijackBonus = false;
var freezeTimeout = null;
var revealEditBtnTimeout = null;

let playerTurn = null;
var playerIds = [];
var playerNames = {};
var playerScores = {};
let playerColors = {};
let playersBuzzedIn = [];
var setupComplete = false;

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
    setupComplete = false;
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

function revealAnswerImageIfPresent() {
    let elem = document.querySelector(".question-answer-image");
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
    if (canPlayersBuzzIn()) {
        socket.emit("enable_powerup", playerId, powerId);
    }
}

function disablePowerUp(playerId=null, powerId=null) {
    if (canPlayersBuzzIn()) {
        socket.emit("disable_powerup", playerId, powerId);
    }
}

function hideFreezeAnimation() {
    let freezeWrapper = document.querySelector(".question-countdown-frozen");
    freezeWrapper.style.transition = "opacity 2s";
    freezeWrapper.style.opacity = 0;
    setTimeout(function() {
        freezeWrapper.classList.add("d-none");
    }, 1000);
}

function triggerScoreUpdateAnimation(element, delta) {
    let duration = Number.parseFloat(window.getComputedStyle(element).animationDuration.replace("s", ""));

    let animationName;
    let absDelta = Math.abs(delta);
    if (absDelta < 500) {
        animationName = "scoreUpdatedSmall";
    }
    else if (absDelta < 1000) {
        animationName = "scoreUpdatedMedium";
    }
    else if (absDelta < 1500) {
        animationName = "scoreUpdatedLarge";
    }
    else {
        animationName = "scoreUpdatedHuge";
    }
    element.style.animationName = animationName;

    let className = `score-animation-${delta >= 0 ? 'correct' : 'wrong'}`;
    element.classList.add(className);
 
    setTimeout(function() {
        // Reset animation after it has played
        element.style.animationName = "none";
        element.offsetHeight; // Trigger reflow
        element.style.animationName = null;
        element.classList.remove(className);
    }, duration * 1000);
}

function updatePlayerScore(playerId, delta) {
    playerScores[playerId] += delta;
    let playerEntry = document.querySelector(`.footer-contestant-${playerId}`);
    let scoreElem = playerEntry.querySelector(".footer-contestant-entry-score");

    scoreElem.textContent = `${playerScores[playerId]} ${localeStrings["points_short"]}`;
    triggerScoreUpdateAnimation(scoreElem, delta);
}

function updatePlayerBuzzStats(playerId, hit, delta=1) {
    let playerEntry = document.querySelector(`.footer-contestant-${playerId}`);
    let name = hit ? ".footer-contestant-entry-hits" : ".footer-contestant-entry-misses"
    let statElem = playerEntry.querySelector(name);

    let newValue = Number.parseInt(statElem.textContent) + delta;
    statElem.textContent = newValue.toString();
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

function setPlayerTurn(playerId, save) {
    let playerEntries = document.querySelectorAll(".footer-contestant-entry");
    playerEntries.forEach((entry) => {
        entry.classList.remove("active-contestant-entry");
    });

    if (playerId != null) {
        let playerEntry = document.querySelector(`.footer-contestant-${playerId}`);
        playerEntry.classList.add("active-contestant-entry");
    }

    if (save) {
        playerTurn = playerId;
    }
}

function registerAction(callback) {
    window.onkeydown = function(e) {
        if (e.code == PRESENTER_ACTION_KEY) {
            callback(e);
        }
    }
}

function playerHasPowerUp(playerId, powerId) {
    let powersWrapper = document.querySelector(`.footer-contestant-${playerId} .footer-contestant-entry-powers`);
    let powerUsedElem = powersWrapper.querySelector(`.footer-contestant-power-${powerId} > .footer-contestant-entry-power-used`);
    return powerUsedElem.classList.contains("d-none");
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
    buzzFeed.querySelector("ul").innerHTML = "";

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
    if (wrongAnswers > 0) {
        let choices = getNumAnswerChoices();
        activeValue -= (activeValue * (wrongAnswers / choices));
    }

    if (hijackBonus) {
        activeValue *= 1.5;
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

function revealAnswer() {
    revealAnswerImageIfPresent();

    let answerElem = document.getElementById("question-actual-answer");
    answerElem.classList.remove("d-none");

    afterQuestion();
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

    let allPlayersAnswered = Object.values(activePlayers).every(v => !v);
    if (outOfTime || allPlayersAnswered) {
        // No players are eligible to answer, go to next question
        let playerHasRewind = answeringPlayer != null && playerHasPowerUp(answeringPlayer, "rewind");
        let delay = 0;

        if (outOfTime) { // If out of time, move on immediately
            valueElem.textContent = "";
        }
        else if (playerHasRewind) {
            // If last buzzing player has rewind,
            // give them a few seconds to use rewind
            delay = TIME_TO_REWIND_AFTER_QUESTION * 1000;
        }

        setTimeout(function() {
            if (delay == 0 || activePowerUp != "rewind") {
                revealAnswer();
                afterAnswer();
            }
        }, delay);
    }
    else {
        afterAnswer();
    }
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
    let keys = Array.apply(null, Array(max - min + 1)).map(function (x, i) { return (i + min).toString(); });
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

function getNumAnswerChoices() {
    return document.getElementsByClassName("question-choice-entry").length;
}

function answerQuestion(event) {
    let choices = getNumAnswerChoices();
    if (keyIsNumeric(event.key, 1, Math.max(choices, 2))) {
        if (choices) {
            // Highlight element as having been selected as the answer.
            const elem = document.querySelector(".question-choice-" + event.key);

            if (
                elem.classList.contains("question-answering")
                || elem.classList.contains("question-answered-wrong")
                || elem.classList.contains("question-answered-correct")
            ) {
                return;
            }

            const delay = 2500
            const answerElem = elem.querySelector(".question-choice-text");
            elem.classList.add("question-answering");

            const timeoutId = setTimeout(function() {
                elem.classList.remove("question-answering");
                
                if (answerElem.textContent == activeAnswer) {
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

function setCountdownText(countdownText, millis, maxMillis) {
    let seconds = (maxMillis - millis) / 1000;
    countdownText.textContent = seconds.toFixed(2);
}

function setCountdownValues(countdownBar, milis, green, red, maxMilis) {
    let width = (milis / maxMilis) * 100;
    countdownBar.style.width = width + "%";
    countdownBar.style.backgroundColor = "rgb(" + red.toFixed(0) + ", " + green.toFixed(0) + ", 0)";
}

function startCountdown(duration, callback=null) {
    if (countdownInterval) {
        stopCountdown();
    }

    let countdownWrapper = document.querySelector(".question-countdown-wrapper");
    if (countdownWrapper.classList.contains("d-none")) {
        countdownWrapper.classList.remove("d-none");
    }
    countdownWrapper.style.opacity = 1;
    let countdownBar = document.querySelector(".question-countdown-filled");
    let countdownText = document.querySelector(".question-countdown-text");

    let green = 255
    let red = 136;

    let currTime = 0;
    let delay = 30;
    let durationMillis = duration * 1000;

    let totalSteps = durationMillis / delay;
    let colorDelta = (green + red) / totalSteps;

    setCountdownText(countdownText, currTime, durationMillis);
    setCountdownValues(countdownBar, currTime, green, red, durationMillis);

    countdownPaused = false;

    countdownInterval = setInterval(function() {
        if (countdownPaused) {
            return;
        }

        if (red < 255) {
            red += colorDelta;
        }
        else if (green > 0) {
            green -= colorDelta;
        }

        setCountdownValues(countdownBar, currTime, green, red, durationMillis);
        setCountdownText(countdownText, currTime, durationMillis);

        currTime += delay;

        if (currTime >= durationMillis) {
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
        if (!videoElem.paused) {
            videoElem.pause();
        }
    }
}

function pauseBeforeAnswer() {
    // Disable 'hijack' power-up for all and 'freeze' for the answering player
    // after an answer has been given
    disablePowerUp(null, "hijack");
    disablePowerUp(answeringPlayer, "freeze");

    // Pause video if one is playing
    pauseVideo();

    // Clear countdown
    stopCountdown();

    window.onkeydown = answerQuestion;
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
    registerAction(pauseBeforeAnswer);
}

function addToGameFeed(text) {
    let wrapper = document.getElementById("question-game-feed");
    wrapper.classList.remove("d-none");

    let listParent = wrapper.querySelector("ul");

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
    addToGameFeed(`<span style="color: ${color}; font-weight: 800">${name}</span> ${powerStr1} <strong>${powerId}</strong> ${powerStr2}!`);
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
        startAnswerCountdown(answerTime);

        // Enable 'freeze' for player who buzzed
        enablePowerUp(playerId, "freeze");
    }, 500);
}

function playerBuzzedFirst(playerId) {
    if (activePowerUp != null && (activePowerUp != "hijack")) {
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
        freezeWrapper.offsetHeight; // Trigger reflow
        freezeWrapper.style.transition = `opacity ${TIME_FOR_FREEZE - fadeInDuration}s`;
        freezeWrapper.style.opacity = 0.05;

        setTimeout(function() {
            if (answeringPlayer != null) {
                freezeWrapper.classList.add("d-none");
                pauseCountdown(false);
            }
        }, (TIME_FOR_FREEZE - fadeInDuration) * 1000)
    }, fadeInDuration * 1000);
}

function onRewindUsed(playerId) {
    stopCountdown();

    // Refund the score the player lost on the previous answer
    let score = playerScores[playerId];
    let missesElem = document.querySelector(`.footer-contestant-${playerId} .footer-contestant-entry-misses`);
    let misses = Number.parseInt(missesElem.textContent)

    let data = {"misses": misses - 1, "score": score + activeValue};
    socket.emit("edit_contestant_info", playerId, JSON.stringify(data));

    updatePlayerScore(playerId, activeValue);
    updatePlayerBuzzStats(playerId, false, -1);

    // If other players buzzed in at the same time as rewind was used,
    // refund them their buzzes
    let afterPlayer = false;
    let filteredBuzzes = [];
    for (let playerBuzzed of playersBuzzedIn) {
        if (afterPlayer) {
            activePlayers[playerBuzzed] = true;
        }
        else {
            filteredBuzzes.push(playerBuzzed);
        }

        if (playerBuzzed == playerId) {
            afterPlayer = true;
        }
    }
    playersBuzzedIn = filteredBuzzes;    

    answeringPlayer = playerId;
}

function afterRewindUsed() {
    afterBuzzIn(answeringPlayer);
}

function isHijackBeforeQuestion() {
    let questionHeader = document.querySelector(".question-question-header");
    let questionImage = document.querySelector(".question-question-image");
    let videoElem = document.querySelector(".question-question-video");
    if (questionImage != null) {
        return getComputedStyle(questionImage).opacity < 0.5
    }
    if (videoElem != null) {
        return getComputedStyle(videoElem).opacity < 0.5
    }

    return questionHeader != null && getComputedStyle(questionHeader).opacity < 0.5;
}

function onHijackUsed(playerId) {
    pauseCountdown(true);

    // If question has not been asked yet, hijack gives bonus points
    hijackBonus = isHijackBeforeQuestion();

    activePlayers = {};
    playerIds.forEach((id) => {
        activePlayers[id] = false;
    });
    activePlayers[playerId] = true;

    if (!hijackBonus && answeringPlayer != null) {
        stopCountdown();
    }
}

function afterHijackUsed(playerId, videoPaused) {
    if (!hijackBonus && answeringPlayer != null) {
        answeringPlayer = playerId;
        afterBuzzIn(playerId);
    }
    else {
        setPlayerTurn(playerId, false);
        if (videoPaused) { // Unpause question media video if we paused it ealier
            document.querySelector(".question-question-video").play();
        }
    }

    pauseCountdown(false);
}

function powerUpUsed(playerId, powerId) {
    activePowerUp = powerId;

    console.log(`Player ${playerNames[playerId]} used power '${powerId}'`);

    let videoElem = document.querySelector(".question-question-video");
    let videoPaused = videoElem != null && !videoElem.paused && !videoElem.ended;
    if (videoPaused) {
        videoElem.pause();
    }

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
        onHijackUsed(playerId);
        callback = () => afterHijackUsed(playerId, videoPaused);
    }

    addPowerUseToFeed(playerId, powerId);
    showPowerUpVideo(powerId, playerId).then(() => {
        if (callback) {
            callback();
        }
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

    let delay = index == 0 ? TIME_BEFORE_FIRST_TIP : TIME_BEFORE_EXTRA_TIPS;
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
            // Allow presenter to abort the question if no one wants to answer
            window.onkeydown = function(e) {
                if (e.code == "Enter") {
                    stopCountdown();
                    wrongAnswer(localeStrings["wrong_answer_cowards"], true);
                }
            }

            hideAnswerIndicator();
            showTip(0);

            if (buzzInTime > 0) {
                startCountdown(buzzInTime);
            }
        }
        else if (isDailyDouble || activePowerUp == "hijack") {
            startAnswerCountdown(buzzInTime);
        }
        else if (activeStage == "finale_question") {
            // Go to finale screen after countdown is finished if it's round 3
            document.getElementById("question-finale-suspense").play();
            let url = getFinaleURL();
    
            startCountdown(TIME_FOR_FINAL_ANSWER, () => goToPage(url));

            // Allow us to override the countdown if people are done answering
            setTimeout(function() {
                registerAction(function() {
                    stopCountdown();
                    goToPage(url);
                });
            }, 2000);
        }
    }, countdownDelay);

    if (canPlayersBuzzIn()) {
        // Enable participants to buzz in if we are in regular rounds
        listenForBuzzIn();
    }
}

function showAnswerChoice(index) {
    let choiceElems = document.querySelectorAll(".question-choice-entry");
    let currChoice = choiceElems[index];
    currChoice.style.opacity = 1;

    if (index == choiceElems.length - 1) {
        questionAsked(500);
    }
    else {
        registerAction(function() {
            showAnswerChoice(index + 1);
        })
    }
}

function afterShowQuestion() {
    if (getNumAnswerChoices()) {
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
    if (elem.dataset["media_size"] == "maximized") {
        document.querySelector(".question-category-header").style.display = "none";
        document.querySelector(".question-question-header").style.display = "none";
    }
    elem.style.opacity = 1;
}

function showQuestion() {
    window.onkeydown = null;
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
        registerAction(function() {
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
                else if (isDailyDouble) {
                    // If daily double, allow interruption of the video by presenter
                    registerAction(function() {
                        videoElem.onended = null;
                        pauseBeforeAnswer();
                    });
                }
            }
        });
    }
    else {
        // If there is no answer image, either show answer choices if question
        // is multiple choice, otherwise show question image/video
        if (getNumAnswerChoices()) {
            if (questionImage != null) {
                showImageOrVideo(questionImage);
            }
            afterShowQuestion();
        }
        else {
            if (questionImage != null) {
                showImageOrVideo(questionImage);
            }
            registerAction(afterShowQuestion);
        }
    }
}

function afterDailyDoubleWager(amount) {
    let wrapper = document.getElementById("question-wager-wrapper");
    if (wrapper.classList.contains("d-none")) {
        return;
    }
    wrapper.classList.add("d-none");

    activeValue = amount;
    let questionDesc = document.querySelector(".question-desc-span");
    questionDesc.innerHTML = `${localeStrings['for']} <span class="question-reward-span">${amount} ${localeStrings["points"]}</span>`;

    showQuestion();
}

function initialize(playerJson, stage, localeJson, pageSpecificJson=null) {
    let playerData = JSON.parse(playerJson);
    let pageSpecificData = pageSpecificJson == null ? null : JSON.parse(pageSpecificJson);

    localeStrings = JSON.parse(localeJson);

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

    
    activeStage = stage;
    if (pageSpecificData) {
        activeAnswer = pageSpecificData["answer"];
        activeValue = pageSpecificData["value"];
        answerTime = pageSpecificData["answer_time"];
        buzzInTime = pageSpecificData["buzz_time"];
        isDailyDouble = pageSpecificData["daily_double"];
        if (isDailyDouble) {
            answeringPlayer = playerTurn;
            setPlayerTurn(answeringPlayer, false);
        }
    }
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
        div.getElementsByTagName("span").item(0).textContent = `${localeStrings["daily_double"]}!`;
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

function setContestantTextSizeAndColors() {
    let contestantEntries = document.getElementsByClassName("footer-contestant-entry");
    for (let i = 0; i < contestantEntries.length; i++) {
        let entry = contestantEntries.item(i);

        // Set color of text that achieves most contrast with background color
        let bgColor = entry.style.backgroundColor;
        let split = bgColor.replace("rgb(", "").replace(")", "").split(",");

        let red = parseInt(split[0]);
        let green = parseInt(split[1]);
        let blue = parseInt(split[2]);

        let fgColor = red * 0.299 + green * 0.587 + blue * 0.114 > 160 ? "black" : "white";
        entry.style.color = fgColor;

        // Set dynamic font size of player name
        let baseWidth = 184;
        let scale = (entry.getBoundingClientRect().width * 2) / (baseWidth * 2);

        let playerName = entry.querySelector(".footer-contestant-entry-name");
        let fontSize = scale * (120 - (playerName.textContent.length * 3.3));
        playerName.style.fontSize = Math.round(fontSize) + "%";
    }
}

function chooseStartingPlayer() {
    let playerEntries = document.getElementsByClassName("footer-contestant-entry");
    let minIters = 30;
    let maxIters = 40;
    let iters = minIters + (maxIters - minIters) * Math.random();
    let minWait = 25;
    let maxWait = 420;

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
                setPlayerTurn(playerId, true);
                document.querySelectorAll(".selection-question-box").forEach((elem) => {
                    elem.classList.remove("inactive");
                });
                socket.emit("first_turn", playerId);
            }
        }, wait);
    }

    showStartPlayerCandidate(0);
}

function beginJeopardy() {
    goToPage(getSelectionURL());
}

function contestantRemoved(playerId) {
    let wrapper = document.getElementById("footer-contestants");
    let playerDiv = document.querySelector(`.footer-contestant-${playerId}`);

    wrapper.removeChild(playerDiv);
}

function removeContestant(playerId) {
    if (!confirm(localeStrings["confirm_remove"])) {
        return;
    }

    socket.emit("remove_contestant", playerId);
}

function addContestantInGame(contestantData) {
    let avatar = contestantData["avatar"];

    let wrapper = document.getElementById("footer-contestants");

    let classId = `footer-contestant-${contestantData["id"]}`;
    let existingDiv = document.querySelector(`.${classId}`);

    let div = existingDiv != null ? existingDiv : document.createElement("div");

    if (existingDiv == null) {
        div.className = `footer-contestant-entry ${classId}`;
        div.style.backgroundColor = contestantData["color"];
        div.onmouseenter = function() {
            revealContestantEditBtn(id);
        }
        div.onmouseleave = function() {
            hideContestantEditBtn(id);
        }

        // Create buzzes div
        let buzzElem = document.createElement("div");
        buzzElem.className = "footer-contestant-buzzes";

        let hitsElem = document.createElement("div");
        hitsElem.className = "footer-contestant-entry-hits";
        hitsElem.textContent = contestantData["hits"];

        let missesElem = document.createElement("div");
        missesElem.className = "footer-contestant-entry-misses";
        missesElem.textContent = contestantData["misses"];

        buzzElem.appendChild(hitsElem);
        buzzElem.appendChild(missesElem);

        // Create header div
        let headerElem = document.createElement("div");
        headerElem.className = "footer-contestant-header";

        let nameElem = document.createElement("div");
        nameElem.className = "footer-contestant-entry-name";
        nameElem.textContent = contestantData["name"];

        let scoreElem = document.createElement("div");
        scoreElem.className = "footer-contestant-entry-score";
        scoreElem.textContent = `${contestantData["score"]} ${localeStrings['points_short']}`;

        headerElem.appendChild(nameElem);
        headerElem.appendChild(scoreElem);

        // Create avatar images
        let avatarElem = document.createElement("img");
        avatarElem.className = "footer-contestant-entry-avatar";
        avatarElem.src = `${getBaseURL()}/static/${avatar}`;

        let readyElem = document.createElement("img");
        readyElem.className = "footer-contestant-entry-ready";
        readyElem.src = `${getBaseURL()}/static/img/check.png`;

        let disconnectedElem = document.createElement("img");
        disconnectedElem.className = "footer-contestant-entry-disconnected";
        disconnectedElem.src = `${getBaseURL()}/static/img/disconnected.png`;

        // Create edit btn
        let editBtn = document.createElement("button");
        editBtn.className = "footer-contestant-edit-btn d-none";
        editBtn.onclick = function() {
            toggleEditContestantInfo(contestantData["id"]);
        }

        let editImg = document.createElement("img");
        editImg.className = "footer-contestant-edit-edit";
        editImg.src = `${getBaseURL()}/static/img/edit.png`;

        let saveImg = document.createElement("img");
        saveImg.className = "footer-contestant-edit-save d-none";
        saveImg.src = `${getBaseURL()}/static/img/save.png`;

        editBtn.appendChild(editImg);
        editBtn.appendChild(saveImg);

        // Create button for kicking contestant
        let removeBtn = document.createElement("button");
        removeBtn.className = "footer-contestant-remove-btn d-none";
        removeBtn.innerHTML = "&times;";
        removeBtn.onclick = function() {
            removeContestant(id);
        }

        // Create powers div
        let powersWrapper = document.createElement("div");
        powersWrapper.className = "footer-contestant-entry-powers";

        contestantData["power_ups"].forEach((power) => {
            let powerElem = document.createElement("div");
            powerElem.className = `footer-contestant-power-${power["type"]}`;

            let usedImg = document.createElement("img");
            usedImg.className = "footer-contestant-entry-power-used";
            if (!power["used"]) {
                usedImg.classList.add("d-none");
            }
            usedImg.src = `${getBaseURL()}/static/img/forbidden.png`;

            let powerImg = document.createElement("img");
            powerImg.className = "footer-contestant-entry-power-icon";
            if (!power["used"]) {
                powerImg.classList.add("d-none");
            }
            powerImg.src = `${getBaseURL()}/static/${power["icon"]}`;

            powerElem.appendChild(usedImg);
            powerElem.appendChild(powerImg);

            powersWrapper.appendChild(powerElem);
        });

        div.appendChild(buzzElem);
        div.appendChild(headerElem);
        div.appendChild(avatarElem);
        div.appendChild(readyElem);
        div.appendChild(disconnectedElem);
        div.appendChild(editBtn);
        div.appendChild(removeBtn);
        div.appendChild(powersWrapper);

        wrapper.appendChild(div);
    }
    else {
        let nameElem = div.querySelector(".footer-contestant-entry-name");
        nameElem.textContent = contestantData["name"];

        let scoreElem = div.querySelector(".footer-contestant-entry-score");
        scoreElem.textContent = `${contestantData["score"]} ${localeStrings['points_short']}`;
 
        let avatarElem = div.querySelector(".footer-contestant-entry-avatar");
        avatarElem.src = `${getBaseURL()}/static/${avatar}`;

        let disconnectedIcon = div.querySelector(".footer-contestant-entry-disconnected");
        disconnectedIcon.classList.add("d-none");
    }
}

function addContestantInLobby(contestantData) {
    let avatar = contestantData["avatar"];

    let wrapper = document.getElementById("menu-contestants");
    let placeholder = document.getElementById("menu-no-contestants-placeholder");
    if (placeholder != null) {
        wrapper.removeChild(placeholder);
    }

    let divId = "player_" + contestantData["id"];
    let existingDiv = document.getElementById(divId);
    let div = existingDiv != null ? existingDiv : document.createElement("div");

    div.style.border = "2px solid " + contestantData["color"];

    if (existingDiv == null) {
        div.id = divId;
        div.className = "menu-contestant-entry";

        let avatarElem = document.createElement("img");
        avatarElem.className = "menu-contestant-avatar";
        avatarElem.style.border = "2px solid " + contestantData["color"];
        avatarElem.src = `${getBaseURL()}/static/${avatar}`;
    
        let nameElem = document.createElement("div");
        nameElem.className = "menu-contestant-name";
        nameElem.textContent = contestantData["name"];
    
        div.appendChild(avatarElem);
        div.appendChild(nameElem);

        wrapper.appendChild(div);
    }
    else {
        let nameElem = div.querySelector(".menu-contestant-name");
        nameElem.textContent = contestantData["name"];
 
        let avatarElem = div.querySelector(".menu-contestant-avatar");
        avatarElem.src = `${getBaseURL()}/static/${avatar}`;
    }
}

function contestantJoined(contestantJson) {
    let contestantData = JSON.parse(contestantJson);

    if (activeStage == "lobby") {
        addContestantInLobby(contestantData);
    }
    else {
        addContestantInGame(contestantData);
    }

    let contestantId = contestantData["id"]
    playerScores[contestantId] = contestantData["score"];
    playerNames[contestantId] = contestantData["name"];
    playerColors[contestantId] = contestantData["color"];
}

function contestantDisconnected(playerId) {
    console.log("Contestant disconnected:", playerId);
    
    if (activeStage == "lobby") {
        return;
    }

    let playerDiv = document.querySelector(`.footer-contestant-${playerId}`);
    let disconnectIcon = playerDiv.querySelector(".footer-contestant-entry-disconnected");
    disconnectIcon.classList.remove("d-none");
}

function setPlayerReady(playerId) {
    console.log("Setting ready state for player:", playerId);

    let playerEntry = document.querySelector(`.footer-contestant-${playerId}`);

    if (playerEntry) {
        let readyIcon = playerEntry.querySelector(".footer-contestant-entry-ready");
        readyIcon.classList.remove("d-none");
    }
}

function showFinaleCategory() {
    registerAction(function() {
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

            registerAction(function() {
                goToPage(getQuestionURL());
            });
        }, 3000);
    });
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
                if (amountRaw != localeStrings["nothing"]) {
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
                else if (isCtrlZHeld(e) && e.key == "z") {
                    // Undo last answer
                    const correct = descElem.classList.contains("wager-answer-correct");
                    if (correct) {
                        descElem.classList.remove("wager-answer-correct");
                    }
                    else {
                        descElem.classList.remove("wager-answer-wrong");
                    }

                    descElem.innerHTML = "";
                    descElem.style.opacity = 0;

                    socket.emit("finale_answer_undo", playerId, correct ? -amount : amount);
                }
            }
        }
    }

    registerAction(function() {
        showNextResult(0);
    });

    let answerElem = document.getElementById("finale-answer");
    answerElem.style.opacity = 1;
}

function startEndscreenAnimation() {
    let endscreenMusic = document.getElementById("endscreen-music");
    let confettiVideo = document.getElementById("endscreen-confetti-video");
    let overlay = document.getElementById("endscreen-techno-overlay");

    endscreenMusic.play();
    confettiVideo.play();
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

    // Add listener for stopping the party when the police knocks down the door
    registerAction(function() {
        overlay.classList.add("d-none");
        endscreenMusic.pause();
        confettiVideo.pause();
        confettiVideo.classList.add("d-none");
    });
}

function startWinnerParty() {
    registerAction(function() {
        const endscreenSound = document.getElementById("endscreen-sound");
        if (endscreenSound) {
            endscreenSound.play();
            endscreenSound.onended = function() {
                startEndscreenAnimation();
            }
        }
        else {
            startEndscreenAnimation();
        }
    });
}

function revealContestantEditBtn(playerId) {
    let editBtn = document.querySelector(`.footer-contestant-${playerId} > .footer-contestant-edit-btn`);
    let saveImage = editBtn.querySelector(".footer-contestant-edit-save");
    if (!saveImage.classList.contains("d-none") && !editBtn.classList.contains("d-none")) {
        return;
    }

    revealEditBtnTimeout = setTimeout(function() {
        revealEditBtnTimeout = null;
        editBtn.classList.remove("d-none");
    }, 1500);
}

function hideContestantEditBtn(playerId) {
    let editBtn = document.querySelector(`.footer-contestant-${playerId} > .footer-contestant-edit-btn`);
    let saveImage = editBtn.querySelector(".footer-contestant-edit-save");
    if (!saveImage.classList.contains("d-none") && !editBtn.classList.contains("d-none")) {
        return;
    }

    if (revealEditBtnTimeout != null) {
        clearTimeout(revealEditBtnTimeout);
    }
    editBtn.classList.add("d-none");
}

function toggleEditContestantInfo(playerId) {
    let wrapper = document.querySelector(`.footer-contestant-${playerId}`);
    let editBtn = wrapper.querySelector(".footer-contestant-edit-btn");
    let removeBtn = wrapper.querySelector(".footer-contestant-remove-btn");

    let saveImage = editBtn.querySelector(".footer-contestant-edit-save");
    let editImage = editBtn.querySelector(".footer-contestant-edit-edit");

    let editable;
    if (saveImage.classList.contains("d-none")) {
        editImage.classList.add("d-none");
        saveImage.classList.remove("d-none");
        removeBtn.classList.remove("d-none");
        editable = true;
    }
    else {
        editImage.classList.remove("d-none");
        saveImage.classList.add("d-none");
        removeBtn.classList.add("d-none");
        editable = false;
    }

    let hitsElem = wrapper.querySelector(".footer-contestant-entry-hits");
    let missesElem = wrapper.querySelector(".footer-contestant-entry-misses");
    let scoreElem = wrapper.querySelector(".footer-contestant-entry-score");
    let powersWrapper = wrapper.querySelectorAll(".footer-contestant-entry-powers > div");

    hitsElem.contentEditable = editable;
    missesElem.contentEditable = editable;
    scoreElem.contentEditable = editable;

    powersWrapper.forEach((elem) => {
        if (editable) {
            let usedIcon = elem.querySelector(".footer-contestant-entry-power-used");
            elem.onclick = function() {
                if (usedIcon.classList.contains("d-none")) {
                    usedIcon.classList.remove("d-none");
                }
                else {
                    usedIcon.classList.add("d-none");
                }
            };
        }
        else {
            elem.onclick = null;
        }
    });

    if (!editable) {
        let hits = Number.parseInt(hitsElem.textContent);
        let misses = Number.parseInt(missesElem.textContent);
        let score = Number.parseInt(scoreElem.textContent.split(" ")[0]);

        let powersUsed = {};
        powersWrapper.forEach((elem) => {
            let classSplit = elem.className.split("-");;
            let powerId = classSplit[classSplit.length - 1];
            let used = !elem.querySelector(".footer-contestant-entry-power-used").classList.contains("d-none");
            powersUsed[powerId] = used;
        });

        let data = {"hits": hits, "misses": misses, "score": score, "powers": powersUsed};

        socket.emit("edit_contestant_info", playerId, JSON.stringify(data));
        editBtn.classList.add("d-none");
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
