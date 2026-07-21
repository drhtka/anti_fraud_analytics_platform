import {
    getCloseScenarioModalButton,
    getScenarioModal,
} from './dom-state.js';

function showScenarioModal() {
    const scenarioModal = getScenarioModal();
    if (!(scenarioModal instanceof HTMLDivElement)) {
        return;
    }

    scenarioModal.hidden = false;
}

function hideScenarioModal() {
    const scenarioModal = getScenarioModal();
    if (!(scenarioModal instanceof HTMLDivElement)) {
        return;
    }

    scenarioModal.hidden = true;
}

function bindScenarioModal() {
    const closeScenarioModalButton = getCloseScenarioModalButton();
    const scenarioModal = getScenarioModal();

    if (closeScenarioModalButton) {
        if (closeScenarioModalButton.dataset.modalBound !== 'true') {
            closeScenarioModalButton.dataset.modalBound = 'true';
            closeScenarioModalButton.addEventListener('click', () => {
                hideScenarioModal();
            });
        }
    }

    if (scenarioModal instanceof HTMLDivElement) {
        if (scenarioModal.dataset.modalBackdropBound === 'true') {
            return;
        }

        scenarioModal.dataset.modalBackdropBound = 'true';
        scenarioModal.addEventListener('click', (event) => {
            if (event.target === scenarioModal) {
                hideScenarioModal();
            }
        });
    }
}

export { bindScenarioModal, hideScenarioModal, showScenarioModal };
