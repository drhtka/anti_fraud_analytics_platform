import {
    LANGUAGE_STORAGE_KEY,
    getCurrentLanguage,
    languageSwitchButtons,
} from './dom-state.js';

function buildUrlWithLanguage(targetLanguage, baseUrl = window.location.href) {
    const nextUrl = new URL(baseUrl, window.location.origin);
    nextUrl.searchParams.set('lang', targetLanguage);
    return nextUrl;
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
        button.addEventListener('click', () => {
            const targetLanguage = button.dataset.langSwitch;

            if (!targetLanguage || targetLanguage === getCurrentLanguage()) {
                return;
            }

            localStorage.setItem(LANGUAGE_STORAGE_KEY, targetLanguage);
            window.location.assign(
                buildUrlWithLanguage(targetLanguage).toString(),
            );
        });
    });
}

export {
    applySavedLanguagePreference,
    bindLanguageSwitchButtons,
    buildUrlWithLanguage,
};
