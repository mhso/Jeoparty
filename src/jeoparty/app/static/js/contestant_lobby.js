function setRandomColor() {
    let colorInput = document.getElementById("contestant-lobby-color");

    let randRed = (Math.random() * 255).toString(16).split(".")[0];
    if (randRed == "0") {
        randRed = "00";
    }
    let randGreen = (Math.random() * 255).toString(16).split(".")[0];
    if (randGreen == "0") {
        randGreen = "00";
    }
    let randBlue = (Math.random() * 255).toString(16).split(".")[0];
    if (randBlue == "0") {
        randBlue = "00";
    }

    colorInput.type = "color";
    colorInput.value = `#${randRed}${randGreen}${randBlue}`;
}

const fileTypes = [
  "image/apng",
  "image/gif",
  "image/jpeg",
  "image/pjpeg",
  "image/png",
  "image/webp",
];

function validFileType(file) {
    return fileTypes.includes(file.type);
}

function updateAvatarImg() {
    let avatarInput = document.getElementById("contestant-lobby-avatar-input");
    let defaultAvatar = document.getElementById("contestant-lobby-default-avatar");
    let wrapper = document.getElementById("contestant-lobby-avatar-wrapper");

    let files = avatarInput.files;
    if (files.length != 0) {
        let file = files[0];
        if (validFileType(file)) {
            let imageElem = document.getElementById("contestant-lobby-avatar-img");
            imageElem.src = URL.createObjectURL(file);
            imageElem.alt = imageElem.title = file.name;

            if (defaultAvatar != null) {
                wrapper.removeChild(defaultAvatar);
            }
        } else {
            alert(`${file.name}' is a valid file type.`);
        }
    }
}

function getRenderedColor(color) {
    const elem = document.createElement("div");
    elem.style.color = color;
    return elem.style.color.replace(/\s+/,'').toLowerCase();
}

function validateForm() {
    let color = document.getElementById("contestant-lobby-color").value;

    if (!getRenderedColor(color)) {
        alert(`Invalid color: '${color}', please provide a valid color.`);
        return false;
    }

    return true;
}