function getCsrfToken() {
    const input = document.querySelector('#tier-maker [name=csrfmiddlewaretoken]');
    if (input) {
        return input.value;
    }
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
}

function serializeTierlist() {
    const tiers = {};
    document.querySelectorAll('.tier-maker-drop[data-tier]').forEach(drop => {
        const tier = drop.dataset.tier;
        if (!tier) {
            return;
        }
        tiers[tier] = Array.from(drop.querySelectorAll('[data-anime-id]')).map(
            el => el.dataset.animeId
        );
    });
    return tiers;
}

function setStatus(message) {
    const status = document.getElementById('tier-maker-status');
    if (status) {
        status.textContent = message;
    }
}

let saveTimer = null;

function scheduleSave() {
    clearTimeout(saveTimer);
    setStatus('Saving…');
    saveTimer = setTimeout(saveTierlist, 400);
}

function saveTierlist() {
    const maker = document.getElementById('tier-maker');
    if (!maker) {
        return;
    }
    const deviceInput = maker.querySelector('[name=device_id]');
    const deviceId = deviceInput ? deviceInput.value : '';
    const formData = new FormData();
    formData.append('device_id', deviceId);
    formData.append('tiers', JSON.stringify(serializeTierlist()));
    formData.append('csrfmiddlewaretoken', getCsrfToken());

    fetch(maker.dataset.saveUrl, {
        method: 'POST',
        body: formData,
        credentials: 'same-origin',
    }).then(response => {
        if (response.ok) {
            setStatus('Saved');
            return;
        }
        setStatus('Save failed');
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const maker = document.getElementById('tier-maker');
    if (!maker || typeof Sortable === 'undefined') {
        return;
    }

    const deviceInput = maker.querySelector('[name=device_id]');
    if (deviceInput && typeof getDeviceId === 'function') {
        deviceInput.value = getDeviceId();
    }

    document.querySelectorAll('.tier-maker-drop').forEach(drop => {
        Sortable.create(drop, {
            group: 'tierlist',
            animation: 150,
            delay: 120,
            delayOnTouchOnly: true,
            touchStartThreshold: 3,
            draggable: '.tier-item--draggable',
            ghostClass: 'tier-item--ghost',
            chosenClass: 'tier-item--chosen',
            onEnd: scheduleSave,
        });
    });
});
