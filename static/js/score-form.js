import {
    SCORE_RESULT_SCROLL_STORAGE_KEY,
    clearFormButton,
    demoButtons,
    demoPayloads,
    getCurrentLanguage,
    getSelectedDemoKey,
    scoreLoadingOverlay,
    setSelectedDemoKey,
    submitButton,
    transactionForm,
    uiTexts,
} from './dom-state.js';
import { activateScreen } from './app-shell.js';
import { buildUrlWithLanguage } from './language-switch.js';
import { hideScenarioModal, showScenarioModal } from './modals.js';

const SCORE_PLACEHOLDER_HTML = `
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

function showScoreLoadingOverlay() {
    if (!(scoreLoadingOverlay instanceof HTMLDivElement)) {
        return;
    }

    scoreLoadingOverlay.hidden = false;
    document.body.classList.add('is-loading-score');
}

function hideScoreLoadingOverlay() {
    if (!(scoreLoadingOverlay instanceof HTMLDivElement)) {
        return;
    }

    scoreLoadingOverlay.hidden = true;
    document.body.classList.remove('is-loading-score');
}

function scrollToLatestScoreResult() {
    const scoreStatusCard = document.querySelector('[data-score-status-card]');
    const scoreResults = document.querySelector('[data-score-results]');
    const target = scoreStatusCard ?? scoreResults;

    if (!(target instanceof HTMLElement)) {
        return;
    }

    window.requestAnimationFrame(() => {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        if (scoreStatusCard instanceof HTMLElement) {
            scoreStatusCard.focus({ preventScroll: true });
        }
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
        scoreScreen.insertAdjacentHTML('beforeend', SCORE_PLACEHOLDER_HTML);
    }
}

function updateSelectedDemoButton(nextDemoKey) {
    setSelectedDemoKey(nextDemoKey);

    demoButtons.forEach((button) => {
        const isActive = button.dataset.demoKey === nextDemoKey;
        button.classList.toggle('is-selected', isActive);
        button.setAttribute('aria-pressed', String(isActive));
    });
}

function bindDemoButtons() {
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
}

function bindTransactionForm() {
    if (!transactionForm) {
        return;
    }

    transactionForm.addEventListener('submit', (event) => {
        if (getSelectedDemoKey()) {
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
    if (!clearFormButton || !transactionForm) {
        return;
    }

    clearFormButton.addEventListener('click', () => {
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
