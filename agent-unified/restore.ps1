# Windows PowerShell 5.1 / PowerShell 7，使用随包 Python。
[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$Verify,
    [switch]$Doctor,
    [switch]$Offline,
    [switch]$SkipSystem,
    [switch]$NoPath,
    [switch]$ReplaceExistingMcp,
    [switch]$ReplaceExistingSkills,
    [string]$Root,
    [string]$CodexHome,
    [string]$SkillsDir,
    [string]$ProjectDir,
    [string]$Rollback,
    [string]$Platform
)
$ErrorActionPreference = 'Stop'
$bundle = $PSScriptRoot
$archive = Get-ChildItem -LiteralPath "$bundle\assets\runtimes\windows-x86_64" -Filter 'cpython-3.13.13*.tar.gz'
if (@($archive).Count -ne 1) { throw '缺少或存在多份 Windows Python 运行时，请完整解压迁移包。' }
$expected = (Get-Content -LiteralPath ($archive.FullName + '.sha256') -Raw).Trim()
if ((Get-FileHash -LiteralPath $archive.FullName -Algorithm SHA256).Hash.ToLower() -ne $expected) { throw 'Python 归档校验失败。' }
$bootstrap = Join-Path ([IO.Path]::GetTempPath()) ('agent-unified-bootstrap-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $bootstrap | Out-Null
try {
    & tar.exe -xzf $archive.FullName -C $bootstrap
    if ($LASTEXITCODE -ne 0) { throw '无法解压 Python；需要 Windows 自带 tar.exe。' }
    $arguments = @('-X', 'utf8', "$bundle\restore.py")
    foreach ($item in @(@('Apply','--apply'),@('Verify','--verify'),@('Doctor','--doctor'),@('Offline','--offline'),@('SkipSystem','--skip-system'),@('NoPath','--no-path'),@('ReplaceExistingMcp','--replace-existing-mcp'),@('ReplaceExistingSkills','--replace-existing-skills'))) {
        if (Get-Variable -Name $item[0] -ValueOnly) { $arguments += $item[1] }
    }
    foreach ($item in @(@('Root','--root'),@('CodexHome','--codex-home'),@('SkillsDir','--skills-dir'),@('ProjectDir','--project-dir'),@('Rollback','--rollback'),@('Platform','--platform'))) {
        $value = Get-Variable -Name $item[0] -ValueOnly
        if ($value) { $arguments += @($item[1], $value) }
    }
    $env:PYTHONUTF8 = '1'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & "$bootstrap\python\python.exe" @arguments
    $restoreExitCode = $LASTEXITCODE
} finally {
    $resolved = [IO.Path]::GetFullPath($bootstrap)
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if ($resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -and ([IO.Path]::GetFileName($resolved)).StartsWith('agent-unified-bootstrap-')) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
exit $restoreExitCode
