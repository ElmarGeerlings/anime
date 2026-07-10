const DEVICE_KEY = 'anime_device_id';
const DEVICE_COOKIE = 'anime_device_id';

function getDeviceId() {
    let id = localStorage.getItem(DEVICE_KEY);
    if (!id) {
        id = crypto.randomUUID();
        localStorage.setItem(DEVICE_KEY, id);
    }
    document.cookie = `${DEVICE_COOKIE}=${id}; path=/; max-age=31536000; SameSite=Lax`;
    return id;
}

document.addEventListener('DOMContentLoaded', () => {
    const deviceId = getDeviceId();
    document.querySelectorAll('[name="device_id"]').forEach(el => {
        el.value = deviceId;
    });
});
