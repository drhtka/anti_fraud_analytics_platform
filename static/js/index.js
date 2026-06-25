const transactionForm = document.getElementById('transaction-form');
const clearFormButton = document.getElementById('clear-form');
const demoButtons = document.querySelectorAll('[data-demo-key]');
const screenTabs = document.querySelectorAll('[data-screen-target]');
const demoPayloadsElement = document.getElementById('demo-payloads-json');
const scenarioModal = document.getElementById('scenario-modal');
const closeScenarioModalButton = document.getElementById('close-scenario-modal');

const demoPayloads = demoPayloadsElement
    ? JSON.parse(demoPayloadsElement.textContent)
    : [];
const DEFAULT_SCREEN = 'score';
const ACTIVE_SCREEN_STORAGE_KEY = 'anti-fraud-active-screen';
let selectedDemoKey = '';

function showScenarioModal() {
    if (!(scenarioModal instanceof HTMLDivElement)) {
        return;
    }

    scenarioModal.hidden = false;
}

function hideScenarioModal() {
    if (!(scenarioModal instanceof HTMLDivElement)) {
        return;
    }

    scenarioModal.hidden = true;
}

function updateSelectedDemoButton(nextDemoKey) {
    selectedDemoKey = nextDemoKey;

    demoButtons.forEach((button) => {
        const isActive = button.dataset.demoKey === nextDemoKey;
        button.classList.toggle('is-selected', isActive);
        button.setAttribute('aria-pressed', String(isActive));
    });
}

function hideDashboardLoading(frameCard) {
    if (!(frameCard instanceof HTMLElement) || frameCard.dataset.ready === 'true') {
        return;
    }

    frameCard.dataset.ready = 'true';
    frameCard.classList.remove('is-soft-loading');
    frameCard.classList.remove('is-loading');
}

function iframeHasStartedLoading(iframe) {
    try {
        const currentHref = iframe.contentWindow?.location?.href;
        return Boolean(currentHref && currentHref !== 'about:blank');
    } catch (error) {
        // Cross-origin access starts throwing once the iframe navigates away from about:blank.
        return true;
    }
}

function getScreens() {
    return document.querySelectorAll('[data-screen-name]');
}

function initDashboardEmbeds() {
    const dashboardIframes = document.querySelectorAll('.dashboard-iframe');

    dashboardIframes.forEach((iframe) => {
        if (!(iframe instanceof HTMLIFrameElement)) {
            return;
        }

        const frameCard = iframe.closest('.dashboard-frame-card');

        if (!(frameCard instanceof HTMLElement)) {
            return;
        }

        const finishLoading = () => {
            hideDashboardLoading(frameCard);
        };

        const softenLoading = () => {
            if (frameCard.dataset.ready === 'true') {
                return;
            }

            frameCard.classList.add('is-soft-loading');
        };

        if (iframeHasStartedLoading(iframe)) {
            softenLoading();
        }

        if (iframe.dataset.bound !== 'true') {
            iframe.dataset.bound = 'true';
            iframe.addEventListener('load', finishLoading, { once: true });
        }

        if (frameCard.dataset.fallbackScheduled !== 'true') {
            frameCard.dataset.fallbackScheduled = 'true';
            window.setTimeout(softenLoading, 900);
        }
    });
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
            credentials: 'same-origin',
        });

        if (!response.ok) {
            throw new Error(`Request failed with status ${response.status}`);
        }

        const html = await response.text();
        const nextScreen = document.createElement('template');
        nextScreen.innerHTML = html.trim();
        const renderedScreen = nextScreen.content.firstElementChild;

        if (!(renderedScreen instanceof HTMLElement)) {
            throw new Error('Deferred screen did not return a valid root element');
        }

        renderedScreen.hidden = false;
        renderedScreen.dataset.loaded = 'true';
        screen.replaceWith(renderedScreen);
        initDashboardEmbeds();
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
initDashboardEmbeds();

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

        hideScenarioModal();
        updateSelectedDemoButton(payloadKey);

        Object.entries(payload).forEach(([fieldName, fieldValue]) => {
            const input = transactionForm.elements.namedItem(fieldName);

            if (!(input instanceof HTMLInputElement)) {
                return;
            }

            input.value = fieldValue ?? '';
        });
    });
});

if (closeScenarioModalButton) {
    closeScenarioModalButton.addEventListener('click', () => {
        hideScenarioModal();
    });
}

if (scenarioModal instanceof HTMLDivElement) {
    scenarioModal.addEventListener('click', (event) => {
        if (event.target === scenarioModal) {
            hideScenarioModal();
        }
    });
}

if (transactionForm) {
    transactionForm.addEventListener('submit', (event) => {
        if (selectedDemoKey) {
            return;
        }

        event.preventDefault();
        showScenarioModal();
    });
}

if (clearFormButton && transactionForm) {
    clearFormButton.addEventListener('click', () => {
        const cleanUrl = `${window.location.pathname}${window.location.hash || ''}`;
        window.location.assign(cleanUrl);
    });
}
