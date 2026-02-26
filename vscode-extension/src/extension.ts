import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
    let terminal: vscode.Terminal | undefined;

    // Helper to get or create a dedicated terminal for vdx
    function getTerminal() {
        if (!terminal || terminal.exitStatus !== undefined) {
            terminal = vscode.window.createTerminal('VDX CLI');
        }
        return terminal;
    }

    function runVdxCommand(command: string) {
        const t = getTerminal();
        t.show();
        t.sendText(`vdx ${command}`);
    }

    // Register all commands
    context.subscriptions.push(
        vscode.commands.registerCommand('vdx.login', () => runVdxCommand('login')),

        vscode.commands.registerCommand('vdx.pull', async () => {
            const includeTranslations = await vscode.window.showQuickPick(['No', 'Yes'], {
                placeHolder: 'Include translations in pull?'
            });
            if (includeTranslations === undefined) return; // User cancelled
            const command = includeTranslations === 'Yes' ? 'pull --translations' : 'pull';
            runVdxCommand(command);
        }),

        vscode.commands.registerCommand('vdx.push', async () => {
            const includeTranslations = await vscode.window.showQuickPick(['No', 'Yes'], {
                placeHolder: 'Include translations in push?'
            });
            if (includeTranslations === undefined) return; // User cancelled
            const command = includeTranslations === 'Yes' ? 'push --translations' : 'push';
            runVdxCommand(command);
        }),

        vscode.commands.registerCommand('vdx.pushDryRun', async () => {
            const includeTranslations = await vscode.window.showQuickPick(['No', 'Yes'], {
                placeHolder: 'Include translations in push (dry-run)?'
            });
            if (includeTranslations === undefined) return; // User cancelled
            const command = includeTranslations === 'Yes' ? 'push --dry-run --translations' : 'push --dry-run';
            runVdxCommand(command);
        }),

        vscode.commands.registerCommand('vdx.package', () => runVdxCommand('package')),

        vscode.commands.registerCommand('vdx.clean', () => runVdxCommand('clean'))
    );
}

export function deactivate() {}
