[CmdletBinding()]
param(
    [string]$OutDir,
    [switch]$IncludeWork,
    [switch]$IncludeInbox,
    [switch]$SkipLibrary,
    [switch]$SkipZip,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'

if (-not $OutDir) {
    $OutDir = Join-Path $Root ("dist\FGUI-ArtFlow_$Stamp")
}
$OutDir = [System.IO.Path]::GetFullPath($OutDir)
$ZipPath = "$OutDir.zip"

if ($OutDir -eq $Root) {
    throw "输出目录不能是工作区根：$OutDir"
}
$OpenCodeRoot = Join-Path $Root '.opencode'
if ($OutDir.StartsWith($OpenCodeRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "输出目录不能放在 .opencode 里面：$OutDir"
}

if (Test-Path -LiteralPath $OutDir) {
    if (-not $Force) {
        throw "输出目录已存在：$OutDir（加 -Force 覆盖）"
    }
    Remove-Item -LiteralPath $OutDir -Recurse -Force
}
if (Test-Path -LiteralPath $ZipPath) {
    if (-not $Force) {
        throw "压缩包已存在：$ZipPath（加 -Force 覆盖）"
    }
    Remove-Item -LiteralPath $ZipPath -Force
}

New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

$ExcludeDirs = @('node_modules', '__pycache__', '.git', 'dist')
if (-not $IncludeWork) { $ExcludeDirs += 'work' }
if (-not $IncludeInbox) { $ExcludeDirs += 'inbox' }
if ($SkipLibrary) { $ExcludeDirs += 'PSD素材库' }

$ExcludeFiles = @(
    'workspace.json',
    'photocraft.json',
    '.gitignore',
    'package.json',
    'package-lock.json',
    'bun.lock',
    '*.pyc'
)

Write-Host "工作区根：$Root"
Write-Host "输出目录：$OutDir"

# 1. 复制 .opencode 目录
$Source = Join-Path $Root '.opencode'
$Dest = Join-Path $OutDir '.opencode'
$RoboArgs = @($Source, $Dest, '/E')
if ($ExcludeDirs.Count -gt 0) {
    $RoboArgs += '/XD'
    $RoboArgs += $ExcludeDirs
}
if ($ExcludeFiles.Count -gt 0) {
    $RoboArgs += '/XF'
    $RoboArgs += $ExcludeFiles
}
$RoboArgs += @('/NFL', '/NDL', '/NJH', '/NJS', '/NP')

& robocopy @RoboArgs | Out-Null
$RoboCode = $LASTEXITCODE
if ($RoboCode -ge 8) {
    throw "robocopy 复制 .opencode 失败，退出码 $RoboCode"
}

# 2. 复制 docs 目录到顶层
$DocsSource = Join-Path $Root 'docs'
$DocsDest = Join-Path $OutDir 'docs'
$DocsRoboArgs = @($DocsSource, $DocsDest, '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/NP')
& robocopy @DocsRoboArgs | Out-Null
if ($LASTEXITCODE -ge 8) {
    throw "robocopy 复制 docs 失败，退出码 $LASTEXITCODE"
}

# 3. 复制 AGENTS.md
$Agents = Join-Path $Root 'AGENTS.md'
if (Test-Path -LiteralPath $Agents) {
    Copy-Item -LiteralPath $Agents -Destination (Join-Path $OutDir 'AGENTS.md')
} else {
    Write-Warning "未找到工作区根的 AGENTS.md，交付包会缺少会话级硬规矩"
}

# 4. 生成说明文件
$InfoLines = @(
    'FGUI 美术流程交付包',
    '',
    "打包时间：$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "来源工作区：$Root",
    '',
    '文档入口：docs/README.md',
    '首次使用：docs/02-安装与首次配置.md',
    '命令手册：docs/03-命令手册.md',
    'PhotoCraft/MCP：docs/06-PhotoCraft与MCP配置.md',
    '打包/迁移：docs/07-打包与迁移.md',
    '常见问题：docs/08-常见问题.md',
    '',
    '本包不包含 workspace.json、photocraft.json、token 文件和模型 API Key。',
    '接收方按 docs/02-安装与首次配置.md 安装依赖并运行 s0 定位工程。'
)
[System.IO.File]::WriteAllLines(
    (Join-Path $OutDir 'PACKAGE-INFO.txt'),
    $InfoLines,
    (New-Object System.Text.UTF8Encoding($false))
)

$Readme = @(
    '先看这里',
    '',
    '1. 解压到工作区根（含 .opencode 的那层）。',
    '2. 打开 docs/README.md 查看文档目录。',
    '3. 首次安装与定位看 docs/02-安装与首次配置.md。',
    '4. s3/s4 的 PhotoCraft 与 MCP 看 docs/06-PhotoCraft与MCP配置.md。',
    '5. 打包与迁移看 docs/07-打包与迁移.md。',
    '',
    '注意：本包不带 token、API Key、workspace.json、photocraft.json。'
)
[System.IO.File]::WriteAllLines(
    (Join-Path $OutDir '先看这里.txt'),
    $Readme,
    (New-Object System.Text.UTF8Encoding($false))
)

# 5. 压缩成 .zip
$Size = (Get-ChildItem -LiteralPath $OutDir -Recurse -File | Measure-Object -Property Length -Sum).Sum
if (-not $SkipZip) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $Items = Get-ChildItem -LiteralPath $OutDir -Force | Select-Object -ExpandProperty FullName
    Compress-Archive -LiteralPath $Items -DestinationPath $ZipPath -Force
    $ZipSize = (Get-Item -LiteralPath $ZipPath).Length
    Write-Host "打包成功：$ZipPath（$([math]::Round($ZipSize / 1MB, 1)) MB）"
} else {
    Write-Host "打包成功：$OutDir（$([math]::Round($Size / 1MB, 1)) MB，未压缩）"
}
