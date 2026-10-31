param(
    [Parameter(Mandatory = $true)][string]$Bin,
    [Parameter(Mandatory = $true)][string]$RedistRoot
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $RedistRoot)) {
    throw "ARM64 VC++ redistributable directory not found: $RedistRoot"
}

$redist = @(Get-ChildItem -LiteralPath $RedistRoot -Recurse -Filter *.dll -File)

function Get-PeFiles([string]$Directory) {
    Get-ChildItem -LiteralPath $Directory -File |
        Where-Object { $_.Extension -eq '.exe' -or $_.Extension -eq '.dll' }
}

function Get-Imports([string]$Path) {
    $names = New-Object System.Collections.Generic.List[string]
    $headerOk = $false
    $output = & dumpbin.exe /headers /dependents $Path 2>&1
    foreach ($line in $output) {
        $text = "$line"
        if ($text -match 'machine \(ARM64\)') {
            $headerOk = $true
        }
        if ($text -match '^\s+(\S+\.dll)\s*$') {
            $names.Add($Matches[1])
        }
    }
    if (-not $headerOk) {
        throw "NON-ARM64: $Path"
    }
    return $names
}

$copied = New-Object System.Collections.Generic.List[string]
$guard = 0
$count = 0
do {
    $guard++
    if ($guard -gt 5) {
        throw "VC++ runtime copy did not settle."
    }
    $missing = New-Object 'System.Collections.Generic.HashSet[string]'
    $count = 0
    foreach ($pe in (Get-PeFiles $Bin)) {
        $count++
        if (($count % 100) -eq 0) {
            Write-Output "scanned $count"
        }
        foreach ($name in (Get-Imports $pe.FullName)) {
            if (-not (Test-Path -LiteralPath (Join-Path $Bin $name))) {
                [void]$missing.Add($name)
            }
        }
    }
    $added = 0
    foreach ($name in $missing) {
        $hit = $redist | Where-Object { $_.Name -ieq $name } | Select-Object -First 1
        if ($hit) {
            Copy-Item -LiteralPath $hit.FullName -Destination (Join-Path $Bin $name)
            $copied.Add($name)
            $added++
            continue
        }
        if ($name -like 'api-ms-win-*' -or $name -like 'ext-ms-win-*') {
            continue
        }
        $sys = Join-Path $env:SystemRoot "System32\$name"
        $downlevel = Join-Path $env:SystemRoot "System32\downlevel\$name"
        if ((Test-Path -LiteralPath $sys) -or (Test-Path -LiteralPath $downlevel)) {
            continue
        }
        throw "Required DLL is not in the bin directory, the ARM64 VC++ redist, or Windows: $name"
    }
} while ($added -gt 0)

Write-Output "SCANNED=$count NON_ARM64=0"
if ($copied.Count -eq 0) {
    Write-Output "VC++ runtime: already present"
}
else {
    Write-Output ("VC++ runtime copied: " + ($copied -join ', '))
}
