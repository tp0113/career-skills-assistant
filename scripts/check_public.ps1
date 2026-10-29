<#
.SYNOPSIS
  Fails if anything that should not be public is tracked or in the git history.

.DESCRIPTION
  Generic checks live here: key-shaped strings, a tracked .env, absolute home paths,
  and single-author history. Project-specific private terms (names, words, file names)
  are read from a terms file kept OUTSIDE the repo, so this script never publishes them.

  Terms file format, one per line ("#" starts a comment):
    word:<text>    whole-word, case-insensitive
    exact:<text>   whole-word, case-sensitive
    regex:<re>     .NET regex, case-insensitive
    file:<name>    a file name that must never be tracked

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/check_public.ps1 -TermsFile <path>
  powershell -ExecutionPolicy Bypass -File scripts/check_public.ps1 -GenericOnly
#>
param(
    [string]$TermsFile = $env:PUBLIC_SCAN_TERMS,
    [string]$ExpectedAuthor = "Tilak Patel <133725308+tp0113@users.noreply.github.com>",
    [switch]$GenericOnly
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$self = "scripts/check_public.ps1"
$problems = New-Object System.Collections.Generic.List[string]

# --- Build the rule list -------------------------------------------------------------
# Each rule: label, .NET regex, case-sensitive?
$rules = New-Object System.Collections.Generic.List[object]
$rules.Add(@("Anthropic-style key", 'sk-ant-[A-Za-z0-9_\-]{20,}', $true))
$rules.Add(@("OpenAI-style key", '\bsk-[A-Za-z0-9]{32,}', $true))
$rules.Add(@("GitHub token", '\bgh[pousr]_[A-Za-z0-9]{30,}', $true))
$rules.Add(@("AWS access key", '\bAKIA[0-9A-Z]{16}\b', $true))
$rules.Add(@("API key with a value", '(API_KEY|SECRET|TOKEN)\s*=\s*[^\s#]+', $false))
$rules.Add(@("absolute home path", '[A-Za-z]:\\Users\\|/Users/[a-z]|/home/[a-z]', $false))

$bannedFiles = @(".env")
if (-not $GenericOnly) {
    if (-not $TermsFile -or -not (Test-Path $TermsFile)) {
        Write-Host "FAIL: no private terms file. Pass -TermsFile <path> (or set PUBLIC_SCAN_TERMS)," -ForegroundColor Red
        Write-Host "      or run with -GenericOnly to check only keys, paths and authorship." -ForegroundColor Red
        exit 2
    }
    foreach ($line in Get-Content $TermsFile) {
        $t = $line.Trim()
        if ($t -eq "" -or $t.StartsWith("#")) { continue }
        $kind, $value = $t.Split(":", 2)
        switch ($kind) {
            "word"  { $rules.Add(@("private word '$value'", "\b$([regex]::Escape($value))\b", $false)) }
            "exact" { $rules.Add(@("private word '$value'", "\b$([regex]::Escape($value))\b", $true)) }
            "regex" { $rules.Add(@("private pattern", $value, $false)) }
            "file"  { $bannedFiles += $value }
            default { Write-Host "WARN: unknown line in terms file: $t" -ForegroundColor Yellow }
        }
    }
}

function Test-Text([string]$text, [string]$where) {
    foreach ($r in $rules) {
        $opts = if ($r[2]) { "None" } else { "IgnoreCase" }
        $m = [regex]::Match($text, $r[1], $opts)
        if ($m.Success) { $problems.Add("$where : $($r[0])") }
    }
}

# --- 1. Tracked file names -----------------------------------------------------------
$tracked = @(git ls-files)
foreach ($f in $tracked) {
    $leaf = Split-Path $f -Leaf
    if ($bannedFiles -contains $leaf) { $problems.Add("tracked file must not be public: $f") }
}

# --- 2. Tracked file contents --------------------------------------------------------
foreach ($f in $tracked) {
    if ($f -eq $self -or -not (Test-Path $f)) { continue }
    $text = [IO.File]::ReadAllText((Resolve-Path $f))
    if ($text.IndexOf([char]0) -ge 0) { continue }   # skip binary files
    Test-Text $text $f
}

# --- 3. History: every commit's diff, message and author -----------------------------
$commits = @(git rev-list --all)
foreach ($c in $commits) {
    $body = (git show --format="%an <%ae>%n%B" $c -- . ":(exclude)$self") -join "`n"
    Test-Text $body "commit $($c.Substring(0, 8))"
}

# --- 4. Authorship -------------------------------------------------------------------
$authors = @(git log --all --format="%an <%ae>" | Sort-Object -Unique)
foreach ($a in $authors) {
    if ($a -ne $ExpectedAuthor) { $problems.Add("unexpected author in history: $a") }
}
$committers = @(git log --all --format="%cn <%ce>" | Sort-Object -Unique)
foreach ($a in $committers) {
    if ($a -ne $ExpectedAuthor) { $problems.Add("unexpected committer in history: $a") }
}

# --- Report --------------------------------------------------------------------------
$mode = if ($GenericOnly) { "generic checks only" } else { "generic + private terms" }
if ($problems.Count -gt 0) {
    Write-Host "check_public: FAIL ($mode), $($problems.Count) problem(s):" -ForegroundColor Red
    $problems | Sort-Object -Unique | ForEach-Object { Write-Host "  - $_" }
    exit 1
}
Write-Host "check_public: PASS ($mode). $($tracked.Count) tracked files, $($commits.Count) commits scanned." -ForegroundColor Green
exit 0
