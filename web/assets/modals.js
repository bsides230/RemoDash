window.CustomModals = {
    show: function(options) {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.style.cssText = `
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0, 0, 0, 0.5); display: flex;
                align-items: center; justify-content: center;
                z-index: 10000; font-family: var(--font-family, sans-serif);
                backdrop-filter: blur(4px);
            `;

            const dialog = document.createElement('div');
            dialog.style.cssText = `
                background: var(--bg-core, #1e1e1e);
                color: var(--text-color, #ffffff);
                padding: 20px; border-radius: 8px;
                min-width: 300px; max-width: 80%;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
                border: 1px solid var(--border-color, #333);
                display: flex; flex-direction: column; gap: 15px;
            `;

            const title = document.createElement('div');
            title.style.fontWeight = 'bold';
            title.style.fontSize = '1.1em';
            title.textContent = options.title || (options.type === 'alert' ? 'Alert' : options.type === 'confirm' ? 'Confirm' : 'Input Required');

            const message = document.createElement('div');
            message.textContent = options.message || '';
            message.style.whiteSpace = 'pre-wrap';

            let input;
            if (options.type === 'prompt') {
                input = document.createElement('input');
                input.type = 'text';
                input.value = options.defaultValue || '';
                input.style.cssText = `
                    width: 100%; padding: 8px; background: var(--bg-surface, #2c2c2c);
                    border: 1px solid var(--border-color, #444); color: inherit;
                    border-radius: 4px; box-sizing: border-box; font-family: inherit;
                `;
            }

            const buttons = document.createElement('div');
            buttons.style.cssText = `display: flex; justify-content: flex-end; gap: 10px; margin-top: 5px;`;

            const createBtn = (text, isPrimary, onClick) => {
                const btn = document.createElement('button');
                btn.textContent = text;
                btn.style.cssText = `
                    padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer;
                    background: ${isPrimary ? 'var(--brand-color, #1ea096)' : 'var(--bg-surface, #333)'};
                    color: white; font-weight: bold; transition: opacity 0.2s;
                    font-family: inherit; border: 1px solid var(--border-color, #444);
                `;
                btn.onmouseover = () => btn.style.opacity = '0.8';
                btn.onmouseout = () => btn.style.opacity = '1';
                btn.onclick = () => {
                    document.body.removeChild(overlay);
                    onClick();
                };
                return btn;
            };

            if (options.type === 'alert') {
                buttons.appendChild(createBtn('OK', true, () => resolve(true)));
            } else if (options.type === 'confirm') {
                buttons.appendChild(createBtn('Cancel', false, () => resolve(false)));
                buttons.appendChild(createBtn('OK', true, () => resolve(true)));
            } else if (options.type === 'prompt') {
                buttons.appendChild(createBtn('Cancel', false, () => resolve(null)));
                buttons.appendChild(createBtn('OK', true, () => resolve(input.value)));
                input.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        document.body.removeChild(overlay);
                        resolve(input.value);
                    }
                });
            }

            dialog.appendChild(title);
            if (options.message) dialog.appendChild(message);
            if (input) dialog.appendChild(input);
            dialog.appendChild(buttons);
            overlay.appendChild(dialog);
            document.body.appendChild(overlay);

            if (input) {
                input.focus();
                input.setSelectionRange(0, input.value.length);
            } else {
                // Focus OK button
                const okBtn = buttons.children[buttons.children.length - 1];
                if (okBtn) okBtn.focus();
            }
        });
    },
    alert: function(message, title='Alert') {
        return this.show({ type: 'alert', message, title });
    },
    confirm: function(message, title='Confirm') {
        return this.show({ type: 'confirm', message, title });
    },
    prompt: function(message, defaultValue='', title='Input Required') {
        return this.show({ type: 'prompt', message, defaultValue, title });
    }
};
