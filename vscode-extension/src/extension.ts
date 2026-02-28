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

        vscode.commands.registerCommand('vdx.showChangesInUI', async () => {
            const config = vscode.workspace.getConfiguration('vdx');
            const projectPath = config.get<string>('projectPath');

            if (!projectPath) {
                const openSettings = 'Open Settings';
                const selection = await vscode.window.showErrorMessage(
                    'The path to your VDX project is not configured. Please set the "vdx.projectPath" setting.',
                    openSettings
                );
                if (selection === openSettings) {
                    vscode.commands.executeCommand('workbench.action.openSettings', 'vdx.projectPath');
                }
                return;
            }

            const workspaceFolders = vscode.workspace.workspaceFolders;
            if (!workspaceFolders) {
                vscode.window.showErrorMessage("No workspace folder open.");
                return;
            }
            const workspaceRoot = workspaceFolders[0].uri.fsPath;
            const vdxPath = path.join(projectPath, 'venv', 'bin', 'vdx');

            exec(`"${vdxPath}" patch --json`, { cwd: workspaceRoot }, (error, stdout, stderr) => {
                if (error) {
                    // Check for the specific "No such file or directory" error related to vdxPath
                    if (error.message.includes(vdxPath)) {
                         vscode.window.showErrorMessage(`Could not find the vdx executable at the configured path: ${vdxPath}. Please check your 'vdx.projectPath' setting and ensure the virtual environment exists.`);
                    } else {
                        vscode.window.showErrorMessage(`Error executing vdx patch: ${stderr || error.message}`);
                    }
                    return;
                }

                try {
                    const changes = JSON.parse(stdout);
                    if (!Array.isArray(changes) || changes.length === 0) {
                        vscode.window.showInformationMessage("No local changes detected in the VDX project.");
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

                    // Cleanup temp files after a short delay
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
                    vscode.window.showErrorMessage(`Failed to parse changes from vdx command: ${e}`);
                }
            });
        })
    );
}

export function deactivate() {}
