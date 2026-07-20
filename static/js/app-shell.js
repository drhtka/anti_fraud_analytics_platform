import {
    ACTIVE_SCREEN_STORAGE_KEY,
    DEFAULT_SCREEN,
    getAvailableScreens,
    getScreens,
    screenTabs,
} from './dom-state.js';
import { ensureScreenLoaded } from './screen-loader.js';

function parseHashTarget(hashValue) {
    const cleaned = hashValue.replace('#', '').trim();
    const [screenName = '', anchorId = ''] = cleaned.split(':');
    return { screenName: screenName.trim(), anchorId: anchorId.trim() };
}

async function activateScreen(screenName) {
    await ensureScreenLoaded(screenName);

    localStorage.setItem(ACTIVE_SCREEN_STORAGE_KEY, screenName);
    const currentHash = window.location.hash || '';
    if (
        currentHash !== `#${screenName}` &&
        !currentHash.startsWith(`#${screenName}:`)
    ) {
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
    const hashScreen = parseHashTarget(window.location.hash).screenName;
    const savedScreen = localStorage.getItem(ACTIVE_SCREEN_STORAGE_KEY) ?? '';
    const availableScreens = getAvailableScreens();

    if (hashScreen && availableScreens.has(hashScreen)) {
        return hashScreen;
    }

    if (savedScreen && availableScreens.has(savedScreen)) {
        return savedScreen;
    }

    return DEFAULT_SCREEN;
}

function bindScreenTabs() {
    screenTabs.forEach((tab) => {
        tab.addEventListener('click', async () => {
            await activateScreen(tab.dataset.screenTarget);
        });
    });
}

function bindHashChange() {
    window.addEventListener('hashchange', async () => {
        const { screenName, anchorId } = parseHashTarget(window.location.hash);
        const availableScreens = getAvailableScreens();

        if (!screenName || !availableScreens.has(screenName)) {
            return;
        }

        await activateScreen(screenName);

        if (!anchorId) {
            return;
        }

        const anchor = document.getElementById(anchorId);
        if (anchor) {
            anchor.scrollIntoView({ block: 'start' });
        }
    });
}

function bindInternalHashLinks() {
    document.addEventListener('click', async (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }

        const link = event.target.closest('a[href^="#"]');
        if (!(link instanceof HTMLAnchorElement)) {
            return;
        }

        const href = link.getAttribute('href') ?? '';
        if (!href || href === '#') {
            return;
        }

        const { screenName, anchorId } = parseHashTarget(href);
        if (!screenName) {
            return;
        }

        const availableScreens = getAvailableScreens();
        if (!availableScreens.has(screenName)) {
            return;
        }

        event.preventDefault();

        if (window.location.hash !== href) {
            window.location.hash = href;
            return;
        }

        await activateScreen(screenName);

        if (!anchorId) {
            return;
        }

        const anchor = document.getElementById(anchorId);
        if (anchor) {
            anchor.scrollIntoView({ block: 'start' });
        }
    });
}

export {
    activateScreen,
    bindHashChange,
    bindInternalHashLinks,
    bindScreenTabs,
    getInitialScreenName,
    parseHashTarget,
};
