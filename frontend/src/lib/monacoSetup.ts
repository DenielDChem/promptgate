// Monaco bootstrap — offline, slim, and Vite-friendly.
//
// PromptGate is self-hosted with a no-external-calls promise (architecture §0),
// so we must NOT let @monaco-editor/react fetch the editor from a CDN (its
// default). We also don't want the full 4 MB distribution that bundles every
// language; templates are plain text highlighted as `handlebars`. So we import
// a *slim* Monaco built from the ESM entry points:
//
//   • `editor.api`            — the editor API surface (monaco.editor, markers…)
//   • `editor.all`            — core editor contributions (find, hover, …)
//   • basic-languages/handlebars — the only syntax we highlight
//
// Workers: the slim build only needs the base `editor.worker` (no TS/JSON/CSS
// language services), wired through Vite's `?worker` suffix → built locally at
// compile time (no CDN, no eval).
//
// Import this module once for its side effects before the editor mounts.

import { loader } from '@monaco-editor/react';
// Runtime: the slim ESM entry (no language pack). Its types ship without
// per-path .d.ts, so we borrow the namespace type from the package root below.
// @ts-expect-error — deep ESM path has no bundled declaration file.
import * as monacoRuntime from 'monaco-editor/esm/vs/editor/editor.api';
import 'monaco-editor/esm/vs/editor/editor.all.js';
import 'monaco-editor/esm/vs/basic-languages/handlebars/handlebars.contribution.js';
// Vite turns this into a Worker constructor at build time (no CDN, no eval).
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker';
import type * as Monaco from 'monaco-editor';

// The slim runtime API is the same shape as the package's typed namespace.
const monaco = monacoRuntime as typeof Monaco;

declare global {
  // eslint-disable-next-line no-var
  var MonacoEnvironment: Monaco.Environment | undefined;
}

let configured = false;

export function setupMonaco(): void {
  if (configured) return;
  configured = true;

  self.MonacoEnvironment = {
    getWorker() {
      return new EditorWorker();
    },
  };

  // Hand the React wrapper our locally-bundled instance instead of the CDN one.
  loader.config({ monaco });
}

export { monaco };
