import {
    inFlightScreenLoads,
    getCurrentLanguage,
    getUiTexts,
} from './dom-state.js';
import { initDashboardEmbeds } from './dashboard-embed.js';

function reportDeferredDebug(event, payload = {}) {
    try {
        const body = JSON.stringify({
            event,
            payload,
            href: window.location.href,
            ua: window.navigator.userAgent,
            at: new Date().toISOString(),
        });
        if (navigator.sendBeacon) {
            navigator.sendBeacon('/api/debug/deferred-tabs', body);
            return;
        }
        fetch('/api/debug/deferred-tabs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body,
            keepalive: true,
            credentials: 'same-origin',
        }).catch(() => {});
    } catch (_) {
        // no-op
    }
}

function normalizeDeferredUrl(value) {
    const url = new URL(value, window.location.origin);
    url.protocol = window.location.protocol;
    url.host = window.location.host;
    url.searchParams.set('lang', getCurrentLanguage());
    return url.toString();
}

function getScreenLabel(screenName) {
    const uiTexts = getUiTexts();
    return uiTexts.screenLabels?.[screenName] ?? screenName.toUpperCase();
}

async function ensureScreenLoaded(screenName) {
    const screen = document.querySelector(`[data-screen-name="${screenName}"]`);

    reportDeferredDebug('ensure_screen_loaded_start', {
        screenName,
        hasScreen: Boolean(screen),
    });

    if (!screen) {
        return;
    }

    const deferredUrl = screen.dataset.deferredUrl;
    const requestUrl = deferredUrl ? normalizeDeferredUrl(deferredUrl) : null;
    const currentLoadState = screen.dataset.loaded;
    const alreadyLoaded = currentLoadState === 'true';

    reportDeferredDebug('ensure_screen_loaded_state', {
        screenName,
        deferredUrl,
        requestUrl,
        loaded: screen.dataset.loaded,
        hidden: screen.hidden,
    });

    if (!requestUrl || alreadyLoaded) {
        return;
    }

    if (currentLoadState === 'loading') {
        return inFlightScreenLoads.get(screenName);
    }

    screen.dataset.loaded = 'loading';
    const uiTexts = getUiTexts();
    screen.innerHTML = `
        <article class="content-card deferred-card">
            <h2>${uiTexts.loadingTitle ?? 'Завантаження'}</h2>
            <p class="deferred-hint">${uiTexts.loadingHintPrefix ?? 'Рендеримо вміст розділу'} ${getScreenLabel(screenName)}...</p>
        </article>
    `;

    const loadPromise = (async () => {
        try {
            const response = await fetch(requestUrl, {
                headers: {
                    'X-Requested-With': 'fetch',
                },
                credentials: 'same-origin',
            });

            reportDeferredDebug('ensure_screen_loaded_response', {
                screenName,
                status: response.status,
                ok: response.ok,
                redirected: response.redirected,
                contentType: response.headers.get('content-type'),
                finalUrl: response.url,
            });

            if (!response.ok) {
                throw new Error(`Request failed with status ${response.status}`);
            }

            const html = await response.text();
            const nextScreen = document.createElement('template');
            nextScreen.innerHTML = html.trim();
            const renderedScreen = nextScreen.content.firstElementChild;

            reportDeferredDebug('ensure_screen_loaded_html', {
                screenName,
                htmlPreview: html.slice(0, 200),
                hasRenderedScreen: renderedScreen instanceof HTMLElement,
                renderedTag: renderedScreen?.tagName ?? null,
                renderedName: renderedScreen?.dataset?.screenName ?? null,
            });

            if (!(renderedScreen instanceof HTMLElement)) {
                throw new Error(
                    'Deferred screen did not return a valid root element',
                );
            }

            renderedScreen.hidden = screen.dataset.screenName !== screenName;
            renderedScreen.dataset.loaded = 'true';
            screen.replaceWith(renderedScreen);
            initDashboardEmbeds();

            reportDeferredDebug('ensure_screen_loaded_success', {
                screenName,
                hidden: renderedScreen.hidden,
                loaded: renderedScreen.dataset.loaded,
            });
        } catch (error) {
            const uiTexts = getUiTexts();
            reportDeferredDebug('ensure_screen_loaded_error', {
                screenName,
                message: error instanceof Error ? error.message : String(error),
            });
            screen.dataset.loaded = 'error';
            screen.innerHTML = `
                <article class="content-card deferred-card">
                    <h2>${uiTexts.loadingErrorTitle ?? 'Помилка завантаження'}</h2>
                    <p class="deferred-hint">${uiTexts.loadingErrorPrefix ?? 'Не вдалося завантажити вміст розділу'} ${getScreenLabel(screenName)}.</p>
                </article>
            `;
        } finally {
            inFlightScreenLoads.delete(screenName);
        }
    })();

    inFlightScreenLoads.set(screenName, loadPromise);
    return loadPromise;
}

export { ensureScreenLoaded };
