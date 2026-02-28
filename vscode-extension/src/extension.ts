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

            exec(`"${vdxPath}" patch --json`, { cwd: workspaceRoot }, async (error, stdout, stderr) => {
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

                    // Group changes by component type
                    const groups = new Map<string, any[]>();
                    changes.forEach(change => {
                        const pathParts = change.file_path.split(path.sep);
                        const componentsIndex = pathParts.indexOf('components');
                        if (componentsIndex > -1 && pathParts.length > componentsIndex + 1) {
                            const componentType = pathParts[componentsIndex + 1];
                            if (!groups.has(componentType)) {
                                groups.set(componentType, []);
                            }
                            groups.get(componentType)!.push(change);
                        }
                    });

                    const componentTypes = Array.from(groups.keys());
                    let selectedChanges = [];

                    if (componentTypes.length > 1) {
                        // More than one type, so show type picker first
                        const typePickItems = componentTypes.map(type => ({
                            label: type,
                            description: `${groups.get(type)!.length} changed component(s)`
                        }));

                        const selectedType = await vscode.window.showQuickPick(typePickItems, {
                            placeHolder: "Select a component type to view changes"
                        });

                        if (!selectedType) { // User cancelled the type picker
                            // Still need to clean up temp files
                            const tempFiles = changes.map(c => c.original_file);
                            setTimeout(() => {
                                tempFiles.forEach(filePath => fs.unlink(filePath, () => {}));
                            }, 1000);
                            return;
                        }
                        selectedChanges = groups.get(selectedType.label)!;

                    } else if (componentTypes.length === 1) {
                        // Only one type, bypass type picker
                        selectedChanges = groups.get(componentTypes[0])!;
                    } else {
                        // No component files found, but other files might have changed which we don't handle here
                        vscode.window.showInformationMessage("No recognized component changes detected.");
                        return;
                    }

                    // Show file picker for the selected (or only) type
                    const filePickItems = selectedChanges.map(change => ({
                        label: path.basename(change.file_path),
                        description: change.file_path,
                        change: change
                    }));

                    const selectedFileItem = await vscode.window.showQuickPick(filePickItems, {
                        placeHolder: "Select a file to view the diff"
                    });

                    // Cleanup all temp files created by the patch command
                    const tempFiles = changes.map(c => c.original_file);
                    setTimeout(() => {
                        tempFiles.forEach(filePath => {
                            fs.unlink(filePath, (err) => {
                                if (err) console.error(`Failed to delete temp file: ${filePath}`, err);
                            });
                        });
                    }, 5000);

                    if (selectedFileItem) {
                        const change = selectedFileItem.change;
                        const originalUri = vscode.Uri.file(change.original_file);
                        const modifiedUri = vscode.Uri.file(change.modified_file);
                        const filename = path.basename(change.file_path);
                        
                        vscode.commands.executeCommand('vscode.diff', originalUri, modifiedUri, `${filename} (Original <-> Local)`);
                    }

                } catch (e) {
                    vscode.window.showErrorMessage(`Failed to parse changes from vdx command: ${e}`);
                }
            });
        })
    );
}

export function deactivate() {}
