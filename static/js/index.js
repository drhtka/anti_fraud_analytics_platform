import {
    activateScreen,
    bindHashChange,
    bindInternalHashLinks,
    bindScreenTabs,
    getInitialScreenName,
} from './app-shell.js';
import { initDashboardEmbeds } from './dashboard-embed.js';
import {
    applySavedLanguagePreference,
    bindLanguageSwitchButtons,
} from './language-switch.js';
import { bindScenarioModal } from './modals.js';
import {
    bindClearForm,
    bindDemoButtons,
    bindTransactionForm,
    restoreScoreResultScroll,
} from './score-form.js';

applySavedLanguagePreference();

bindScreenTabs();
bindHashChange();
bindInternalHashLinks();
bindScenarioModal();
bindDemoButtons();
bindTransactionForm();
bindClearForm();
bindLanguageSwitchButtons();

activateScreen(getInitialScreenName());
initDashboardEmbeds();
restoreScoreResultScroll();
