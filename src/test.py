import requests

_VALID_IMAGE_FILETYPES = [
    "image/apng",
    "image/gif",
    "image/jpeg",
    "image/jpg",
    "image/pjpeg",
    "image/png",
    "image/webp",
]

_VALID_VIDEO_FILETYPES = [
    "video/webm",
    "video/mp4",
]

def go_fetch(url):
    # First try to do an 'options' request to just get content-type header
    response = requests.options(url)
    content_type = None

    all_valid_types = _VALID_IMAGE_FILETYPES + _VALID_VIDEO_FILETYPES

    if response.status_code == 200:
        content_type = response.headers.get("Content-Type")

    if content_type is None or content_type not in all_valid_types:
        # If response is invalid, return error
        response = requests.get(url)
        if response.status_code != 200:
            print("It didn't work 2...", "Status:", response.status_code, response.text)
            return

        # If content-type was valid or 'options' request failed, get the full file
        content_type = response.headers.get("Content-Type")
        if content_type not in all_valid_types:
            print("It didn't work 3...", "Content-Type", content_type)
            return

        print("It worked!", content_type)

url = "https://imengine.public.mhm.infomaker.io/?uuid=422c3ae2-436b-531a-b1b1-07721245ec2f"
go_fetch(url)
