/*
Minimal Remotion SSR entrypoint for rendering a normalized storyboard.

Compatibility: Remotion 4.x (tested with 4.0.365+).
Requires @remotion/bundler and @remotion/renderer installed in the target project.

Example:
  npx tsx scripts/render_video.ts \
    --entry remotion/index.ts \
    --props workspace/storyboard.normalized.json \
    --composition RemotionVideo \
    --out workspace/output/final.mp4
*/

import fs from 'node:fs/promises';
import {existsSync} from 'node:fs';
import {createRequire} from 'node:module';
import path from 'node:path';

type CliArgs = {
  entry: string;
  props: string;
  composition: string;
  out: string;
  codec: string;
  chromeMode: string;
  browserExecutable: string;
};

type ChromeMode = 'chrome-for-testing' | 'headless-shell';

const findDefaultBrowserExecutable = () => {
  const candidates =
    process.platform === 'win32'
      ? [
          'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
          'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
          `${process.env.LOCALAPPDATA ?? ''}\\Google\\Chrome\\Application\\chrome.exe`,
          `${process.env.PROGRAMFILES ?? ''}\\Google\\Chrome\\Application\\chrome.exe`,
        ]
      : process.platform === 'darwin'
        ? [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Chromium.app/Contents/MacOS/Chromium',
          ]
        : [
            '/usr/bin/google-chrome',
            '/usr/bin/google-chrome-stable',
            '/usr/bin/chromium',
            '/usr/bin/chromium-browser',
            '/snap/bin/chromium',
          ];

  return (
    candidates.find((candidate) => {
      return candidate && existsSync(candidate);
    }) ?? ''
  );
};

function parseArgs(argv: string[]): CliArgs {
  const defaults: CliArgs = {
    entry: '',
    props: '',
    composition: 'RemotionVideo',
    out: '',
    codec: 'h264',
    chromeMode: process.env.REMOTION_CHROME_MODE ?? 'auto',
    browserExecutable:
      process.env.REMOTION_BROWSER_EXECUTABLE ?? findDefaultBrowserExecutable(),
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = argv[i + 1];
    if (arg === '--entry' && next) defaults.entry = next;
    if (arg === '--props' && next) defaults.props = next;
    if (arg === '--composition' && next) defaults.composition = next;
    if (arg === '--out' && next) defaults.out = next;
    if (arg === '--codec' && next) defaults.codec = next;
    if (arg === '--chrome-mode' && next) defaults.chromeMode = next;
    if (arg === '--browser-executable' && next) defaults.browserExecutable = next;
  }

  if (!defaults.entry || !defaults.props || !defaults.out) {
    throw new Error(
      'Missing required arguments. Expected --entry <file> --props <json> --out <mp4>.'
    );
  }

  return defaults;
}

async function readJson<T>(filePath: string): Promise<T> {
  const content = await fs.readFile(filePath, 'utf8');
  return JSON.parse(content) as T;
}

async function loadRemotionModules(entry: string) {
  const requireFromEntry = createRequire(entry);
  const bundler = requireFromEntry(
    '@remotion/bundler'
  ) as typeof import('@remotion/bundler');
  const renderer = requireFromEntry(
    '@remotion/renderer'
  ) as typeof import('@remotion/renderer');
  return {
    bundle: bundler.bundle,
    openBrowser: renderer.openBrowser,
    renderMedia: renderer.renderMedia,
    selectComposition: renderer.selectComposition,
  };
}

/**
 * 尝试以指定 chromeMode 打开浏览器；如果失败则 fallback 到另一种模式。
 * Remotion 4.x 在不同安装环境下对 chromeMode 的支持不同：
 *   - chrome-for-testing: 需要 Chrome for Testing 二进制
 *   - headless-shell: 使用 Remotion 自带的 headless shell
 * 当用户传 'auto' 时，先尝试 headless-shell（兼容性最好），失败再尝试 chrome-for-testing。
 */
async function openBrowserWithFallback(
  openBrowser: Awaited<ReturnType<typeof loadRemotionModules>>['openBrowser'],
  requestedMode: string,
  browserExecutable: string
) {
  const modeOrder: ChromeMode[] =
    requestedMode === 'chrome-for-testing'
      ? ['chrome-for-testing', 'headless-shell']
      : requestedMode === 'headless-shell'
        ? ['headless-shell', 'chrome-for-testing']
        : ['headless-shell', 'chrome-for-testing'];

  let lastError: unknown;
  for (const mode of modeOrder) {
    try {
      console.log(`Trying to open browser with chromeMode=${mode}`);
      const browser = await openBrowser('chrome', {
        browserExecutable: browserExecutable || null,
        chromeMode: mode,
        logLevel: 'info',
      });
      console.log(`Browser opened successfully with chromeMode=${mode}`);
      return browser;
    } catch (error) {
      lastError = error;
      const message = error instanceof Error ? error.message : String(error);
      console.warn(
        `WARN: chromeMode=${mode} failed: ${message}. ` +
          (mode === modeOrder[modeOrder.length - 1]
            ? 'No more fallback modes.'
            : 'Trying next mode...')
      );
    }
  }
  throw lastError;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const entry = path.resolve(args.entry);
  const propsPath = path.resolve(args.props);
  const outPath = path.resolve(args.out);
  const inputProps = await readJson<Record<string, unknown>>(propsPath);
  const {bundle, openBrowser, renderMedia, selectComposition} =
    await loadRemotionModules(entry);

  await fs.mkdir(path.dirname(outPath), {recursive: true});

  console.log(`Bundling Remotion project from ${entry}`);
  const bundled = await bundle({
    entryPoint: entry,
    onProgress: (progress) => {
      const normalizedProgress = progress > 1 ? progress : progress * 100;
      console.log(`Bundle progress: ${normalizedProgress.toFixed(1)}%`);
    },
  });

  const browser = await openBrowserWithFallback(
    openBrowser,
    args.chromeMode,
    args.browserExecutable
  );

  try {
    console.log(`Selecting composition: ${args.composition}`);
    const composition = await selectComposition({
      serveUrl: bundled,
      id: args.composition,
      inputProps,
      puppeteerInstance: browser,
    });

    console.log(
      `Rendering ${composition.id} at ${composition.width}x${composition.height}, ` +
        `${composition.fps}fps, ${composition.durationInFrames} frames`
    );

    await renderMedia({
      serveUrl: bundled,
      composition,
      codec: args.codec as 'h264' | 'h265' | 'vp8' | 'vp9' | 'prores',
      audioCodec: 'aac',
      audioBitrate: '320K',
      enforceAudioTrack: true,
      logLevel: 'info',
      outputLocation: outPath,
      inputProps,
      puppeteerInstance: browser,
      onProgress: (progress) => {
        console.log(
          `Render progress: rendered=${progress.renderedFrames} ` +
            `encoded=${progress.encodedFrames} stage=${progress.stitchStage}`
        );
      },
    });
  } finally {
    try {
      await browser.close();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.warn(`WARN: browser cleanup failed after render: ${message}`);
    }
  }

  console.log(`Render complete: ${outPath}`);
}

main()
  .then(() => {
    setTimeout(() => process.exit(0), 300);
  })
  .catch((error) => {
    if (error instanceof Error) {
      console.error(`ERROR: ${error.message}`);
      if (error.stack) {
        console.error(error.stack);
      }
    } else {
      console.error(`ERROR: ${String(error)}`);
    }
    setTimeout(() => process.exit(1), 300);
  });
