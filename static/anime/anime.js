const DEVICE_KEY = 'anime_device_id';
const DEVICE_COOKIE = 'anime_device_id';
const TIER_MODE_KEY = 'anime_tier_mode';

function getDeviceId() {
    let id = localStorage.getItem(DEVICE_KEY);
    if (!id) {
        id = crypto.randomUUID();
        localStorage.setItem(DEVICE_KEY, id);
    }
    document.cookie = `${DEVICE_COOKIE}=${id}; path=/; max-age=31536000; SameSite=Lax`;
    return id;
}

function getStoredTierMode() {
    const stored = localStorage.getItem(TIER_MODE_KEY);
    if (stored === 'text' || stored === 'posters') {
        return stored;
    }
    if (window.matchMedia('(max-width: 600px)').matches) {
        return 'text';
    }
    return 'posters';
}

function applyTierMode(mode) {
    const page = document.getElementById('anime-page');
    if (!page) {
        return;
    }
    if (mode === 'text') {
        page.classList.add('anime-page--text');
    } else {
        page.classList.remove('anime-page--text');
    }
    localStorage.setItem(TIER_MODE_KEY, mode);
    updateTierViewButtons(mode);
}

function updateTierViewButtons(mode) {
    const postersBtn = document.getElementById('tier-view-posters');
    const textBtn = document.getElementById('tier-view-text');
    if (!postersBtn || !textBtn) {
        return;
    }
    const isText = mode === 'text';
    postersBtn.setAttribute('aria-pressed', isText ? 'false' : 'true');
    textBtn.setAttribute('aria-pressed', isText ? 'true' : 'false');
    postersBtn.classList.toggle('tier-list-view-btn--active', !isText);
    textBtn.classList.toggle('tier-list-view-btn--active', isText);
}

document.addEventListener('DOMContentLoaded', () => {
    const deviceId = getDeviceId();
    document.querySelectorAll('[name="device_id"]').forEach(el => {
        el.value = deviceId;
    });

    const postersBtn = document.getElementById('tier-view-posters');
    const textBtn = document.getElementById('tier-view-text');
    if (postersBtn && textBtn) {
        const mode = getStoredTierMode();
        applyTierMode(mode);
        postersBtn.addEventListener('click', () => applyTierMode('posters'));
        textBtn.addEventListener('click', () => applyTierMode('text'));
    }
});
