import * as vscode from 'vscode';
import { exec, spawn } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import * as util from 'util';

const execPromise = util.promisify(exec);

export async function activate(context: vscode.ExtensionContext) {
    const outputChannel = vscode.window.createOutputChannel('VDX CLI');

    // 1. Define paths for the isolated environment in the extension's global storage
    const storageUri = context.globalStorageUri;
    if (!fs.existsSync(storageUri.fsPath)) {
        fs.mkdirSync(storageUri.fsPath, { recursive: true });
    }
    
    const venvPath = path.join(storageUri.fsPath, 'venv');
    const isWin = process.platform === 'win32';
    const pythonCmd = isWin ? path.join(venvPath, 'Scripts', 'python.exe') : path.join(venvPath, 'bin', 'python');
    const pipCmd = isWin ? path.join(venvPath, 'Scripts', 'pip.exe') : path.join(venvPath, 'bin', 'pip');

    // Path to the CLI bundled inside the extension
    const vdxMainPath = context.asAbsolutePath(path.join('vdx_project', 'main.py'));

    // 2. Automatically initialize the virtual environment if missing
    if (!fs.existsSync(pythonCmd)) {
        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: "Initializing VDX Environment (First Run)...",
            cancellable: false
        }, async () => {
            try {
                // Determine system python
                const sysPython = isWin ? 'python' : 'python3';
                await execPromise(`${sysPython} -m venv "${venvPath}"`);
                
                // Install dependencies
                const reqPath = context.asAbsolutePath(path.join('vdx_project', 'requirements.txt'));
                if (fs.existsSync(reqPath)) {
                    await execPromise(`"${pipCmd}" install -r "${reqPath}"`);
                } else {
                    await execPromise(`"${pipCmd}" install requests`);
                }
                
                vscode.window.showInformationMessage("VDX CLI setup complete!");
            } catch (err) {
                vscode.window.showErrorMessage(`Failed to set up VDX environment: ${err}`);
            }
        });
    }

    function runVdxCommand(args: string[], title: string, interactive: boolean = false) {
        if (interactive) {
            // For login, we still use the terminal because it prompts for a password via getpass
            const terminal = vscode.window.createTerminal('VDX CLI');
            terminal.show(true);
            const commandStr = `"${pythonCmd}" "${vdxMainPath}" ${args.join(' ')}`;
            terminal.sendText(commandStr);
            return;
        }

        outputChannel.show(true);
        outputChannel.appendLine(`\n> vdx ${args.join(' ')}`);

        vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: `VDX: ${title}`,
            cancellable: true
        }, (progress, token) => {
            return new Promise<void>((resolve, reject) => {
                const workspaceFolders = vscode.workspace.workspaceFolders;
                const cwd = workspaceFolders ? workspaceFolders[0].uri.fsPath : process.cwd();

                const child = spawn(pythonCmd, [vdxMainPath, ...args], { cwd });

                token.onCancellationRequested(() => {
                    child.kill('SIGINT');
                    outputChannel.appendLine('Command cancelled by user.');
                    resolve();
                });

                child.stdout.on('data', (data) => {
                    outputChannel.append(data.toString());
                });

                child.stderr.on('data', (data) => {
                    outputChannel.append(data.toString());
                });

                child.on('close', (code) => {
                    outputChannel.appendLine(`Command exited with code ${code}`);
                    if (code === 0) {
                        vscode.window.showInformationMessage(`VDX: ${title} completed successfully.`);
                        resolve();
                    } else {
                        vscode.window.showErrorMessage(`VDX: ${title} failed. Check the output channel for details.`);
                        resolve(); // Resolve rather than reject so the progress notification closes gracefully
                    }
                });
            });
        });
    }

    // Register all commands
    context.subscriptions.push(
        vscode.commands.registerCommand('vdx.login', () => runVdxCommand(['login'], 'Login', true)),

        vscode.commands.registerCommand('vdx.pull', async () => {
            const workspaceFolders = vscode.workspace.workspaceFolders;
            if (!workspaceFolders) {
                vscode.window.showErrorMessage("No workspace folder open.");
                return;
            }
            const workspaceRoot = workspaceFolders[0].uri.fsPath;
            const stateFile = path.join(workspaceRoot, '.vdx_state.json');
            
            let pullMode = 'advanced';

            const modeSelection = await vscode.window.showQuickPick([
                { label: 'Advanced', description: 'Extract subcomponents and nested JSON/XML into folders (Recommended)' },
                { label: 'Simple', description: 'Standard MDL files without subcomponent extraction' }
            ], {
                placeHolder: 'Select Pull Structure Mode'
            });

            if (!modeSelection) return; // User cancelled
            pullMode = modeSelection.label.toLowerCase();

            const includeTranslations = await vscode.window.showQuickPick(['No', 'Yes'], {
                placeHolder: 'Include translations in pull? (Default: No)'
            });
            if (includeTranslations === undefined) return; // User cancelled

            const args = ['pull'];
            if (pullMode === 'simple') {
                args.push('--simple');
            }
            if (includeTranslations === 'Yes') {
                args.push('--translations');
            }
            
            runVdxCommand(args, 'Pull from Vault');
        }),

        vscode.commands.registerCommand('vdx.push', async () => {
            const includeTranslations = await vscode.window.showQuickPick(['No', 'Yes'], {
                placeHolder: 'Include translations in push?'
            });
            if (includeTranslations === undefined) return; // User cancelled
            const args = includeTranslations === 'Yes' ? ['push', '--translations'] : ['push'];
            runVdxCommand(args, 'Push to Vault');
        }),

        vscode.commands.registerCommand('vdx.pushDryRun', async () => {
            const includeTranslations = await vscode.window.showQuickPick(['No', 'Yes'], {
                placeHolder: 'Include translations in push (dry-run)?'
            });
            if (includeTranslations === undefined) return; // User cancelled
            const args = includeTranslations === 'Yes' ? ['push', '--dry-run', '--translations'] : ['push', '--dry-run'];
            runVdxCommand(args, 'Push Dry Run');
        }),

        vscode.commands.registerCommand('vdx.package', () => runVdxCommand(['package'], 'Package')),

        vscode.commands.registerCommand('vdx.cleanCache', () => runVdxCommand(['clean-cache'], 'Clean Cache Only')),

        vscode.commands.registerCommand('vdx.cleanFiles', async () => {
            const includeTranslations = await vscode.window.showQuickPick(['No', 'Yes'], {
                placeHolder: 'Include translations in deletion? (Default: No)'
            });
            if (includeTranslations === undefined) return;
            const args = includeTranslations === 'Yes' ? ['clean-files', '--include-translations'] : ['clean-files'];
            runVdxCommand(args, 'Clean All Files');
        }),

        vscode.commands.registerCommand('vdx.pushFile', (uri?: vscode.Uri) => {
            let targetPath = '';
            if (uri && uri.fsPath) {
                targetPath = uri.fsPath;
            } else {
                const editor = vscode.window.activeTextEditor;
                if (editor) {
                    targetPath = editor.document.uri.fsPath;
                }
            }
            if (!targetPath) {
                vscode.window.showErrorMessage("No file selected or active to push.");
                return;
            }
            runVdxCommand(['push', '--file', targetPath], `Push ${path.basename(targetPath)}`);
        }),

        vscode.commands.registerCommand('vdx.organizeFile', (uri?: vscode.Uri) => {
            const workspaceFolders = vscode.workspace.workspaceFolders;
            if (!workspaceFolders) {
                vscode.window.showErrorMessage("No workspace folder open.");
                return;
            }
            const workspaceRoot = workspaceFolders[0].uri.fsPath;
            
            let targetPath = '';
            let isTemp = false;

            const editor = vscode.window.activeTextEditor;
            
            if (uri && uri.fsPath && !(editor && editor.document.uri.fsPath === uri.fsPath && editor.document.isDirty)) {
                // Triggered from explorer, or from editor but the file is saved
                targetPath = uri.fsPath;
            } else if (editor) {
                // Triggered from command palette, or file is dirty/unsaved
                const tmpDir = path.join(workspaceRoot, '.tmp');
                if (!fs.existsSync(tmpDir)) {
                    fs.mkdirSync(tmpDir, { recursive: true });
                }
                targetPath = path.join(tmpDir, 'organize_temp.mdl');
                fs.writeFileSync(targetPath, editor.document.getText(), 'utf8');
                isTemp = true;
            }

            if (!targetPath) {
                vscode.window.showErrorMessage("No file selected or active to organize.");
                return;
            }
            
            const displayPath = isTemp ? "unsaved file" : path.basename(targetPath);
            runVdxCommand(['organize', targetPath], `Organize ${displayPath}`);
            
            // Clean up temp file after a short delay to allow CLI to read it
            if (isTemp) {
                setTimeout(() => {
                    if (fs.existsSync(targetPath)) {
                        fs.unlinkSync(targetPath);
                    }
                }, 5000);
            }
        }),

        vscode.commands.registerCommand('vdx.showChangesInUI', async () => {
            const workspaceFolders = vscode.workspace.workspaceFolders;
            if (!workspaceFolders) {
                vscode.window.showErrorMessage("No workspace folder open.");
                return;
            }
            const workspaceRoot = workspaceFolders[0].uri.fsPath;

            exec(`"${pythonCmd}" "${vdxMainPath}" patch --json`, { cwd: workspaceRoot }, async (error, stdout, stderr) => {
                if (error) {
                    vscode.window.showErrorMessage(`Error executing vdx patch: ${stderr || error.message}`);
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
                    changes.forEach((change: any) => {
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
                    let selectedChanges: any[] = [];

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
                            const tempFiles = changes.map((c: any) => c.original_file);
                            setTimeout(() => {
                                tempFiles.forEach((filePath: string) => fs.unlink(filePath, () => {}));
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
                    const tempFiles = changes.map((c: any) => c.original_file);
                    setTimeout(() => {
                        tempFiles.forEach((filePath: string) => {
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