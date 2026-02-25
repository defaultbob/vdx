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
        vscode.commands.registerCommand('vdx.pull', () => runVdxCommand('pull')),
        vscode.commands.registerCommand('vdx.push', () => runVdxCommand('push')),
        vscode.commands.registerCommand('vdx.pushDryRun', () => runVdxCommand('push --dry-run')),
        vscode.commands.registerCommand('vdx.package', () => runVdxCommand('package'))
    );
}

export function deactivate() {}
