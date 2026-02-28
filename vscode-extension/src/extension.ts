import * as vscode from 'vscode';
import { exec } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

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

        vscode.commands.registerCommand('vdx.clean', () => runVdxCommand('clean')),

        vscode.commands.registerCommand('vdx.showChangesInUI', () => {
            const workspaceFolders = vscode.workspace.workspaceFolders;
            if (!workspaceFolders) {
                vscode.window.showErrorMessage("No workspace folder open.");
                return;
            }
            const workspaceRoot = workspaceFolders[0].uri.fsPath;

            exec('vdx patch --json', { cwd: workspaceRoot }, (error, stdout, stderr) => {
                if (error) {
                    vscode.window.showErrorMessage(`Error executing vdx patch: ${stderr}`);
                    return;
                }

                try {
                    const changes = JSON.parse(stdout);
                    if (!Array.isArray(changes) || changes.length === 0) {
                        vscode.window.showInformationMessage("No local changes detected.");
                        return;
                    }

                    const tempFiles: string[] = [];

                    changes.forEach(change => {
                        const originalUri = vscode.Uri.file(change.original_file);
                        const modifiedUri = vscode.Uri.file(change.modified_file);
                        tempFiles.push(change.original_file);

                        const filename = path.basename(change.file_path);
                        vscode.commands.executeCommand('vscode.diff', originalUri, modifiedUri, `${filename} (Original <-> Local)`);
                    });

                    // Cleanup temp files after a short delay to ensure they are no longer needed by VS Code
                    setTimeout(() => {
                        tempFiles.forEach(filePath => {
                            fs.unlink(filePath, (err) => {
                                if (err) {
                                    console.error(`Failed to delete temp file: ${filePath}`, err);
                                }
                            });
                        });
                    }, 5000);

                } catch (e) {
                    vscode.window.showErrorMessage(`Failed to parse changes: ${e}`);
                }
            });
        })
    );
}

export function deactivate() {}
