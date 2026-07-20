import {
    LANGUAGE_STORAGE_KEY,
    SCORE_RESULT_SCROLL_STORAGE_KEY,
    getCurrentLanguage,
    languageSwitchButtons,
} from './dom-state.js';

const TRANSLATE_ONLY_QUERY_PARAM = 'ui_translate';
const LANGUAGE_PAGE_CACHE_PREFIX = 'anti-fraud-language-page:';
const inFlightLanguageFetches = new Map();

function buildUrlWithLanguage(targetLanguage, baseUrl = window.location.href) {
    const nextUrl = new URL(baseUrl, window.location.origin);
    nextUrl.searchParams.set('lang', targetLanguage);
    return nextUrl;
}

function getStaticAssetFingerprint() {
    return (
        document
            .querySelector('script[src*="/static/js/index.js"]')
            ?.getAttribute('src') ?? 'no-asset-fingerprint'
    );
}

function buildTranslateOnlyUrl(targetLanguage, baseUrl = window.location.href) {
    const nextUrl = buildUrlWithLanguage(targetLanguage, baseUrl);
    nextUrl.searchParams.set(TRANSLATE_ONLY_QUERY_PARAM, '1');

    const scoreStatusCard = document.querySelector('[data-score-status-card]');
    if (!(scoreStatusCard instanceof HTMLElement)) {
        return nextUrl;
    }

    nextUrl.searchParams.set(
        'ui_score_source',
        scoreStatusCard.dataset.scoreSource ?? '',
    );
    nextUrl.searchParams.set(
        'ui_event_status',
        scoreStatusCard.dataset.eventStatus ?? '',
    );
    nextUrl.searchParams.set(
        'ui_event_sink',
        scoreStatusCard.dataset.eventSink ?? '',
    );
    nextUrl.searchParams.set('ui_event_id', scoreStatusCard.dataset.eventId ?? '');
    nextUrl.searchParams.set(
        'ui_scored_at',
        scoreStatusCard.dataset.scoredAt ?? '',
    );

    return nextUrl;
}

function stripTranslateOnlyParams(urlLike) {
    const cleanUrl = new URL(urlLike, window.location.origin);

    [
        TRANSLATE_ONLY_QUERY_PARAM,
        'ui_score_source',
        'ui_event_status',
        'ui_event_sink',
        'ui_event_id',
        'ui_scored_at',
    ].forEach((paramName) => {
        cleanUrl.searchParams.delete(paramName);
    });

    return cleanUrl;
}

function buildLanguagePageCacheKey(targetLanguage, baseUrl = window.location.href) {
    return [
        LANGUAGE_PAGE_CACHE_PREFIX,
        getStaticAssetFingerprint(),
        buildTranslateOnlyUrl(targetLanguage, baseUrl).toString(),
    ].join(':');
}

function getCachedLanguagePage(targetLanguage, baseUrl = window.location.href) {
    try {
        return sessionStorage.getItem(
            buildLanguagePageCacheKey(targetLanguage, baseUrl),
        );
    } catch (_) {
        return null;
    }
}

function setCachedLanguagePage(
    targetLanguage,
    html,
    baseUrl = window.location.href,
) {
    try {
        sessionStorage.setItem(
            buildLanguagePageCacheKey(targetLanguage, baseUrl),
            html,
        );
    } catch (_) {
        // no-op
    }
}

async function fetchLanguagePageHtml(
    targetLanguage,
    baseUrl = window.location.href,
) {
    const cachedHtml = getCachedLanguagePage(targetLanguage, baseUrl);
    if (cachedHtml) {
        return cachedHtml;
    }

    const requestUrl = buildTranslateOnlyUrl(targetLanguage, baseUrl).toString();
    const existingRequest = inFlightLanguageFetches.get(requestUrl);
    if (existingRequest) {
        return existingRequest;
    }

    const requestPromise = fetch(requestUrl, {
        credentials: 'same-origin',
        headers: {
            'X-Requested-With': 'fetch',
        },
    })
        .then((response) => {
            if (!response.ok) {
                throw new Error(`Language page request failed: ${response.status}`);
            }

            return response.text();
        })
        .then((html) => {
            setCachedLanguagePage(targetLanguage, html, baseUrl);
            return html;
        })
        .finally(() => {
            inFlightLanguageFetches.delete(requestUrl);
        });

    inFlightLanguageFetches.set(requestUrl, requestPromise);
    return requestPromise;
}

function replaceDocumentWithLanguageHtml(html, targetLanguage) {
    const cleanTargetUrl = stripTranslateOnlyParams(
        buildUrlWithLanguage(targetLanguage),
    );

    window.history.replaceState({}, document.title, cleanTargetUrl.toString());
    document.open();
    document.write(html);
    document.close();
}

function preserveScoreResultScroll() {
    if (!document.querySelector('[data-score-status-card]')) {
        return;
    }

    try {
        sessionStorage.setItem(SCORE_RESULT_SCROLL_STORAGE_KEY, 'true');
    } catch (_) {
        // no-op
    }
}

function scheduleLanguagePrefetch(targetLanguage) {
    const startPrefetch = () => {
        fetchLanguagePageHtml(targetLanguage).catch(() => {});
    };

    if (typeof window.requestIdleCallback === 'function') {
        window.requestIdleCallback(startPrefetch, { timeout: 1500 });
        return;
    }

    window.setTimeout(startPrefetch, 250);
}

function applySavedLanguagePreference() {
    const savedLanguage = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    const currentUrl = new URL(window.location.href);
    const urlLanguage = currentUrl.searchParams.get('lang');

    if (!savedLanguage || savedLanguage === getCurrentLanguage() || urlLanguage) {
        return;
    }

    window.location.replace(buildUrlWithLanguage(savedLanguage).toString());
}

function bindLanguageSwitchButtons() {
    languageSwitchButtons.forEach((button) => {
        const targetLanguage = button.dataset.langSwitch;

        if (targetLanguage && targetLanguage !== getCurrentLanguage()) {
            scheduleLanguagePrefetch(targetLanguage);
        }

        button.addEventListener('click', async () => {
            const targetLanguage = button.dataset.langSwitch;

            if (!targetLanguage || targetLanguage === getCurrentLanguage()) {
                return;
            }

            localStorage.setItem(LANGUAGE_STORAGE_KEY, targetLanguage);

            try {
                preserveScoreResultScroll();
                const html = await fetchLanguagePageHtml(targetLanguage);
                replaceDocumentWithLanguageHtml(html, targetLanguage);
            } catch (_) {
                window.location.assign(
                    stripTranslateOnlyParams(
                        buildUrlWithLanguage(targetLanguage),
                    ).toString(),
                );
            }
        });
    });
}

export {
    applySavedLanguagePreference,
    bindLanguageSwitchButtons,
    buildUrlWithLanguage,
};
