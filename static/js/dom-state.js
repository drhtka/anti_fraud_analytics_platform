const transactionForm = document.getElementById('transaction-form');
const clearFormButton = document.getElementById('clear-form');
const scoreLoadingOverlay = document.getElementById('score-loading-overlay');
const submitButton = transactionForm?.querySelector('.submit-button');
const demoButtons = Array.from(document.querySelectorAll('[data-demo-key]'));
const screenTabs = Array.from(document.querySelectorAll('[data-screen-target]'));
const demoPayloadsElement = document.getElementById('demo-payloads-json');
const frontendI18nElement = document.getElementById('frontend-i18n-json');
const scenarioModal = document.getElementById('scenario-modal');
const closeScenarioModalButton = document.getElementById('close-scenario-modal');
const languageSwitchButtons = Array.from(
    document.querySelectorAll('[data-lang-switch]'),
);

const demoPayloads = demoPayloadsElement
    ? JSON.parse(demoPayloadsElement.textContent)
    : [];
const uiTexts = frontendI18nElement
    ? JSON.parse(frontendI18nElement.textContent)
    : {};

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

function getAvailableScreens() {
    return new Set(screenTabs.map((tab) => tab.dataset.screenTarget));
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
    clearFormButton,
    closeScenarioModalButton,
    demoButtons,
    demoPayloads,
    getAvailableScreens,
    getCurrentLanguage,
    getScreens,
    getSelectedDemoKey,
    inFlightScreenLoads,
    languageSwitchButtons,
    scenarioModal,
    screenTabs,
    scoreLoadingOverlay,
    setSelectedDemoKey,
    state,
    submitButton,
    transactionForm,
    uiTexts,
};
