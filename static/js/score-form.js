import {
    SCORE_RESULT_SCROLL_STORAGE_KEY,
    getCurrentLanguage,
    getClearFormButton,
    getDemoButtons,
    getDemoPayloads,
    getSelectedDemoKey,
    getScoreLoadingOverlay,
    getSubmitButton,
    getTransactionForm,
    getUiTexts,
    setSelectedDemoKey,
} from './dom-state.js';
import { activateScreen } from './app-shell.js';
import { buildUrlWithLanguage } from './url-state.js';
import { hideScenarioModal, showScenarioModal } from './modals.js';

function buildScorePlaceholderHtml() {
    const uiTexts = getUiTexts();
    return `
        <section class="placeholder">
            <h2>${uiTexts.scorePlaceholderTitle ?? 'Готово до демонстрації скорингу'}</h2>
            <p>${uiTexts.scorePlaceholderIntro ?? 'Обери один із трьох демо-сценаріїв і натисни кнопку "Виконати скоринг".'}</p>
            <p>${uiTexts.scorePlaceholderAfter ?? "Після запуску на цій сторінці з'являться:"}</p>
            <ul>
                ${(uiTexts.scorePlaceholderBullets ?? [])
                    .map((item) => `<li>${item}</li>`)
                    .join('')}
            </ul>
        </section>
    `;
}

function showScoreLoadingOverlay() {
    const scoreLoadingOverlay = getScoreLoadingOverlay();
    if (!(scoreLoadingOverlay instanceof HTMLDivElement)) {
        return;
    }

    scoreLoadingOverlay.hidden = false;
    document.body.classList.add('is-loading-score');
}

function hideScoreLoadingOverlay() {
    const scoreLoadingOverlay = getScoreLoadingOverlay();
    if (!(scoreLoadingOverlay instanceof HTMLDivElement)) {
        return;
    }

    scoreLoadingOverlay.hidden = true;
    document.body.classList.remove('is-loading-score');
}

function scrollToLatestScoreResult() {
    const scoreResults = document.querySelector('[data-score-results]');
    const scoreStatusCard = document.querySelector('[data-score-status-card]');

    if (!(scoreResults instanceof HTMLElement)) {
        return;
    }

    const focusTarget =
        scoreResults.querySelector('.decision-summary-card h2') ?? scoreResults;

    window.requestAnimationFrame(() => {
        scoreResults.scrollIntoView({ behavior: 'smooth', block: 'start' });

        window.setTimeout(() => {
            scoreResults.scrollIntoView({ behavior: 'smooth', block: 'start' });
            if (focusTarget instanceof HTMLElement) {
                focusTarget.focus({ preventScroll: true });
            } else if (scoreStatusCard instanceof HTMLElement) {
                scoreStatusCard.blur();
            }
        }, 250);
    });
}

function resetScoreScreenView() {
    const scoreScreen = document.querySelector('[data-screen-name="score"]');

    if (!(scoreScreen instanceof HTMLElement)) {
        return;
    }

    scoreScreen.querySelector('.message.error')?.remove();
    scoreScreen.querySelector('.results')?.remove();
    scoreScreen.querySelector('.json-action-link')?.remove();

    if (!scoreScreen.querySelector('.placeholder')) {
        scoreScreen.insertAdjacentHTML('beforeend', buildScorePlaceholderHtml());
    }
}

function updateSelectedDemoButton(nextDemoKey) {
    setSelectedDemoKey(nextDemoKey);

    getDemoButtons().forEach((button) => {
        const isActive = button.dataset.demoKey === nextDemoKey;
        button.classList.toggle('is-selected', isActive);
        button.setAttribute('aria-pressed', String(isActive));
    });
}

function bindDemoButtons() {
    const transactionForm = getTransactionForm();

    getDemoButtons().forEach((button) => {
        if (button.dataset.demoBound === 'true') {
            return;
        }

        button.dataset.demoBound = 'true';
        button.addEventListener('click', () => {
            const payloadKey = button.dataset.demoKey;
            const payloadEntry = getDemoPayloads().find(
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
}

function bindTransactionForm() {
    const transactionForm = getTransactionForm();
    if (!transactionForm) {
        return;
    }

    if (transactionForm.dataset.submitBound === 'true') {
        return;
    }

    transactionForm.dataset.submitBound = 'true';
    transactionForm.addEventListener('submit', (event) => {
        if (getSelectedDemoKey()) {
            const submitButton = getSubmitButton();
            const uiTexts = getUiTexts();
            sessionStorage.setItem(SCORE_RESULT_SCROLL_STORAGE_KEY, 'true');
            showScoreLoadingOverlay();
            if (submitButton instanceof HTMLButtonElement) {
                submitButton.disabled = true;
                submitButton.textContent =
                    uiTexts.submitRunning ?? 'Виконуємо скоринг...';
            }
            return;
        }

        event.preventDefault();
        showScenarioModal();
    });
}

function bindClearForm() {
    const clearFormButton = getClearFormButton();
    const transactionForm = getTransactionForm();
    if (!clearFormButton || !transactionForm) {
        return;
    }

    if (clearFormButton.dataset.clearBound === 'true') {
        return;
    }

    clearFormButton.dataset.clearBound = 'true';
    clearFormButton.addEventListener('click', () => {
        const submitButton = getSubmitButton();
        const uiTexts = getUiTexts();
        const cleanUrl = `${window.location.pathname}${window.location.hash || ''}`;

        sessionStorage.removeItem(SCORE_RESULT_SCROLL_STORAGE_KEY);
        hideScoreLoadingOverlay();
        hideScenarioModal();
        updateSelectedDemoButton('');

        Array.from(transactionForm.elements).forEach((element) => {
            if (element instanceof HTMLInputElement) {
                element.value = '';
            }
        });

        if (submitButton instanceof HTMLButtonElement) {
            submitButton.disabled = false;
            submitButton.textContent =
                uiTexts.submitDefault ?? 'Виконати скоринг';
        }

        resetScoreScreenView();
        const cleanStateUrl = buildUrlWithLanguage(
            getCurrentLanguage(),
            `${window.location.origin}${cleanUrl}`,
        );
        window.history.replaceState({}, document.title, cleanStateUrl);
    });
}

function restoreScoreResultScroll() {
    if (sessionStorage.getItem(SCORE_RESULT_SCROLL_STORAGE_KEY) !== 'true') {
        return;
    }

    sessionStorage.removeItem(SCORE_RESULT_SCROLL_STORAGE_KEY);
    hideScoreLoadingOverlay();
    activateScreen('score').then(() => {
        scrollToLatestScoreResult();
    });
}

export {
    bindClearForm,
    bindDemoButtons,
    bindTransactionForm,
    hideScoreLoadingOverlay,
    restoreScoreResultScroll,
};
