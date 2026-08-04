import { LANGUAGE_STORAGE_KEY, getCurrentLanguage, getLanguageSwitchButtons } from './dom-state.js';
import { bootstrapUi } from './index.js';
import { buildUrlWithLanguage } from './url-state.js';

const TRANSLATE_ONLY_QUERY_PARAM = 'ui_translate';
const LANGUAGE_PAGE_CACHE_PREFIX = 'anti-fraud-language-page:';
const inFlightLanguageFetches = new Map();

// #region debug-point language-switch-report
function reportLanguageSwitchDebug(event, payload = {}) {
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
// #endregion debug-point language-switch-report

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
    // #region debug-point language-switch-fetch
    const requestStartedAt = performance.now();
    // #endregion debug-point language-switch-fetch
    const cachedHtml = getCachedLanguagePage(targetLanguage, baseUrl);
    if (cachedHtml) {
        // #region debug-point language-switch-fetch
        reportLanguageSwitchDebug('language_switch_fetch_html', {
            targetLanguage,
            baseUrl,
            cacheHit: true,
            durationMs: Number((performance.now() - requestStartedAt).toFixed(2)),
            htmlLength: cachedHtml.length,
        });
        // #endregion debug-point language-switch-fetch
        return cachedHtml;
    }

    const requestUrl = buildTranslateOnlyUrl(targetLanguage, baseUrl).toString();
    const existingRequest = inFlightLanguageFetches.get(requestUrl);
    if (existingRequest) {
        // #region debug-point language-switch-fetch
        reportLanguageSwitchDebug('language_switch_fetch_html', {
            targetLanguage,
            baseUrl,
            requestUrl,
            cacheHit: false,
            reusedInFlightRequest: true,
            durationMs: Number((performance.now() - requestStartedAt).toFixed(2)),
        });
        // #endregion debug-point language-switch-fetch
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
            // #region debug-point language-switch-fetch
            reportLanguageSwitchDebug('language_switch_fetch_html', {
                targetLanguage,
                baseUrl,
                requestUrl,
                cacheHit: false,
                reusedInFlightRequest: false,
                durationMs: Number((performance.now() - requestStartedAt).toFixed(2)),
                htmlLength: html.length,
            });
            // #endregion debug-point language-switch-fetch
            return html;
        })
        .catch((error) => {
            // #region debug-point language-switch-fetch
            reportLanguageSwitchDebug('language_switch_fetch_error', {
                targetLanguage,
                baseUrl,
                requestUrl,
                durationMs: Number((performance.now() - requestStartedAt).toFixed(2)),
                message: error instanceof Error ? error.message : String(error),
            });
            // #endregion debug-point language-switch-fetch
            throw error;
        })
        .finally(() => {
            inFlightLanguageFetches.delete(requestUrl);
        });

    inFlightLanguageFetches.set(requestUrl, requestPromise);
    return requestPromise;
}

function replaceDocumentWithLanguageHtml(html, targetLanguage) {
    const parsedDocument = new DOMParser().parseFromString(html, 'text/html');
    const cleanTargetUrl = stripTranslateOnlyParams(
        buildUrlWithLanguage(targetLanguage),
    );

    document.documentElement.lang = parsedDocument.documentElement.lang || targetLanguage;
    document.title = parsedDocument.title;
    document.body.replaceWith(parsedDocument.body);
    window.history.replaceState({}, document.title, cleanTargetUrl.toString());
    bootstrapUi();
}

function preserveViewportPosition() {
    const activeElementId =
        document.activeElement instanceof HTMLElement && document.activeElement.id
            ? document.activeElement.id
            : null;

    return {
        scrollX: window.scrollX,
        scrollY: window.scrollY,
        activeElementId,
    };
}

function restoreViewportPosition(viewportState) {
    window.requestAnimationFrame(() => {
        window.scrollTo({ left: viewportState.scrollX, top: viewportState.scrollY });

        if (!viewportState.activeElementId) {
            return;
        }

        const nextActiveElement = document.getElementById(viewportState.activeElementId);
        if (nextActiveElement instanceof HTMLElement) {
            nextActiveElement.focus({ preventScroll: true });
        }
    });
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
    getLanguageSwitchButtons().forEach((button) => {
        const targetLanguage = button.dataset.langSwitch;

        if (targetLanguage && targetLanguage !== getCurrentLanguage()) {
            scheduleLanguagePrefetch(targetLanguage);
        }

        if (button.dataset.langSwitchBound === 'true') {
            return;
        }

        button.dataset.langSwitchBound = 'true';
        button.addEventListener('click', async () => {
            const targetLanguage = button.dataset.langSwitch;
            // #region debug-point language-switch-click
            const clickStartedAt = performance.now();
            // #endregion debug-point language-switch-click

            if (!targetLanguage || targetLanguage === getCurrentLanguage()) {
                return;
            }

            localStorage.setItem(LANGUAGE_STORAGE_KEY, targetLanguage);
            // #region debug-point language-switch-click
            reportLanguageSwitchDebug('language_switch_click', {
                targetLanguage,
                currentLanguage: getCurrentLanguage(),
                hasScoreStatusCard: Boolean(
                    document.querySelector('[data-score-status-card]'),
                ),
            });
            // #endregion debug-point language-switch-click

            try {
                const viewportState = preserveViewportPosition();
                const html = await fetchLanguagePageHtml(targetLanguage);
                // #region debug-point language-switch-click
                reportLanguageSwitchDebug('language_switch_before_replace', {
                    targetLanguage,
                    totalDurationMs: Number(
                        (performance.now() - clickStartedAt).toFixed(2),
                    ),
                    htmlLength: html.length,
                });
                // #endregion debug-point language-switch-click
                replaceDocumentWithLanguageHtml(html, targetLanguage);
                restoreViewportPosition(viewportState);
            } catch (_) {
                // #region debug-point language-switch-click
                reportLanguageSwitchDebug('language_switch_fallback_navigation', {
                    targetLanguage,
                    totalDurationMs: Number(
                        (performance.now() - clickStartedAt).toFixed(2),
                    ),
                });
                // #endregion debug-point language-switch-click
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
