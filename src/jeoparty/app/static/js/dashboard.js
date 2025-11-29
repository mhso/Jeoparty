function getBaseURL() {
    return window.location.protocol + "//" + window.location.hostname + ":" + window.location.port;
}

function getSpecificParent(element, parentClass) {
    while (element != null && !element.classList.contains(parentClass)) {
        element = element.parentElement;
    }

    return element;
}

function deleteElement(id, name, desc, event, wrapperId) {
    event.stopPropagation();

    if (!confirm(`Are you sure you want to delete this ${desc}?`)) {
        return;
    }

    $.ajax(`${getBaseURL()}/jeoparty/${name}/${id}/delete`, 
        {method: "POST"}
    ).done(function() {
        let wrapper = document.getElementById(wrapperId);
        let entry = getSpecificParent(event.target, "dashboard-entry-wrapper");

        wrapper.removeChild(entry);

    }).fail(function(response) {
        let data = JSON.parse(response["responseText"]);
        alert(data["response"]);
    });
}

function deletePack(event, packId) {
    deleteElement(packId, "pack", "question pack", event, "dashboard-questions-data");
}

function deleteGame(event, gameId) {
    deleteElement(gameId, "game", "game", event, "dashboard-games-data");
}