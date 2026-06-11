const transactionForm = document.getElementById('transaction-form');
const clearFormButton = document.getElementById('clear-form');
const demoButtons = document.querySelectorAll('[data-demo-key]');
const screenTabs = document.querySelectorAll('[data-screen-target]');
const screens = document.querySelectorAll('[data-screen-name]');
const demoPayloadsElement = document.getElementById('demo-payloads-json');

const demoPayloads = demoPayloadsElement
    ? JSON.parse(demoPayloadsElement.textContent)
    : [];

function activateScreen(screenName) {
    screenTabs.forEach((tab) => {
        const isActive = tab.dataset.screenTarget === screenName;
        tab.classList.toggle('is-active', isActive);
        tab.setAttribute('aria-pressed', String(isActive));
    });

    screens.forEach((screen) => {
        screen.hidden = screen.dataset.screenName !== screenName;
    });
}

screenTabs.forEach((tab) => {
    tab.addEventListener('click', () => {
        activateScreen(tab.dataset.screenTarget);
    });
});

activateScreen('score');

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

        Object.entries(payload).forEach(([fieldName, fieldValue]) => {
            const input = transactionForm.elements.namedItem(fieldName);

            if (!(input instanceof HTMLInputElement)) {
                return;
            }

            input.value = fieldValue ?? '';
        });
    });
});

if (clearFormButton && transactionForm) {
    clearFormButton.addEventListener('click', () => {
        Array.from(transactionForm.elements).forEach((element) => {
            if (!(element instanceof HTMLInputElement)) {
                return;
            }

            element.value = '';
        });
    });
}
