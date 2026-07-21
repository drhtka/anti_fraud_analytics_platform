const DEFAULT_SCREEN = 'score';
const ACTIVE_SCREEN_STORAGE_KEY = 'anti-fraud-active-screen';
const SCORE_RESULT_SCROLL_STORAGE_KEY = 'anti-fraud-scroll-to-score-results';
const LANGUAGE_STORAGE_KEY = 'anti-fraud-language';

const inFlightScreenLoads = new Map();
const state = {
    selectedDemoKey: '',
};

function getScreens() {
    return Array.from(document.querySelectorAll('[data-screen-name]'));
}

function getTransactionForm() {
    const transactionForm = document.getElementById('transaction-form');
    return transactionForm instanceof HTMLFormElement ? transactionForm : null;
}

function getClearFormButton() {
    const clearFormButton = document.getElementById('clear-form');
    return clearFormButton instanceof HTMLButtonElement ? clearFormButton : null;
}

function getScoreLoadingOverlay() {
    const scoreLoadingOverlay = document.getElementById('score-loading-overlay');
    return scoreLoadingOverlay instanceof HTMLDivElement
        ? scoreLoadingOverlay
        : null;
}

function getSubmitButton() {
    const submitButton = getTransactionForm()?.querySelector('.submit-button');
    return submitButton instanceof HTMLButtonElement ? submitButton : null;
}

function getDemoButtons() {
    return Array.from(document.querySelectorAll('[data-demo-key]'));
}

function getScreenTabs() {
    return Array.from(document.querySelectorAll('[data-screen-target]'));
}

function getDemoPayloads() {
    const demoPayloadsElement = document.getElementById('demo-payloads-json');
    if (!demoPayloadsElement?.textContent) {
        return [];
    }

    try {
        return JSON.parse(demoPayloadsElement.textContent);
    } catch (_) {
        return [];
    }
}

function getUiTexts() {
    const frontendI18nElement = document.getElementById('frontend-i18n-json');
    if (!frontendI18nElement?.textContent) {
        return {};
    }

    try {
        return JSON.parse(frontendI18nElement.textContent);
    } catch (_) {
        return {};
    }
}

function getScenarioModal() {
    const scenarioModal = document.getElementById('scenario-modal');
    return scenarioModal instanceof HTMLDivElement ? scenarioModal : null;
}

function getCloseScenarioModalButton() {
    const closeScenarioModalButton = document.getElementById(
        'close-scenario-modal',
    );
    return closeScenarioModalButton instanceof HTMLButtonElement
        ? closeScenarioModalButton
        : null;
}

function getLanguageSwitchButtons() {
    return Array.from(document.querySelectorAll('[data-lang-switch]'));
}

function getAvailableScreens() {
    return new Set(getScreenTabs().map((tab) => tab.dataset.screenTarget));
}

function getCurrentLanguage() {
    return document.documentElement.lang === 'en' ? 'en' : 'uk';
}

function setSelectedDemoKey(nextDemoKey) {
    state.selectedDemoKey = nextDemoKey;
}

function getSelectedDemoKey() {
    return state.selectedDemoKey;
}

export {
    ACTIVE_SCREEN_STORAGE_KEY,
    DEFAULT_SCREEN,
    LANGUAGE_STORAGE_KEY,
    SCORE_RESULT_SCROLL_STORAGE_KEY,
    getAvailableScreens,
    getClearFormButton,
    getCloseScenarioModalButton,
    getCurrentLanguage,
    getDemoButtons,
    getDemoPayloads,
    getLanguageSwitchButtons,
    getScreens,
    getScenarioModal,
    getSelectedDemoKey,
    getScoreLoadingOverlay,
    getScreenTabs,
    getSubmitButton,
    getTransactionForm,
    getUiTexts,
    inFlightScreenLoads,
    setSelectedDemoKey,
    state,
};
