<#
.SYNOPSIS
  Capture the AWS console screenshots, save them, upload them to S3, and
  commit them to the repo.

.DESCRIPTION
  One command for the last manual step in the project.

    .\scripts\capture-evidence.ps1

  What it does:
    1. Installs the Playwright package if it is missing (it drives your
       installed Chrome, so no browser download).
    2. Opens the AWS console and screenshots the pages the rubric asks for.
       The FIRST run shows a Chrome window and waits for you to sign in;
       the session is saved, so every later run is fully automatic.
    3. Saves the PNGs into evidence\run-NN\screenshots\ (permanent, in the
       repo).
    4. Uploads them to S3 alongside the evaluation results.
    5. Commits and pushes them.

  These are real console screenshots. Nothing renders a console-lookalike
  page from API data - a fabricated image presented as a console screenshot
  would be a falsified record.

.PARAMETER Federated
  Sign in without any manual step, using sts:GetFederationToken. Needs an
  IAM user: root credentials cannot call GetFederationToken. Add
  -CreateUser to have the script make one.

.PARAMETER CreateUser
  With -Federated, create the IAM user (ReadOnlyAccess) used for federated
  console sign-in if it does not already exist.

.PARAMETER NoUpload
  Skip the S3 upload.

.PARAMETER NoCommit
  Skip the git commit and push.

.EXAMPLE
  .\scripts\capture-evidence.ps1
  Sign in once in the browser window, then everything else is automatic.

.EXAMPLE
  .\scripts\capture-evidence.ps1 -Federated -CreateUser
  Fully headless, no manual sign-in, ever.
#>

[CmdletBinding()]
param(
    [string]$Region   = "us-east-1",
    [string]$Bucket   = "",
    [string]$RunDir   = "",
    [string]$IamUser  = "evidence-capture",
    [switch]$Federated,
    [switch]$CreateUser,
    [switch]$Headless,
    [switch]$NoUpload,
    [switch]$NoCommit
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

function Step($m) { Write-Host "`n=== $m ===" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "  [ok] $m"   -ForegroundColor Green }
function Warn($m) { Write-Host "  [!]  $m"   -ForegroundColor Yellow }
function Die($m)  { Write-Host "`n[x] $m"    -ForegroundColor Red; exit 1 }

# ------------------------------------------------------------------ .env ----
# Load credentials from the git-ignored .env so the secret never has to be
# pasted into a terminal (where it lands in PSReadLine history).
#
# EVIDENCE_AWS_* is mapped into AWS_* for this process only. They are kept
# under a separate name in .env because the evidence-capture user is
# read-only: putting a read-only key in the generic AWS_ACCESS_KEY_ID slot
# would make run-all.sh fail with a confusing permissions error.
function Import-DotEnv {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return @{} }
    $vars = @{}
    foreach ($line in Get-Content $Path) {
        if ($line -match '^\s*#') { continue }
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $k = $matches[1]; $v = $matches[2].Trim().Trim('"').Trim("'")
            if ($v) { $vars[$k] = $v }
        }
    }
    return $vars
}

Step "Credentials"

$envFile = Join-Path $repo ".env"
$dotenv  = Import-DotEnv $envFile

if ($dotenv.Count -gt 0) { Ok ".env loaded ($($dotenv.Count) values)" }
else { Warn "no .env found at $envFile" }

if (-not $env:AWS_ACCESS_KEY_ID -and $dotenv.ContainsKey("EVIDENCE_AWS_ACCESS_KEY_ID")) {
    $env:AWS_ACCESS_KEY_ID     = $dotenv["EVIDENCE_AWS_ACCESS_KEY_ID"]
    $env:AWS_SECRET_ACCESS_KEY = $dotenv["EVIDENCE_AWS_SECRET_ACCESS_KEY"]
    $env:AWS_SESSION_TOKEN     = $null
    $masked = $env:AWS_ACCESS_KEY_ID.Substring(0, 8) + "..." +
              $env:AWS_ACCESS_KEY_ID.Substring($env:AWS_ACCESS_KEY_ID.Length - 4)
    Ok "using EVIDENCE_AWS_* from .env ($masked)"
    # These are read-only credentials, so federated sign-in is the only mode
    # that can work with them.
    if (-not $Federated) {
        Write-Host "  (they are read-only, so -Federated is implied)" -ForegroundColor DarkGray
        $Federated = $true
    }
} elseif ($env:AWS_ACCESS_KEY_ID) {
    Ok "using AWS_ACCESS_KEY_ID already set in this shell"
}

if ($dotenv.ContainsKey("EVIDENCE_AWS_REGION") -and -not $PSBoundParameters.ContainsKey("Region")) {
    $Region = $dotenv["EVIDENCE_AWS_REGION"]
}
if ($dotenv.ContainsKey("EVIDENCE_IAM_USER") -and -not $PSBoundParameters.ContainsKey("IamUser")) {
    $IamUser = $dotenv["EVIDENCE_IAM_USER"]
}
Ok "region $Region"

# ----------------------------------------------------------- prerequisites --
Step "Prerequisites"

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { Die "python not found on PATH." }
Ok "python: $python"

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    Warn "aws CLI not found - S3 upload will be skipped."
    $NoUpload = $true
} else {
    Ok "aws CLI present"
}

& $python -c "import playwright" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  installing playwright..."
    & $python -m pip install --quiet playwright
    if ($LASTEXITCODE -ne 0) { Die "Could not install playwright." }
}
Ok "playwright ready"

# ------------------------------------------------------------- run folder ---
Step "Run folder"

if (-not $RunDir) {
    $n = 1
    while (Test-Path (Join-Path $repo ("evidence\run-{0:d2}" -f $n))) { $n++ }
    # Reuse the newest existing run rather than making an empty new one.
    if ($n -gt 1) { $n-- }
    $RunDir = Join-Path $repo ("evidence\run-{0:d2}" -f $n)
}
$shots = Join-Path $RunDir "screenshots"
New-Item -ItemType Directory -Force -Path $shots | Out-Null
Ok $shots

# --------------------------------------------------------------- sign-in ----
$signinUrl = $null

if ($Federated) {
    Step "Federated sign-in URL"

    $caller = (aws sts get-caller-identity --output json | ConvertFrom-Json)
    if ($caller.Arn -match ":root$") {
        Warn "You are signed in as root. Root cannot call GetFederationToken."
        if (-not $CreateUser) {
            Die "Re-run with -CreateUser to create the '$IamUser' IAM user, or drop -Federated and sign in once in the browser."
        }
    }

    if ($CreateUser) {
        aws iam get-user --user-name $IamUser 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  creating IAM user $IamUser ..."
            aws iam create-user --user-name $IamUser | Out-Null
            aws iam attach-user-policy --user-name $IamUser `
                --policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess | Out-Null
            Ok "created $IamUser with ReadOnlyAccess"
            Write-Host "  waiting 10s for IAM to propagate..."
            Start-Sleep -Seconds 10
        } else {
            Ok "$IamUser already exists"
        }

        $keyFile = Join-Path $repo ".evidence-capture-key.json"
        if (-not (Test-Path $keyFile)) {
            $key = aws iam create-access-key --user-name $IamUser --output json | ConvertFrom-Json
            $key | ConvertTo-Json | Set-Content -Path $keyFile -Encoding utf8
            Ok "access key created (saved to .evidence-capture-key.json, git-ignored)"
            Start-Sleep -Seconds 10
        } else {
            $key = Get-Content $keyFile -Raw | ConvertFrom-Json
            Ok "reusing the stored access key"
        }
        $env:AWS_ACCESS_KEY_ID     = $key.AccessKey.AccessKeyId
        $env:AWS_SECRET_ACCESS_KEY = $key.AccessKey.SecretAccessKey
        $env:AWS_SESSION_TOKEN     = $null
    }

    $policy = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"*","Resource":"*"}]}'
    $fed = aws sts get-federation-token --name evidence-capture `
        --policy $policy --duration-seconds 3600 --output json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { Die "GetFederationToken failed." }

    $sess = @{
        sessionId  = $fed.Credentials.AccessKeyId
        sessionKey = $fed.Credentials.SecretAccessKey
        sessionToken = $fed.Credentials.SessionToken
    } | ConvertTo-Json -Compress

    $enc = [System.Uri]::EscapeDataString($sess)
    $tokenResp = Invoke-RestMethod -Uri "https://signin.aws.amazon.com/federation?Action=getSigninToken&Session=$enc"
    $dest = [System.Uri]::EscapeDataString("https://$Region.console.aws.amazon.com/console/home?region=$Region")
    $signinUrl = "https://signin.aws.amazon.com/federation?Action=login&Issuer=evidence-capture&Destination=$dest&SigninToken=$($tokenResp.SigninToken)"
    Ok "sign-in URL minted (valid ~1 hour)"
}

# --------------------------------------------------------------- capture ----
Step "Capturing console screenshots"

$capArgs = @("scripts/capture_console.py", "--out", $shots, "--region", $Region)
if ($signinUrl) { $capArgs += @("--signin-url", $signinUrl) }
if ($Headless)  { $capArgs += "--headless" }

if (-not $signinUrl -and -not $Headless) {
    Write-Host "  The first run opens a Chrome window - sign in to AWS there." -ForegroundColor Yellow
    Write-Host "  After that the session is remembered and runs are automatic." -ForegroundColor Yellow
}

& $python @capArgs
$capExit = $LASTEXITCODE

$pngs = @(Get-ChildItem -Path $shots -Filter *.png -ErrorAction SilentlyContinue)
if ($pngs.Count -eq 0) { Die "No screenshots were captured." }
Ok "$($pngs.Count) screenshot(s) in $shots"
if ($capExit -ne 0) { Warn "some pages failed - see the output above" }

# ------------------------------------------------------------------ S3 ------
if (-not $NoUpload) {
    Step "Uploading to S3"

    if (-not $Bucket) {
        $Bucket = aws cloudformation describe-stacks `
            --stack-name bug-report-testing-stack `
            --query "Stacks[0].Outputs[?OutputKey=='EvalDatasetBucketName'].OutputValue" `
            --output text --region $Region 2>$null
    }

    if (-not $Bucket -or $Bucket -eq "None") {
        Warn "Could not resolve the evaluation bucket - skipping upload."
    } else {
        $prefix = "evidence/screenshots/"
        aws s3 cp $shots "s3://$Bucket/$prefix" --recursive `
            --exclude "*" --include "*.png" --include "README.md" `
            --region $Region | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Ok "uploaded to s3://$Bucket/$prefix"
            aws s3 ls "s3://$Bucket/$prefix" --region $Region
        } else {
            Warn "upload failed"
        }
    }
}

# ------------------------------------------------------------------ git -----
if (-not $NoCommit) {
    Step "Committing"

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Warn "git not found - skipping commit."
    } else {
        git add -A -- $RunDir
        git diff --cached --quiet
        if ($LASTEXITCODE -eq 0) {
            Warn "nothing new to commit"
        } else {
            $rel = Resolve-Path -Relative $RunDir
            git commit -q -m "Add console screenshots to $rel

Captured with scripts/capture-evidence.ps1, which drives a real Chrome
session against the AWS console. $($pngs.Count) page(s)."
            Ok "committed"
            git push -q origin HEAD
            if ($LASTEXITCODE -eq 0) { Ok "pushed" } else { Warn "push failed" }
        }
    }
}

Step "Done"
Write-Host "  Screenshots : $shots"
$pngs | ForEach-Object { Write-Host ("    " + $_.Name + "  " + [math]::Round($_.Length/1KB) + " KB") }
Write-Host "`n  Re-run any time - the browser session is remembered." -ForegroundColor Green
