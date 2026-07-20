import {
    closeScenarioModalButton,
    scenarioModal,
} from './dom-state.js';

function showScenarioModal() {
    if (!(scenarioModal instanceof HTMLDivElement)) {
        return;
    }

    scenarioModal.hidden = false;
}

function hideScenarioModal() {
    if (!(scenarioModal instanceof HTMLDivElement)) {
        return;
    }

    scenarioModal.hidden = true;
}

function bindScenarioModal() {
    if (closeScenarioModalButton) {
        closeScenarioModalButton.addEventListener('click', () => {
            hideScenarioModal();
        });
    }

    if (scenarioModal instanceof HTMLDivElement) {
        scenarioModal.addEventListener('click', (event) => {
            if (event.target === scenarioModal) {
                hideScenarioModal();
            }
        });
    }
}

export { bindScenarioModal, hideScenarioModal, showScenarioModal };
