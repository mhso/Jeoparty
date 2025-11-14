// Create a 'Wake Lock' to keep the contestant phone screen from turning off
// while the game is active
let wakeLock = null;
let wakeLockSupported = false;

if ("wakeLock" in navigator) {
    wakeLockSupported = true;
    console.log("Screen Wake Lock API supported!")
} else {
    console.log("Wake lock is not supported by this browser.");
}

const requestWakeLock = async () => {
    if (!wakeLockSupported) {
        return;
    }

    try {
        wakeLock = await navigator.wakeLock.request("screen");
        console.log("Wake Lock acquired!");

        wakeLock.addEventListener("release", () => {
            console.log("Wake Lock has been released!");
        });
    } catch (err) {
        // The Wake Lock request has failed - usually system related, such as battery.
        console.warn(`Could not acquire wake lock: ${err.name}, ${err.message}`);
    }
}

document.addEventListener("visibilitychange", async () => {
    // Create new wakelock if user navigates to another tab
    if (wakeLock !== null && document.visibilityState === "visible") {
        requestWakeLock();
    }
});
