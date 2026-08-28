const vscode = require('vscode');
const zlib = require('zlib');
const fs = require('fs');

const SCHEME = 'gzfs';

// Presents the gunzipped content of a real .gz file as a virtual document.
// readFile/writeFile decompress/recompress directly against the real file
// on disk -- there is no intermediate temp file at any point.
class GzFileSystemProvider {
  constructor() {
    this._emitter = new vscode.EventEmitter();
    this.onDidChangeFile = this._emitter.event;
  }

  watch() {
    return new vscode.Disposable(() => {});
  }

  stat(uri) {
    const st = fs.statSync(uri.fsPath);
    return {
      type: vscode.FileType.File,
      ctime: st.ctimeMs,
      mtime: st.mtimeMs,
      size: st.size,
    };
  }

  readDirectory() {
    return [];
  }

  createDirectory() {}

  readFile(uri) {
    const compressed = fs.readFileSync(uri.fsPath);
    try {
      return new Uint8Array(zlib.gunzipSync(compressed));
    } catch (err) {
      throw vscode.FileSystemError.Unavailable(
        `Failed to decompress ${uri.fsPath}: ${err.message}`
      );
    }
  }

  writeFile(uri, content) {
    const compressed = zlib.gzipSync(Buffer.from(content));
    fs.writeFileSync(uri.fsPath, compressed);
  }

  delete(uri) {
    fs.unlinkSync(uri.fsPath);
  }

  rename(oldUri, newUri) {
    fs.renameSync(oldUri.fsPath, newUri.fsPath);
  }
}

function toGzUri(fileUri) {
  return fileUri.with({ scheme: SCHEME });
}

function activate(context) {
  const provider = new GzFileSystemProvider();
  context.subscriptions.push(
    vscode.workspace.registerFileSystemProvider(SCHEME, provider, {
      isCaseSensitive: true,
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('gzInlineEditor.open', async (uri) => {
      if (!uri) {
        const active = vscode.window.activeTextEditor;
        uri = active ? active.document.uri : undefined;
      }
      if (!uri) {
        vscode.window.showErrorMessage('No .gz file selected to open.');
        return;
      }
      const doc = await vscode.workspace.openTextDocument(toGzUri(uri));
      await vscode.window.showTextDocument(doc);
    })
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
