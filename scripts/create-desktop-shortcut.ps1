# 바탕화면 바로가기 생성 (1회 실행): .\scripts\create-desktop-shortcut.ps1
$root = Split-Path -Parent $PSScriptRoot
$desktop = [Environment]::GetFolderPath("Desktop")
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut("$desktop\개인투자관리시스템.lnk")
$sc.TargetPath = "$root\start-invest-system.bat"
$sc.WorkingDirectory = $root
$sc.IconLocation = "shell32.dll,137"   # 차트 모양 아이콘
$sc.Description = "개인투자관리시스템 실행 (백엔드+프론트+브라우저)"
$sc.Save()
Write-Host "바탕화면에 '개인투자관리시스템' 바로가기를 만들었습니다."
