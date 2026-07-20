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

export { initDashboardEmbeds };
