<#
.SYNOPSIS
Runs the maintained FortiGuard bulk lookup engine from PowerShell.

.DESCRIPTION
This script is a Windows-friendly wrapper around webfilter.py. The Python
implementation is the supported lookup engine because FortiGuard's public
lookup page may reject simple HTTP clients and can change its HTML layout.

This project is an unofficial community tool and is not affiliated with or
supported by Fortinet.

.PARAMETER InputFile
Text file containing one URL or domain per line.

.PARAMETER OutputFile
Optional CSV output path. If omitted, the Python engine creates a timestamped
categories-*.csv file.

.PARAMETER Delay
Seconds to wait between targets.

.PARAMETER Timeout
Per-request timeout in seconds.

.PARAMETER Retries
Number of retries for transient failures.

.EXAMPLE
.\FortiWebFilter-BulkScan.ps1 -InputFile .\addresses.txt

.EXAMPLE
.\FortiWebFilter-BulkScan.ps1 -InputFile .\targets.txt -OutputFile .\results.csv -Delay 3

.NOTES
Original project: SystemJargon/fortiguard-webfilter
License: GPL-3.0
#>

[CmdletBinding()]
param(
    [Parameter()]
    [string]$InputFile = (Join-Path $PSScriptRoot 'addresses.txt'),

    [Parameter()]
    [string]$OutputFile,

    [Parameter()]
    [ValidateRange(0, 60)]
    [double]$Delay = 2,

    [Parameter()]
    [ValidateRange(1, 300)]
    [double]$Timeout = 15,

    [Parameter()]
    [ValidateRange(0, 10)]
    [int]$Retries = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$PythonScript = Join-Path $PSScriptRoot 'webfilter.py'
if (-not (Test-Path -LiteralPath $PythonScript -PathType Leaf)) {
    throw "Python engine not found: $PythonScript"
}

function Get-PythonCommand {
    $candidates = @(
        @{ Command = 'python'; Prefix = @() },
        @{ Command = 'python3'; Prefix = @() },
        @{ Command = 'py'; Prefix = @('-3') }
    )

    foreach ($candidate in $candidates) {
        $resolved = Get-Command $candidate.Command -ErrorAction SilentlyContinue
        if ($null -ne $resolved) {
            return [PSCustomObject]@{
                Path   = $resolved.Source
                Prefix = $candidate.Prefix
            }
        }
    }

    throw "Python 3 was not found. Install Python 3.10+ and run 'python -m pip install -r requirements.txt'."
}

$python = Get-PythonCommand
$arguments = @()
$arguments += $python.Prefix
$arguments += $PythonScript
$arguments += @('--input', $InputFile)
$arguments += @('--delay', $Delay.ToString([Globalization.CultureInfo]::InvariantCulture))
$arguments += @('--timeout', $Timeout.ToString([Globalization.CultureInfo]::InvariantCulture))
$arguments += @('--retries', $Retries.ToString([Globalization.CultureInfo]::InvariantCulture))

if ($OutputFile) {
    $arguments += @('--output', $OutputFile)
}

& $python.Path @arguments
$exitCode = $LASTEXITCODE
if ($null -eq $exitCode) {
    $exitCode = 1
}

exit $exitCode
