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

async function resizeImage(file, size) {
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");

    canvas.width = size
    canvas.height = size

    const bitmap = await createImageBitmap(file)
    const { width, height } = bitmap

    const ratio = Math.max(size / width, size / height)

    const x = (size - (width * ratio)) / 2
    const y = (size - (height * ratio)) / 2

    ctx.drawImage(bitmap, 0, 0, width, height, x, y, width * ratio, height * ratio)

    return new Promise(resolve => {
        canvas.toBlob(blob => {
            let newFile = new File([blob], file.name,  {type: file.type});
            resolve(newFile)
        }, "image/webp", 1)
    });
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

            let size = Number.parseInt(window.getComputedStyle(wrapper).width.replace("px", ""));
            resizeImage(file, size).then((resized) => {
                imageElem.src = URL.createObjectURL(resized);
                imageElem.alt = imageElem.title = file.name;
    
                let dataTransfer = new DataTransfer();
                dataTransfer.items.add(resized);
                avatarInput.files = dataTransfer.files;
    
                if (defaultAvatar != null) {
                    wrapper.removeChild(defaultAvatar);
                }
            });
        } else {
            alert(`${file.name}' is not a valid file type (should be .png, .gif, .jpg, or .webp).`);
        }
    }
}

function getRenderedColor(color) {
    const elem = document.createElement("div");
    elem.style.color = color;
    return elem.style.color.replace(/\s+/,'').toLowerCase();
}

function joinGame(event) {
    event.preventDefault();
    requestWakeLock();

    let color = document.getElementById("contestant-lobby-color").value;
    let errorMsg = document.getElementById("contestant-lobby-error");

    if (!getRenderedColor(color)) {
        errorMsg.textContent = `Invalid color: '${color}', please provide a valid color.`;
        errorMsg.classList.remove("d-none");
        return false;
    }

    let form = document.getElementById("contestant-join-form");
    let formData = new FormData(form);

    $.ajax(
        form.action,
        {
            data: formData,
            method: "POST",
            contentType: false,
            processData: false,
        }
    ).done(function(response) {
        window.location.href = response["redirect"];
    }).fail(function(response) {
        let message;
        if (Object.hasOwn(response, "responseJSON")) {
            message = JSON.parse(response["responseText"])["error"];
        }
        else {
            message = "An unknown error occured, try again later."
        }

        errorMsg.textContent = message;
        errorMsg.classList.remove("d-none");
    });

    return false;
}