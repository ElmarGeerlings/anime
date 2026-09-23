function buildAnimeHeadingText(displayName, title) {
    if (displayName && displayName !== title) {
        return `${displayName} (${title})`;
    }
    return title;
}

function getDisplayNameCsrfToken() {
    const input = document.getElementById('anime-display-name-csrf');
    return input ? input.value : '';
}

document.addEventListener('DOMContentLoaded', () => {
    const heading = document.getElementById('anime-detail-heading');
    if (!heading || !heading.classList.contains('anime-detail-heading--editable')) {
        return;
    }

    const title = heading.dataset.title;
    const saveUrl = heading.dataset.saveUrl;
    const animeId = heading.dataset.animeId;

    function setHeadingText(displayName) {
        heading.textContent = buildAnimeHeadingText(displayName, title);
        heading.dataset.displayName = displayName;
    }

    function saveDisplayName(displayName) {
        const formData = new FormData();
        formData.append('anime_id', animeId);
        formData.append('display_name', displayName);
        formData.append('csrfmiddlewaretoken', getDisplayNameCsrfToken());

        fetch(saveUrl, {
            method: 'POST',
            body: formData,
            credentials: 'same-origin',
        }).then(response => {
            if (response.ok) {
                return response.json();
            }
        }).then(data => {
            if (data) {
                setHeadingText(data.display_name);
            }
        });
    }

    heading.addEventListener('click', () => {
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'anime-detail-heading-input';
        input.value = heading.dataset.displayName || '';
        input.maxLength = 80;
        heading.replaceWith(input);
        input.focus();
        input.select();

        let finished = false;

        function finish() {
            if (finished) {
                return;
            }
            finished = true;
            const newName = input.value.trim();
            input.replaceWith(heading);
            setHeadingText(newName);
            saveDisplayName(newName);
        }

        input.addEventListener('keydown', event => {
            if (event.key === 'Enter') {
                event.preventDefault();
                finish();
            }
        });
        input.addEventListener('blur', finish);
    });
});
