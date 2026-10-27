# 捕获 FairyGUI 编辑器窗口截图（编辑器内置 ScreenCapture 在部分构建被裁，用 OS 级兜底）
# 用法: powershell -ExecutionPolicy Bypass -File capture_editor.ps1 -OutPath "E:\tmp\x.png"
param(
  [Parameter(Mandatory = $true)][string]$OutPath
)

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$proc = Get-Process -Name "FairyGUI-Editor" -ErrorAction Stop | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $proc) { throw "未找到 FairyGUI 编辑器窗口（进程未运行或无主窗口）" }

# 用 Win32 SetForegroundWindow 激活目标窗口，再整屏复制（CopyFromScreen）
$sig = '[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);'
$type = Add-Type -MemberDefinition $sig -Name "Win32" -Namespace "Native" -PassThru
[void]$type::SetForegroundWindow($proc.MainWindowHandle)
Start-Sleep -Milliseconds 400

$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$gfx.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$gfx.Dispose()

$outDir = Split-Path -Parent $OutPath
if ($outDir -and -not (Test-Path $outDir)) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
$bmp.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Output "已保存: $OutPath"
