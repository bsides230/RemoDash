class ModuleSDK {
    constructor(moduleId) {
        this.moduleId = moduleId;
        this.coreUrl = window.location.origin; // Default, usually updated via postMessage
        this.authToken = null;

        // Listen for standard messages from Dashboard
        window.addEventListener('message', (e) => {
            if (e.data.type === 'CORE_URL_CHANGE') {
                this.coreUrl = e.data.url;
            }
            if (e.data.type === 'TOKEN_UPDATE') {
                this.authToken = e.data.token;
            }
        });
    }

    async checkRequirements() {
        if (!this.moduleId) return { missing: [] };

        try {
            const res = await fetch(`${this.coreUrl}/api/modules/${this.moduleId}/check_requirements`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Token': this.authToken
                }
            });
            if (!res.ok) {
                console.warn("Failed to check requirements:", await res.text());
                return { missing: [] };
            }
            return await res.json();
        } catch (e) {
            console.error("Error checking requirements:", e);
            return { missing: [] };
        }
    }

    showInstallModal(missingPackages) {
        if (!missingPackages || missingPackages.length === 0) return;

        // Check if modal already exists
        if (document.getElementById('sdk-install-modal')) return;

        const modal = document.createElement('div');
        modal.id = 'sdk-install-modal';
        modal.style.position = 'fixed';
        modal.style.top = '0';
        modal.style.left = '0';
        modal.style.width = '100%';
        modal.style.height = '100%';
        modal.style.background = 'rgba(0,0,0,0.8)';
        modal.style.display = 'flex';
        modal.style.alignItems = 'center';
        modal.style.justifyContent = 'center';
        modal.style.zIndex = '10000';
        modal.style.fontFamily = 'monospace';

        const box = document.createElement('div');
        box.style.background = '#1a1a1a';
        box.style.border = '1px solid #444';
        box.style.borderRadius = '8px';
        box.style.padding = '20px';
        box.style.width = '400px';
        box.style.maxWidth = '90%';
        box.style.color = '#fff';

        const title = document.createElement('h3');
        title.innerText = 'Missing Dependencies';
        title.style.marginTop = '0';
        title.style.color = '#ff4444';
        box.appendChild(title);

        const p = document.createElement('p');
        p.innerText = 'This module requires the following packages to function correctly:';
        p.style.fontSize = '12px';
        p.style.color = '#ccc';
        box.appendChild(p);

        const list = document.createElement('ul');
        list.style.background = '#000';
        list.style.padding = '10px 20px';
        list.style.borderRadius = '4px';
        list.style.maxHeight = '150px';
        list.style.overflowY = 'auto';
        missingPackages.forEach(pkg => {
            const li = document.createElement('li');
            li.innerText = pkg;
            li.style.color = '#ffaa00';
            list.appendChild(li);
        });
        box.appendChild(list);

        const actions = document.createElement('div');
        actions.style.display = 'flex';
        actions.style.gap = '10px';
        actions.style.marginTop = '20px';

        const btnCancel = document.createElement('button');
        btnCancel.innerText = 'Close';
        btnCancel.style.padding = '8px 12px';
        btnCancel.style.background = 'transparent';
        btnCancel.style.border = '1px solid #444';
        btnCancel.style.color = '#ccc';
        btnCancel.style.cursor = 'pointer';
        btnCancel.onclick = () => modal.remove();
        actions.appendChild(btnCancel);

        const btnInstall = document.createElement('button');
        btnInstall.innerText = 'Install via Terminal';
        btnInstall.style.flex = '1';
        btnInstall.style.padding = '8px 12px';
        btnInstall.style.background = '#10B981'; // Brand color approximation
        btnInstall.style.border = 'none';
        btnInstall.style.color = '#fff';
        btnInstall.style.cursor = 'pointer';
        btnInstall.onclick = () => {
            this.installDependencies();
            modal.remove();
        };
        actions.appendChild(btnInstall);

        box.appendChild(actions);
        modal.appendChild(box);
        document.body.appendChild(modal);
    }

    installDependencies() {
        // Send message to Dashboard to open Terminal
        // Command: python3 -m pip install -r modules/{moduleId}/requirements.txt
        // We assume the module path is standard: modules/{moduleId}
        // If it's a core module migrated to modules/, it follows the same pattern.

        const cmd = `python3 -m pip install -r modules/${this.moduleId}/requirements.txt && echo "Done. Please restart the module or server."`;

        window.parent.postMessage({
            type: 'OPEN_TERMINAL_TAB',
            command: cmd,
            cwd: `modules/${this.moduleId}` // Run in module dir just in case
        }, '*');
    }
}

// Global instance helper
window.ModuleSDK = ModuleSDK;
