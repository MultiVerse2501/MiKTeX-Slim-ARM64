# Add or remove the portable bin directory in the user Path.
#
#   powershell -File user-path.ps1 add [-Front]
#   powershell -File user-path.ps1 remove
#
# The user Path is read and written RAW (DoNotExpandEnvironmentNames), so
# %VAR% references in other entries survive, and the value kind (usually
# REG_EXPAND_SZ) is preserved. Adding records the entry in
# texmfs\registered-user-path.txt so remove takes out exactly what add put
# in, even if the tree has moved since. A WM_SETTINGCHANGE broadcast lets
# new terminals see the change without a sign-out. Per-user only; the
# system Path is never touched.
param(
    [Parameter(Mandatory = $true)][ValidateSet('add', 'remove')][string]$Action,
    [switch]$Front
)
$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$binDir = (Join-Path $here 'texmfs\install\miktex\bin\arm64').TrimEnd('\')
$marker = Join-Path $here 'texmfs\registered-user-path.txt'

if ($Action -eq 'add' -and -not (Test-Path -LiteralPath (Join-Path $binDir 'initexmf.exe'))) {
    throw "This folder does not contain the ARM64 MiKTeX binaries: $binDir"
}

$key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment', $true)
if ($null -eq $key) {
    throw "cannot open HKCU\Environment for writing"
}
try {
    $raw = [string]$key.GetValue('Path', '',
        [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
    try {
        $kind = $key.GetValueKind('Path')
    }
    catch {
        $kind = [Microsoft.Win32.RegistryValueKind]::ExpandString
    }
    $entries = @($raw -split ';' | Where-Object { $_ -ne '' })
    $normalized = @($entries | ForEach-Object { $_.TrimEnd('\') })

    if ($Action -eq 'add') {
        if ($normalized -icontains $binDir) {
            Write-Output "already registered: $binDir"
            return
        }
        if ($Front) {
            $updated = @($binDir) + $entries
        }
        else {
            $updated = $entries + @($binDir)
        }
        $key.SetValue('Path', ($updated -join ';'), $kind)
        Set-Content -LiteralPath $marker -Value $binDir -Encoding UTF8
        $where = 'last'
        if ($Front) { $where = 'first' }
        Write-Output "registered: $binDir"
        Write-Output "added $where to the user Path; new terminals see it immediately."
    }
    else {
        $targets = @($binDir)
        if (Test-Path -LiteralPath $marker) {
            $targets = @((Get-Content -LiteralPath $marker -Raw).Trim()) + $targets
        }
        $normalizedTargets = @($targets | ForEach-Object { $_.TrimEnd('\') })
        $kept = for ($i = 0; $i -lt $entries.Count; $i++) {
            if ($normalizedTargets -inotcontains $normalized[$i]) {
                $entries[$i]
            }
        }
        if (@($kept).Count -eq $entries.Count) {
            Write-Output "was not registered: $binDir"
        }
        else {
            if (@($kept).Count -eq 0) {
                $key.DeleteValue('Path', $false)
            }
            else {
                $key.SetValue('Path', (@($kept) -join ';'), $kind)
            }
            Write-Output "unregistered: $binDir"
            Write-Output "removed from the user Path; new terminals see it immediately."
        }
        if (Test-Path -LiteralPath $marker) {
            Remove-Item -LiteralPath $marker -Force
        }
    }
}
finally {
    $key.Close()
}

# Tell running programs (Explorer above all) that the environment changed.
if (-not ('Win32.NativeMethods' -as [type])) {
    Add-Type -Namespace Win32 -Name NativeMethods -MemberDefinition @"
[DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);
"@
}
$result = [UIntPtr]::Zero
[Win32.NativeMethods]::SendMessageTimeout([IntPtr]0xffff, 0x001A, [UIntPtr]::Zero,
    'Environment', 2, 5000, [ref]$result) | Out-Null
