function getBaseURL() {
    return window.location.protocol + "//" + window.location.hostname + ":" + window.location.port;
}

function getSpecificParent(element, parentClass) {
    while (element != null && !element.classList.contains(parentClass)) {
        element = element.parentElement;
    }

    return element;
}

function deletePack(event, packId) {
    event.stopPropagation();

    if (!confirm("Are you sure you want to delete this question pack?")) {
        return;
    }

    $.ajax(`${getBaseURL()}/jeoparty/pack/${packId}/delete`, 
        {method: "POST"}
    ).done(function() {
        let wrapper = document.getElementById("dashboard-questions-data");
        let entry = getSpecificParent(event.target, "dashboard-entry-wrapper");

        wrapper.removeChild(entry);

    }).fail(function(response) {
        let data = JSON.parse(response["responseText"]);
        alert(data["response"]);
    });
}