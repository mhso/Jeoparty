// Create socket bound to specific game ID.
// 'game_id' is defined before this JS file is imported
const CONN_ATTEMPTS = 3;
var socket;
for (let i = 0; i < CONN_ATTEMPTS; i++) {
    try {
        socket = io(`/${GAME_ID}`, {"transports": ["websocket", "polling"], "rememberUpgrade": true, "timeout": 10000});
        socket.on("connect_error", function(err) {
            console.error("Contestant socket connection error:", err);
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
        console.log(`CONTESTANT --- ERROR #${i} WHEN CONNECTING TO SOCKET IO!`);
        console.log(err);
    }
}

requestWakeLock();

var pingActive = true;
var buzzerResetTimeout = null;

function makeDailyDoubleWager(playerId) {
    let btn = document.getElementById("contestant-wager-btn");
    if (btn.disabled) {
        return;
    }

    btn.disabled = true;
    let value = document.getElementById("daily-wager-input").value;
    socket.once("daily_wager_made", function(amount) {
        btn.classList.add("wager-made");
    });
    socket.emit("make_daily_wager", playerId, value);
}

function makeFinalJeopardyWager(playerId) {
    let btn = document.getElementById("contestant-wager-btn");

    let value = document.getElementById("finale-wager-input").value;
    socket.once("finale_wager_made", function() {
        btn.classList.add("wager-made");
    });
    socket.emit("make_finale_wager", playerId, value);
}

function giveFinalJeopardyAnswer(playerId) {
    let btn = document.getElementById("contestant-wager-btn");

    let answer = document.getElementById("finale-answer").value;
    socket.once("finale_answer_given", function() {
        btn.classList.add("wager-made");
    });
    socket.emit("give_finale_answer", playerId, answer);
}

function pressBuzzer(playerId) {
    console.log("Pressing buzzer:", playerId);
    let activeBuzzer = document.getElementById("buzzer-active");
    if (activeBuzzer.classList.contains("d-none")) {
        return;
    }

    activeBuzzer.classList.add("d-none");

    document.getElementById("buzzer-pressed").classList.remove("d-none");

    socket.emit("buzzer_pressed", playerId);

    if (wakeLock == null) {
        requestWakeLock();
    }
}

function resetBuzzerStatusImg(elem) {
    elem.style.animationName = "none";
    elem.offsetHeight; // Trigger reflow
    elem.style.animationName = null;
    elem.classList.add("d-none");
}

function resetBuzzerState(buzzerStatus) {
    let buzzerWinnerImg = document.getElementById("buzzer-winner");
    let buzzerLoserImg = document.getElementById("buzzer-loser");

    // Reset and hide buzzer status after a delay
    resetBuzzerStatusImg(buzzerWinnerImg);
    resetBuzzerStatusImg(buzzerLoserImg);

    buzzerStatus.classList.add("d-none");
    buzzerStatus.style.opacity = 0;
}

function handleBuzzInResult(imageToShow) {
    let buzzerActive = document.getElementById("buzzer-active");
    let buzzerInactive = document.getElementById("buzzer-inactive");
    let buzzerPressed = document.getElementById("buzzer-pressed");
    let buzzerStatus = document.getElementById("contestant-buzzer-status");

    buzzerActive.classList.add("d-none");
    buzzerPressed.classList.add("d-none");
    buzzerInactive.classList.remove("d-none");

    buzzerStatus.classList.remove("d-none");
    buzzerStatus.style.opacity = 1;
    imageToShow.classList.remove("d-none");
    imageToShow.style.animationName = "showBuzzerStatus";

    buzzerResetTimeout = setTimeout(function() {
        resetBuzzerState(buzzerStatus);
    }, 1600);
}

function usePowerUp(playerId, powerId) {
    let btn = document.getElementById(`contestant-power-btn-${powerId}`);
    btn.disabled = true;

    socket.emit("use_power_up", playerId, powerId);
}

function togglePowerUpsEnabled(playerId, powerIds, enabled) {
    powerIds.forEach((powerId) => {
        let btn = document.getElementById(`contestant-power-btn-${powerId}`);
        let powerIcon = btn.getElementsByClassName("contestant-power-icon").item(0);

        if (enabled && powerIcon.classList.contains("power-disabled")) {
            powerIcon.classList.remove("power-disabled");
            btn.onclick = () => usePowerUp(playerId, powerId);
        }
        else if (!enabled && !powerIcon.classList.contains("power-disabled")) {
            powerIcon.classList.add("power-disabled");
        }

        btn.disabled = !enabled;
    });
}

function monitorGame(userId, localeJson) {
    let localeData = JSON.parse(localeJson);

    let buzzerActive = document.getElementById("buzzer-active");
    let buzzerInactive = document.getElementById("buzzer-inactive");
    let buzzerPressed = document.getElementById("buzzer-pressed");
    let buzzerStatus = document.getElementById("contestant-buzzer-status");
    let pingElem = document.getElementById("contestant-game-ping");
    let buzzerWinnerImg = document.getElementById("buzzer-winner");
    let buzzerLoserImg = document.getElementById("buzzer-loser");

    socket.on("state_changed", function() {
        socket.close();
        window.location.reload();
    });

    // Called when question has been asked and buzzing has been enabled.
    socket.on("buzz_enabled", function() {
        if (!buzzerStatus.classList.contains("d-none")) {
            if (buzzerResetTimeout) {
                clearTimeout(buzzerResetTimeout);
            }
            resetBuzzerState(buzzerStatus);
        }
        buzzerInactive.classList.add("d-none");
        buzzerActive.classList.remove("d-none");
    });

    socket.on("buzz_received", function() {
        let buzzesElem = document.getElementById("contestant-game-buzzes");
        let buzzes = Number.parseInt(buzzesElem.textContent.replace("buzzes", "").trim());
        buzzesElem.textContent = `${buzzes + 1} buzzes`;
    });

    socket.on("buzz_disabled", function() {
        buzzerActive.classList.add("d-none");
        buzzerPressed.classList.add("d-none");
        buzzerInactive.classList.remove("d-none");

        if (buzzerStatus.classList.contains("d-none")) {
            buzzerStatus.classList.remove("d-none");
            buzzerStatus.style.opacity = 1;
        }
    });

    // Called when this person was the fastest to buzz in during a question.
    socket.on("buzz_winner", function() {
        console.log("We won the buzz!");
        handleBuzzInResult(buzzerWinnerImg);
    });

    // Called when this person was not the fastest to buzz in during a question.
    socket.on("buzz_loser", function() {
        console.log("We lost the buzz!");
        if (!buzzerStatus.classList.contains("d-none")) {
            // We already buzzed in (and answered incorrectly) previously
            return;
        }

        handleBuzzInResult(buzzerLoserImg);
    });

    // Called whenever a powerup is available to use
    socket.on("power_up_enabled", function(powerId) {
        togglePowerUpsEnabled(userId, [powerId], true);
    });

    // Called whenever a powerup is no longer available to use
    socket.on("power_ups_disabled", function(powerIds) {
        togglePowerUpsEnabled(userId, powerIds, false);
    });

    // Called whenever we have successfully used a power-up
    socket.on("power_up_used", function(powerId) {
        let usedIcon = document.querySelector(`#contestant-power-btn-${powerId} > .contestant-power-used`);
        usedIcon.classList.remove("d-none");

        if (powerId == "freeze") {
            return;
        }

        if (!buzzerStatus.classList.contains("d-none")) {
            buzzerStatus.classList.add("d-none");
            buzzerStatus.style.opacity = 0;
        }
    });

    // Called when game values for this contestant has changed
    socket.on("contestant_info_changed", function(jsonStr) {
        let data = JSON.parse(jsonStr);
        if (Object.hasOwn(data, "score")) {
            data["score"] = data["score"] + " " + localeData["points"];
        }

        let keys = ["hits", "misses", "score"];
        keys.forEach((k) => {
            if (Object.hasOwn(data, k)) {
                document.getElementById(`contestant-game-${k}`).textContent = data[k];
            }
        });
        
        if (Object.hasOwn(data, "powers")) {
            let usedPowers = data["powers"];
            let powerElements = document.querySelectorAll("#contestant-power-ups > button");
            powerElements.forEach((elem) => {
                let powerIcon = elem.querySelector(".contestant-power-icon");
                let usedIcon = elem.querySelector(".contestant-power-used");
                let split = elem.id.split("-");
                let powerId = split[split.length - 1];
                if (Object.hasOwn(usedPowers, powerId)) {
                    if (usedPowers[powerId]) {
                        elem.disabled = true;
                        usedIcon.classList.remove("d-none");
                        powerIcon.classList.add("power-disabled");
                    }
                    else {
                        elem.disabled = false;
                        usedIcon.classList.add("d-none");
                        powerIcon.classList.remove("power-disabled");
                    }
                }
            });
        }
    });

    // Called whenever the server has received our ping request.
    socket.on("ping_response", function(userId, timeSent) {
        let timeReceived = (new Date()).getTime();
        socket.emit("calculate_ping", userId, timeSent, timeReceived);
    });

    // Called whenever the server has calculated our ping.
    socket.on("ping_calculated", function(ping) {
        pingElem.textContent = ping + " ms";
        let pingNum = Number.parseFloat(ping);

        if (pingNum < 50) {
            pingElem.className = "contestant-low-ping";
        }
        else if (pingNum < 100) {
            pingElem.className = "contestant-moderate-ping";
        }
        else {
            pingElem.className = "contestant-high-ping";
        }
    });

    // Called when person has made a wager that is invalid
    socket.on("invalid_wager", function(minWager, maxWager) {
        let btn = document.getElementById("contestant-wager-btn");
        btn.disabled = false;
        alert(`${localeData["invalid_wager"]} ${minWager} ${localeData['and']} ${maxWager}`);
    });
}

function getUTCTimestamp() {
    let date = new Date();
    return new Date(
        date.getUTCFullYear(),
        date.getUTCMonth(),
        date.getUTCDate(),
        date.getUTCHours(),
        date.getUTCMinutes(),
        date.getUTCSeconds(),
        date.getUTCMilliseconds()
    ).getTime();
}

function sendPingMessage(userId) {
    setTimeout(function() {
        if (!pingActive) {
            return;
        }
        now = (new Date()).getTime();
        socket.emit("ping_request", userId, now);
        sendPingMessage(userId);
    }, 1000);
}

window.addEventListener("DOMContentLoaded", function() {
    let questionHeader = document.getElementById("question-category-header");
    if (questionHeader != null) {
        let size = (window.innerWidth / questionHeader.textContent.length * 2.2);
        questionHeader.style.fontSize = size + "px";
        let questionChoices = document.getElementById("question-choices-indicator");
        if (questionChoices != null) {
            questionChoices.style.height = (size - 5) + "px";
        }
    }
});