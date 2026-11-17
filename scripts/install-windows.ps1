<#
.SYNOPSIS
  AdClip（DSH 插件）在 Windows 上的环境准备 / 自检脚本。

.DESCRIPTION
  这个脚本只处理“pip 不会替你装”的那部分依赖：
    * Python 3.10+（优先 3.12；避免 3.13/3.14 上部分 wheel 还没发布）
    * ffmpeg + ffprobe（winget 的 Gyan.FFmpeg full build）
    * 把 ffmpeg 的 bin 目录写进“用户 PATH”，并刷新当前会话
  它不会安装插件本身，也不会动 AdClip 的数据目录。

  默认会安装缺失项；加 -CheckOnly 只检查、不修改系统。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/install-windows.ps1 -CheckOnly
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/install-windows.ps1
#>
[CmdletBinding()]
param(
  [switch]$CheckOnly,
  [string]$PythonSeries = '3.12',
  [switch]$SkipFfmpeg
)

$ErrorActionPreference = 'Stop'
$script:ok = $true
$wingetAlreadyInstalled = -1978335189  # 0x8A15002B

function Write-Step([string]$text) { Write-Host "`n== $text" -ForegroundColor Cyan }
function Write-Ok([string]$text)   { Write-Host "  [OK] $text" -ForegroundColor Green }
function Write-Bad([string]$text)  { Write-Host "  [!!] $text" -ForegroundColor Red; $script:ok = $false }
function Write-Info([string]$text) { Write-Host "       $text" -ForegroundColor DarkGray }

function Refresh-Path {
  $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
  $user    = [Environment]::GetEnvironmentVariable('Path', 'User')
  $env:Path = (@($machine, $user) | Where-Object { $_ }) -join ';'
}

function Add-UserPath([string]$dir) {
  if (-not $dir) { return }
  $user  = [Environment]::GetEnvironmentVariable('Path', 'User')
  $parts = @($user -split ';' | Where-Object { $_ })
  if ($parts -notcontains $dir) {
    [Environment]::SetEnvironmentVariable('Path', (@($parts + $dir) -join ';'), 'User')
    Write-Info "已把 $dir 写入用户 PATH"
  }
  if (($env:Path -split ';') -notcontains $dir) { $env:Path = $env:Path + ';' + $dir }
}

function Get-PythonInterpreters {
  $found = @()
  $py = Get-Command py.exe -ErrorAction SilentlyContinue
  if ($py) {
    try {
      foreach ($line in (& py -0p 2>$null)) {
        if ($line -match '-V:(\d+)\.(\d+)(\s+\*)?\s+(.+?)\s*$') {
          $found += [pscustomobject]@{
            Major  = [int]$Matches[1]
            Minor  = [int]$Matches[2]
            Path   = $Matches[4].Trim()
            Source = 'py launcher'
          }
        }
      }
    } catch { }
  }
  $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
  # Microsoft Store 的 python.exe 是占位 stub，跑起来只会弹商店，必须排除。
  if ($cmd -and $cmd.Source -notmatch '\\WindowsApps\\') {
    try {
      $v = (& $cmd.Source -c "import sys;print('%d.%d' % sys.version_info[:2])" 2>$null)
      if ($v -match '^(\d+)\.(\d+)$') {
        $found += [pscustomobject]@{
          Major  = [int]$Matches[1]
          Minor  = [int]$Matches[2]
          Path   = $cmd.Source
          Source = 'PATH'
        }
      }
    } catch { }
  }
  $seen = @{}
  $found | Where-Object {
    $key = "$($_.Major).$($_.Minor)|$($_.Path)".ToLowerInvariant()
    if ($seen.ContainsKey($key)) { $false } else { $seen[$key] = $true; $true }
  } | Sort-Object Major, Minor -Descending
}

function Find-Ffmpeg {
  $cmd = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $roots = @(
    (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'),
    (Join-Path $env:USERPROFILE 'scoop\apps\ffmpeg\current\bin'),
    'C:\ffmpeg\bin',
    (Join-Path $env:ProgramFiles 'ffmpeg\bin')
  )
  foreach ($root in $roots) {
    if (-not (Test-Path $root)) { continue }
    $hit = Get-ChildItem $root -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue |
      Select-Object -First 1
    if ($hit) { return $hit.FullName }
  }
  return $null
}

function Invoke-Winget([string]$id) {
  $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
  if (-not $winget) {
    Write-Bad '找不到 winget（App Installer）。Win10 1809 以前没有，请按下面链接手动安装。'
    Write-Info 'Python: https://www.python.org/downloads/windows/  （勾选 Add python.exe to PATH）'
    Write-Info 'ffmpeg: https://www.gyan.dev/ffmpeg/builds/  （解压后把 bin 目录加入 PATH）'
    return $false
  }
  Write-Info "winget install --id $id -e"
  & winget install --id $id -e --source winget `
      --accept-package-agreements --accept-source-agreements
  $code = $LASTEXITCODE
  if ($code -eq 0 -or $code -eq $wingetAlreadyInstalled) { return $true }
  Write-Bad "winget 安装 $id 失败（退出码 $code）"
  return $false
}

Write-Host 'AdClip / Windows 环境检查' -ForegroundColor White
Write-Info ("模式：{0}" -f $(if ($CheckOnly) { '只检查' } else { '检查并安装缺失项' }))

# --- 1. Python -------------------------------------------------------------
Write-Step '1/3  Python 3.10+（首次启用插件时用来创建私有 venv）'
$pythons = @(Get-PythonInterpreters)
$usable  = @($pythons | Where-Object { $_.Major -gt 3 -or ($_.Major -eq 3 -and $_.Minor -ge 10) })
if ($usable.Count -gt 0) {
  foreach ($p in $usable) { Write-Ok ("Python {0}.{1}  {2}（{3}）" -f $p.Major, $p.Minor, $p.Path, $p.Source) }
  $newest = $usable | Select-Object -First 1
  if ($newest.Minor -ge 13) {
    Write-Info '提示：3.13/3.14 上个别依赖可能还没有预编译 wheel，失败时改用 3.12 更稳。'
  }
  # 插件当前用裸 `python` / `py` 启动，若它们指向旧版本，装了新版本也白搭。
  $defaultText = $null
  try { $defaultText = (& py -V 2>$null) } catch { }
  if (-not $defaultText) { try { $defaultText = (& python -V 2>$null) } catch { } }
  if ($defaultText -match '(\d+)\.(\d+)') {
    $dmaj = [int]$Matches[1]; $dmin = [int]$Matches[2]
    if ($dmaj -lt 3 -or ($dmaj -eq 3 -and $dmin -lt 10)) {
      Write-Bad ("默认解释器是 Python {0}.{1}，插件会先撞上它。把 3.10+ 的目录放到 PATH 最前面，或卸载旧版本。" -f $dmaj, $dmin)
    }
  }
} else {
  if ($pythons.Count -gt 0) {
    $pythons | ForEach-Object { Write-Info ("发现 Python {0}.{1}（{2}），版本太低" -f $_.Major, $_.Minor, $_.Path) }
  }
  if ($CheckOnly) {
    Write-Bad '未找到 Python 3.10+。安装：winget install --id Python.Python.3.12 -e'
  } elseif (Invoke-Winget "Python.Python.$PythonSeries") {
    Refresh-Path
    $usable = @(Get-PythonInterpreters | Where-Object { $_.Major -gt 3 -or ($_.Major -eq 3 -and $_.Minor -ge 10) })
    if ($usable.Count -gt 0) {
      $usable | ForEach-Object { Write-Ok ("已安装 Python {0}.{1}  {2}" -f $_.Major, $_.Minor, $_.Path) }
    } else {
      Write-Bad '安装完成但检测不到 Python。请重开一个终端再跑一次本脚本。'
    }
  }
}

# --- 2. ffmpeg -------------------------------------------------------------
Write-Step '2/3  ffmpeg + ffprobe（切点、抽帧、拼接、归一化、导出）'
if ($SkipFfmpeg) {
  Write-Info '按参数跳过。'
} else {
  $ffmpeg = Find-Ffmpeg
  if ($ffmpeg) {
    $dir = Split-Path $ffmpeg -Parent
    Add-UserPath $dir
    Write-Ok "ffmpeg  $ffmpeg"
    $probe = Join-Path $dir 'ffprobe.exe'
    if (Test-Path $probe) { Write-Ok "ffprobe $probe" }
    else { Write-Bad '同一目录下没有 ffprobe.exe，请换一个完整构建（Gyan.FFmpeg full）。' }
    try {
      $version = (& $ffmpeg -hide_banner -version 2>$null | Select-Object -First 1)
      if ($version) { Write-Info $version }
    } catch { }
  } elseif ($CheckOnly) {
    Write-Bad '未找到 ffmpeg/ffprobe。安装：winget install --id Gyan.FFmpeg -e'
  } else {
    if (Invoke-Winget 'Gyan.FFmpeg') {
      Refresh-Path
      $ffmpeg = Find-Ffmpeg
      if ($ffmpeg) {
        Add-UserPath (Split-Path $ffmpeg -Parent)
        Write-Ok "ffmpeg  $ffmpeg"
      } else {
        Write-Bad '安装完成但仍找不到 ffmpeg.exe。重开终端再试，或手动把 bin 目录加入 PATH。'
      }
    }
  }
}

# --- 3. 其它运行时条件 -----------------------------------------------------
Write-Step '3/3  数据目录与网络（首次启动时 pip 需要联网）'
$dataDir = Join-Path $env:APPDATA 'AdPlusStudio\data'
try {
  New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
  $probeFile = Join-Path $dataDir '.write-test'
  Set-Content -Path $probeFile -Value 'ok' -Encoding ASCII
  Remove-Item $probeFile -Force
  Write-Ok "数据目录可写  $dataDir"
} catch {
  Write-Bad "数据目录不可写  $dataDir"
}

$proxy = $env:HTTPS_PROXY
if ($proxy) { Write-Info "检测到 HTTPS_PROXY=$proxy（pip 会走它）" }
Write-Info '首次启用会用 pip 从 PyPI 下载约 40–60 MB；公司代理/SSL 拦截会导致“安装引擎依赖失败”。'
Write-Info '国内网络可设 PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple 后重试。'
Write-Info '可选：OCR/ASR 这类扩展依赖需要 VC++ 运行库（winget install Microsoft.VCRedist.2015+.x64）。'

Write-Host ''
if ($script:ok) {
  Write-Host '检查通过。下一步：' -ForegroundColor Green
} else {
  Write-Host '还有未满足的项，见上面的 [!!]。' -ForegroundColor Yellow
}
Write-Host '  1. 完全退出 DSH（不是只关窗口/刷新页面），再重新打开。' -ForegroundColor White
Write-Host '     PATH 是进程启动时拷贝的，只重启插件引擎不会看到新装的 ffmpeg。' -ForegroundColor DarkGray
Write-Host '  2. Plugins → AdClip → 设置，确认「引擎运行时」显示在线。' -ForegroundColor White
Write-Host '  3. 没有 API key 时生成页会为空，这是正常的，不是环境错误。' -ForegroundColor White

if (-not $script:ok) { exit 1 }
