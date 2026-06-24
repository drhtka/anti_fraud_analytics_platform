const transactionForm = document.getElementById('transaction-form');
const clearFormButton = document.getElementById('clear-form');
const demoButtons = document.querySelectorAll('[data-demo-key]');
const screenTabs = document.querySelectorAll('[data-screen-target]');
const demoPayloadsElement = document.getElementById('demo-payloads-json');

const demoPayloads = demoPayloadsElement
    ? JSON.parse(demoPayloadsElement.textContent)
    : [];
const DEFAULT_SCREEN = 'score';
const ACTIVE_SCREEN_STORAGE_KEY = 'anti-fraud-active-screen';

function getScreens() {
    return document.querySelectorAll('[data-screen-name]');
}

async function ensureScreenLoaded(screenName) {
    const screen = document.querySelector(`[data-screen-name="${screenName}"]`);

    if (!screen) {
        return;
    }

    const deferredUrl = screen.dataset.deferredUrl;
    const alreadyLoaded = screen.dataset.loaded === 'true';

    if (!deferredUrl || alreadyLoaded) {
        return;
    }

    screen.dataset.loaded = 'loading';
    screen.innerHTML = `
        <article class="content-card deferred-card">
            <h2>Завантаження</h2>
            <p class="deferred-hint">Рендеримо вміст розділу ${screenName.toUpperCase()}...</p>
        </article>
    `;

    try {
        const response = await fetch(deferredUrl, {
            headers: {
                'X-Requested-With': 'fetch',
            },
        });

        if (!response.ok) {
            throw new Error(`Request failed with status ${response.status}`);
        }

        const html = await response.text();
        screen.outerHTML = html;
    } catch (error) {
        screen.dataset.loaded = 'error';
        screen.innerHTML = `
            <article class="content-card deferred-card">
                <h2>Помилка завантаження</h2>
                <p class="deferred-hint">Не вдалося завантажити вміст розділу ${screenName.toUpperCase()}.</p>
            </article>
        `;
    }
}

async function activateScreen(screenName) {
    await ensureScreenLoaded(screenName);

    localStorage.setItem(ACTIVE_SCREEN_STORAGE_KEY, screenName);
    if (window.location.hash !== `#${screenName}`) {
        window.location.hash = screenName;
    }

    screenTabs.forEach((tab) => {
        const isActive = tab.dataset.screenTarget === screenName;
        tab.classList.toggle('is-active', isActive);
        tab.setAttribute('aria-pressed', String(isActive));
    });

    getScreens().forEach((screen) => {
        screen.hidden = screen.dataset.screenName !== screenName;
    });
}

function getInitialScreenName() {
    const hashScreen = window.location.hash.replace('#', '').trim();
    const savedScreen = localStorage.getItem(ACTIVE_SCREEN_STORAGE_KEY) ?? '';
    const availableScreens = new Set(
        Array.from(screenTabs).map((tab) => tab.dataset.screenTarget),
    );

    if (hashScreen && availableScreens.has(hashScreen)) {
        return hashScreen;
    }

    if (savedScreen && availableScreens.has(savedScreen)) {
        return savedScreen;
    }

    return DEFAULT_SCREEN;
}

screenTabs.forEach((tab) => {
    tab.addEventListener('click', async () => {
        await activateScreen(tab.dataset.screenTarget);
    });
});

window.addEventListener('hashchange', async () => {
    const hashScreen = window.location.hash.replace('#', '').trim();
    const availableScreens = new Set(
        Array.from(screenTabs).map((tab) => tab.dataset.screenTarget),
    );

    if (!hashScreen || !availableScreens.has(hashScreen)) {
        return;
    }

    await activateScreen(hashScreen);
});

activateScreen(getInitialScreenName());

demoButtons.forEach((button) => {
    button.addEventListener('click', () => {
        const payloadKey = button.dataset.demoKey;
        const payloadEntry = demoPayloads.find(
            (entry) => entry.filename === payloadKey,
        );
        const payload = payloadEntry?.payload;

        if (!payload || !transactionForm) {
            return;
        }

        Object.entries(payload).forEach(([fieldName, fieldValue]) => {
            const input = transactionForm.elements.namedItem(fieldName);

            if (!(input instanceof HTMLInputElement)) {
                return;
            }

            input.value = fieldValue ?? '';
        });
    });
});

if (clearFormButton && transactionForm) {
    clearFormButton.addEventListener('click', () => {
        Array.from(transactionForm.elements).forEach((element) => {
            if (!(element instanceof HTMLInputElement)) {
                return;
            }

            element.value = '';
        });
    });
}
