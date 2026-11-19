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
sidebar entry until the next start. After the restart, **AdClip** appears in the
sidebar.

## Installing a version inside pnpm's 24-hour window

pnpm 11, which DSH bundles, defaults to `minimumReleaseAge: 1440`: a version
published less than 24 hours ago is not resolved, so DSH installs the newest
older version and shows a notice. That is a registry policy, not a plugin
failure, and the spec you paste decides whether it applies:

| Paste into **Add plugin** | Result for a fresh release |
| --- | --- |
| `@chad.dev/dsh-adclip` | newest version **older than 24 h** |
| `@chad.dev/dsh-adclip@0.1.2` | `ERR_PNPM_NO_MATURE_MATCHING_VERSION` |
| `https://registry.npmjs.org/…/dsh-adclip-0.1.2.tgz` | same error — pnpm looks the package up for its publish time |
| a tarball URL on **any other host** | installs immediately |
| absolute path to a downloaded `.tgz` | installs immediately |

So hand users a tarball the day it ships:

```bash
node scripts/release-tarball.mjs --url-base https://<host>/<path>
```

It stages the package, writes `dist/chad.dev-dsh-adclip-<version>.tgz`, prints
the SHA-256, and prints what to paste. Upload that file to a GitHub Release or any
static host — a non-registry URL skips the age check — and users paste the URL (or
the downloaded path) into **Add plugin**, then restart DSH.

Alternatives: wait 24 hours until the plain name resolves to it, or add the exact
version to `minimumReleaseAgeExclude` in
`~/.dsh/profiles/<profile>/pnpm-workspace.yaml`. That last one is a per-machine
setting and not something a plugin can ask of its users.

## First launch

The Host half resolves, in order, an interpreter it can use:

1. `python` from the plugin's row config (development override),
2. the virtualenv beside the engine sources (a source checkout),
3. the private venv this plugin built earlier, under
   `<data>/.engine/venv`,
4. the system `python3`, which it uses to build that private venv.

On a machine without the first two, the first launch creates the venv and runs
`pip install -r engine/requirements.txt` (about 20–60 s, network needed). The
AdClip page shows **引擎准备中** while this happens, and the Settings tab shows the
interpreter, port and any failure. A failure offers **重新启动引擎**, which
retries the preparation.

## What must exist on the machine

DSH installs the plugin package only. Everything below is resolved at runtime,
and nothing outside `engine/requirements.txt` is ever installed for the user.

| Dependency | Needed when | Automatic? | Missing looks like |
| --- | --- | --- | --- |
| Python 3.10+ | first enable, to build the private venv | no | **引擎不可用：未找到 Python 3.10+…** |
| `py` launcher (Windows) | same | ships with python.org / winget | only bare `python` and `py` are probed |
| PyPI reachable | first venv build only | — | **安装引擎依赖失败** (`<data>/.engine/bootstrap.log`) |
| ffmpeg + ffprobe on `PATH` | every media operation | no | **RuntimeError: ffprobe 不可用：未找到 ffmpeg…** |
| Writable `%APPDATA%` / data dir | always | — | engine exits on first write |
| `libx264`, `aac`, `loudnorm`, `xfade`, `testsrc2`, `anullsrc` | encode, stitch, test mode | part of a full ffmpeg build | a run fails late, not at startup |
| `MINIMAX_API_KEY` (or ARK/Kling) | paid generation | no | generation pages stay empty |
| DSH `llm` service | script/analysis text | DSH itself | falls back to MiniMax, then demo copy |
| `faster-whisper` + HuggingFace model (~500 MB) | optional ASR | **no** — not in `requirements.txt` | `analysis.asr.source` says `not_installed`/`failed` and the run warns instead of pretending the clip is silent |
| VC++ 2015-2022 runtime | ASR/OCR wheels | no | import error inside the venv |
| `rapidocr-onnxruntime` | declared in `pyproject.toml` only | no | the engine never imports it |

Platform install commands:

依赖提示页（首次启动/设置页）按系统生成安装步骤：Python 与 ffmpeg 给出对应包管理器的
命令（winget / brew / apt · dnf），可选语音识别给出运行时虚拟环境的真实解释器路径
（Windows `Scripts\python.exe`，macOS/Linux `bin/python`），模型下载失败的
`HF_ENDPOINT` 也按 PowerShell 与 POSIX shell 分别给出写法。

| Tool | macOS | Windows | Linux |
| --- | --- | --- | --- |
| Python 3.10+ | `xcode-select --install` or `brew install python@3.12` | python.org installer (tick *Add python.exe to PATH*) or `winget install --id Python.Python.3.12 -e` | `apt install python3 python3-venv python3-pip` |
| ffmpeg + ffprobe | `brew install ffmpeg` | `winget install --id Gyan.FFmpeg -e` (full build) | `apt install ffmpeg` |

On Windows, `scripts/install-windows.ps1` does both, puts ffmpeg's `bin` on the
user `PATH`, and reports the remaining gaps:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-windows.ps1 -CheckOnly
powershell -ExecutionPolicy Bypass -File scripts/install-windows.ps1
```

### Windows: install order and the PATH trap

1. Install Python 3.10+ **and** ffmpeg before enabling the plugin, or the first
   enable spends its time failing instead of building the venv.
2. Verify in a **new** terminal, not the one that ran `winget`:
   ```powershell
   py -0p            # 3.10+ and 3.12 as the default is the happy path
   where.exe ffmpeg
   where.exe ffprobe
   ```
3. Prefer Python 3.12: 3.13/3.14 occasionally lack prebuilt wheels, so pip falls
   back to compiling and asks for MSVC Build Tools.
4. **Quit DSH completely and reopen it** after installing ffmpeg. The engine
   inherits the Host's environment when it is spawned, and *重新启动引擎* only
   respawns within that same, stale environment. Refreshing the page is not
   enough; `ffprobe 不可用` will persist until DSH itself restarts.
5. Behind a corporate proxy or SSL inspection, set `HTTPS_PROXY` or
   `PIP_INDEX_URL` (e.g. `https://pypi.tuna.tsinghua.edu.cn/simple`) before the
   first enable; otherwise pip fails and the engine never boots.

A missing ffmpeg does not stop the engine: the page opens, and Settings shows
the install command until the tools appear in the *Host's* `PATH`.

## First-run setup page

Opening AdClip for the first time shows a setup page instead of the studio, on
every platform. It is rendered by the Host half, so it works while Python is
still missing — the engine cannot report its own absent interpreter.

One row per check: engine sources, Python 3.10+, the private venv, `ffmpeg`,
`ffprobe`, the data directory, and optional local ASR. A failing row carries the
platform's install command with a **复制命令** button, a download link, and the
note that matters on Windows: **quit and reopen DSH after installing**, because
the running Host keeps the `PATH` it started with. **重新检测** re-runs everything
without restarting the engine.

The choices live in `<data>/.engine/setup.json`:

- **开始使用** records `doneAt`; the page stops opening by itself.
- **稍后再说** records `skippedAt`; the studio opens with a warning banner and
  Settings → **环境检查** brings the page back.
- If a required dependency disappears later, the page returns on its own unless
  it was skipped.

The page never installs anything: commands are copied, not executed. That keeps
the plugin out of elevation prompts, corporate proxies and surprise downloads.
Checks are implemented once in `plugin/host/preflight.js` and shared by macOS,
Windows and Linux; only the remediation commands differ.

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
  page → **Update**, or install `@chad.dev/dsh-adclip@0.1.2`). Data and the venv
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
| **ffmpeg 不可用** | Install ffmpeg, then **quit and reopen DSH** — the engine keeps the `PATH` it was spawned with. |
| **ffprobe 不可用** but `ffmpeg` works | The bin directory holds one but not the other; install a full ffmpeg build. |
| **未找到 Python 3.10+** although 3.12 is installed | `py`/`python` resolve to an older default; put the 3.12 directory first on `PATH` or uninstall the old one. |
| Engine stuck on **引擎准备中** | `<data>/.engine/bootstrap.log`; a pip download over a slow proxy can exceed the 10-minute bootstrap window. |
| Runs succeed but there is never a transcript | Check `GET /adplus/api/asr/status` (or `adclip_transcribe_audio`): `not_installed` → `pip install faster-whisper` into `<data>/.engine/venv`; `failed` → read `last_error`, set `HF_ENDPOINT` where HuggingFace is blocked. |
| 台词只转出一半 / 同音字多 | 覆盖率不足会自动用无 VAD 模式重试；同音字由**当前文本模型**校正（DSH 默认/run 里选的文本模型，失败自动切 Ark lite→turbo→pro）。`ADSTUDIO_ASR_CLEANUP=0` 关闭，`ADSTUDIO_ASR_CLEANUP_MODEL` 强制指定模型。仍不准时设 `ADSTUDIO_ASR_MODEL=medium`（首次多下载约 1.5GB，速度更慢）。 |
| Setup page stays on **正在检查环境…** | The Host check threw; restart DSH and look at its log, then 重新检测. |
| Setup page reappears after 稍后再说 | State could not be written to `<data>/.engine/setup.json` — check the data directory again. |
| Engine exits right after start | `<data>/.engine/bootstrap.log` and the AdClip Settings tab's engine card. |

## Publishing to npm

Publishing makes a version available to the registry, but pnpm 11 (and therefore
DSH) will not install it for 24 hours — see *Installing a version inside pnpm's
24-hour window*. When a release must be usable immediately, also run
`node scripts/release-tarball.mjs` and share the tarball URL.

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

