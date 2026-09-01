# FortiGuard WebFilter Bulk Lookup

Bulk-check domains and URLs against the public FortiGuard Web Filter Lookup and export the detected categories to CSV.

This repository is a maintained fork of [SystemJargon/fortiguard-webfilter](https://github.com/SystemJargon/fortiguard-webfilter). The original project and historical scripts are licensed under GPL-3.0.

> [!IMPORTANT]
> This is an unofficial community tool. It is not a Fortinet API, is not affiliated with Fortinet, and depends on the behavior and HTML of FortiGuard's public lookup website.

## What problem this solves

FortiGuard's public Web Filter Lookup is designed around individual lookups. This tool automates a controlled sequence of lookups from a text file and produces a repeatable CSV result set for firewall-policy review, URL inventory work, and troubleshooting.

The maintained implementation uses Python with `curl_cffi` browser impersonation because simple HTTP clients can be rejected by the FortiGuard front end. The parser supports several observed FortiGuard result layouts to reduce breakage when page markup changes.

## Supported path

- **Python 3.10+** - primary lookup engine: `webfilter.py`
- **PowerShell** - Windows-friendly wrapper: `FortiWebFilter-BulkScan.ps1`
- **Input** - one URL or domain per line
- **Output** - CSV with `target`, `category`, `status`, and `error`

The `engine_6/` directory is retained from the upstream project for historical reference. It is not part of the supported execution path or CI validation.

## Prerequisites

- Python 3.10 or later
- Internet access to `https://www.fortiguard.com/`
- Python dependencies from `requirements.txt`

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## Quick start

Create a local input file from the safe example:

### Windows PowerShell

```powershell
Copy-Item .\addresses.example.txt .\addresses.txt
.\FortiWebFilter-BulkScan.ps1
```

### Python

```bash
cp addresses.example.txt addresses.txt
python webfilter.py
```

`addresses.txt` is intentionally ignored by Git because real lookup lists may contain customer, internal, or otherwise sensitive URLs.

## Input format

One target per line. Blank lines and lines beginning with `#` are ignored. Duplicate targets are processed once.

```text
# domains
example.com
fortinet.com

# full URLs are also accepted
https://github.com/
```

## Python usage

```text
python webfilter.py [options]

-i, --input PATH        Input file. Default: addresses.txt
-o, --output PATH       Output CSV. Default: categories-YYYYMMDD-HHMMSS.csv
--delay SECONDS         Delay between targets. Default: 2
--timeout SECONDS       Per-request timeout. Default: 15
--retries COUNT         Retries for transient failures. Default: 2
--impersonate PROFILE   curl_cffi browser profile. Default: chrome
```

Example:

```bash
python webfilter.py --input targets.txt --output results.csv --delay 3
```

## PowerShell usage

The PowerShell script resolves `python`, `python3`, or the Windows `py -3` launcher and forwards the supported options to the Python engine.

```powershell
.\FortiWebFilter-BulkScan.ps1 `
    -InputFile .\targets.txt `
    -OutputFile .\results.csv `
    -Delay 3 `
    -Timeout 20 `
    -Retries 2
```

## Output

Successful and failed lookups are written to the same CSV so a partial run remains auditable.

```csv
target,category,status,error
example.com,Information Technology,ok,
invalid.example,,error,category not found in response
```

Exit codes:

- `0` - all processed lookups succeeded
- `1` - one or more lookups failed, or a run was interrupted after partial processing
- `2` - local usage or dependency error

## Validation

CI runs on pull requests and pushes to `main` and performs:

- dependency installation on Python 3.10
- Python byte-code compilation
- parser and input-processing tests with `pytest`
- PowerShell AST syntax parsing

CI deliberately does **not** run live bulk lookups against FortiGuard. Live checks would create unnecessary external traffic and would make repository validation depend on a third-party website.

Run the local deterministic checks:

```bash
python -m pip install -r requirements-dev.txt
python -m compileall -q webfilter.py tests
python -m pytest -q
```

## Operational and security considerations

- Treat lookup lists and output CSV files as potentially sensitive operational data.
- Do not commit customer URLs, internal hostnames, credentials, tokens, or raw production evidence.
- Keep a non-zero delay between requests. This project defaults to 2 seconds.
- A category returned by the public website is not proof of the exact result a specific FortiGate will enforce. Firmware, FortiGuard database state, overrides, profile configuration, and policy order can affect production behavior.
- The website is not a stable API contract. A FortiGuard front-end change can require a parser or transport update.
- Respect Fortinet's applicable terms and acceptable-use requirements.

For on-box category ID mapping, the authoritative FortiGate command is:

```text
get webfilter categories
```

## Troubleshooting

### `Missing dependency: curl_cffi`

```bash
python -m pip install -r requirements.txt
```

### HTTP 403 or parsing failures

First update to the latest repository revision and verify the pinned dependencies. If FortiGuard changed its front-end protection or result markup, open a sanitized bug report. Do not post private lookup targets.

### Category differs from FortiGate behavior

Validate the FortiGate's FortiOS version, FortiGuard connectivity, local/web-rating overrides, Web Filter profile, and policy path. This tool reports the public lookup result only.

## Upstream and maintenance

- Upstream: `SystemJargon/fortiguard-webfilter`
- This fork: maintained as a safer, testable bulk-lookup workflow
- Maintenance state: active

Changes in this fork preserve upstream attribution and the GPL-3.0 license.

## License

GNU General Public License v3.0. See `LICENSE.md`.
