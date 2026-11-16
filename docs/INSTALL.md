# Installing AdClip in another DSH

The plugin is an ordinary DSH profile bundle: DSH installs it with pnpm, then
loads its Host half (Node) and Client half (Web UI). The Python engine ships
inside the package and prepares its own runtime on first launch, so the person
installing it needs no checkout, no `pip install`, and no path configuration.

## What the user does

1. Open **Plugins** in the DSH sidebar.
2. **Add plugin** (or the arrow → **Install a third-party plugin**).
3. Paste one of:
   - a package name — `@chad.dev/dsh-adclip` (or `@chad.dev/dsh-adclip@0.1.0`),
   - a Git address — `https://github.com/<you>/adplus-studio`,
   - a tarball — `https://…/adplus-studio-0.1.0.tgz` or an absolute path to one,
   - an absolute path to an unpacked package directory.
4. Watch pnpm's output, then choose **Enable now**.
5. **Restart DSH** (`⌘Q`, then open it again).

Step 5 is not optional for a first install: the Web UI's client-module graph is
composed when the Host starts, so a bundle enabled in a running Host has no
sidebar entry until the next start. After the restart, **Ad+** appears in the
sidebar.

## First launch

The Host half resolves, in order, an interpreter it can use:

1. `python` from the plugin's row config (development override),
2. the virtualenv beside the engine sources (a source checkout),
3. the private venv this plugin built earlier, under
   `<data>/.engine/venv`,
4. the system `python3`, which it uses to build that private venv.

On a machine without the first two, the first launch creates the venv and runs
`pip install -r engine/requirements.txt` (about 20–60 s, network needed). The
Ad+ page shows **引擎准备中** while this happens, and the Settings tab shows the
interpreter, port and any failure. A failure offers **重新启动引擎**, which
retries the preparation.

Prerequisites:

| Tool | When | Install |
| --- | --- | --- |
| Python 3.10+ | only when no prepared runtime exists | macOS: `xcode-select --install` or `brew install python@3.12`; Windows: python.org installer or `winget install Python.Python.3.12`; Linux: `apt install python3 python3-venv python3-pip` |
| ffmpeg + ffprobe | media work (cut, stitch, probe) | macOS: `brew install ffmpeg`; Windows: `winget install Gyan.FFmpeg`; Linux: `apt install ffmpeg` |

A missing ffmpeg does not stop the engine: the page opens, and Settings shows
the install command until the tools appear in `PATH`.

## Where things live

- Data: `~/Library/Application Support/AdPlusStudio/data` (macOS),
  `%APPDATA%/AdPlusStudio/data` (Windows),
  `~/.local/share/adplus-studio/data` (Linux).
  Runs, assets, personas, settings and provider keys are plain files there.
- Engine runtime: `<data>/.engine/` — the private venv, its stamp, and
  `bootstrap.log`.
- Port: chosen at launch on `127.0.0.1`, so two installs and other local
  services never collide. The current port is on the Settings tab.

## Upgrades and removal

- **Upgrade**: install the new version over the old one (Plugins → the bundle's
  page → **Update**, or install `@chad.dev/dsh-adclip@0.2.0`). Data and the venv
  survive; the venv is rebuilt only when `requirements.txt` changes.
- **Remove**: Plugins → the bundle → **Remove**. The engine stops with the
  plugin. `<data>` is left untouched so a later reinstall keeps the history;
  delete that directory to reclaim the disk space.

## Troubleshooting

| Symptom | Where to look |
| --- | --- |
| Installed, enabled, no sidebar entry | Restart DSH — the client graph only includes bundles present at Host start. |
| **引擎不可用：找不到引擎源码** | The package is missing `engine/src/adclip/`. Rebuild it with `node scripts/stage-plugin.mjs`. |
| **创建 Python 虚拟环境失败** | Install the platform's `python3-venv` package (see the table above), then 重新启动引擎. |
| **安装引擎依赖失败** | Network or proxy blocked `pip`. Fix it, then 重新启动引擎; `<data>/.engine/bootstrap.log` has pip's output. |
| **ffmpeg 不可用** | Install ffmpeg, then reopen the page (no restart needed). |
| Engine exits right after start | `<data>/.engine/bootstrap.log` and the Ad+ Settings tab's engine card. |

## Publishing to npm

`plugin/` is the package root; `src/adclip/` is the engine. One command stages the
self-contained package and publishes it under your own npm scope:

```bash
npm login                                   # publish needs a 2FA-enabled account
node scripts/publish-npm.mjs                # -> @<your-npm-user>/dsh-adclip
node scripts/publish-npm.mjs --name @acme/dsh-adclip     # other scope
node scripts/publish-npm.mjs --dry-run      # validate without an account
node scripts/publish-npm.mjs --otp 123456   # non-interactive 2FA
```

It stages to `dist/dsh-adclip/`, runs `npm publish --access public`, and prints
the exact spec users should paste. If an unpublished version is required, bump
`version` in `plugin/package.json` first — npm refuses to overwrite a version.

Publishing the staged directory by hand needs a path npm recognises as one:

```bash
npm publish ./dist/dsh-adclip --access public
```

Note the `./`: `dist/dsh-adclip` alone is parsed as a GitHub `user/repo` spec.

What the staged package contains: the Host and Client halves, the bundle patch,
display resources, `README.md`, the engine sources and the pinned
`requirements.txt`. The script rewrites the package name into the bundle patch
and the client loader id, refuses to build when a developer path leaks into a
shipped file, and sets `engines.dsh` so incompatible DSH releases are rejected at
install time. Typical size: 95 kB packed, 385 kB unpacked.

`pnpm pack dist/adplus-studio` produces the same tarball without a registry, for
handing to someone directly.

## Local development install

Keep using the `link:` form the profile already has — the same code path serves
it. `engineRoot`/`python` from the row config (or this checkout's `.venv`) take
precedence over the bundled engine.

