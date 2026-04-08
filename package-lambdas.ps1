# Package all Lambda functions for deployment
# This script creates proper ZIP files that AWS Lambda can use

Write-Host "Packaging Lambda functions for AWS deployment..." -ForegroundColor Cyan
Write-Host ""

$services = @("auth", "moves", "videos", "events", "users")
$baseDir = $PSScriptRoot

foreach ($svc in $services) {
    Write-Host "Packaging $svc..." -ForegroundColor Yellow

    $svcDir = Join-Path $baseDir "lambdas\$svc"
    $packageDir = Join-Path $svcDir "package"
    $zipFile = Join-Path $svcDir "function.zip"

    # Clean up previous package and zip
    if (Test-Path $packageDir) {
        Remove-Item -Recurse -Force $packageDir
    }
    if (Test-Path $zipFile) {
        Remove-Item -Force $zipFile
    }

    # Create package directory
    New-Item -ItemType Directory -Path $packageDir | Out-Null

    # Install dependencies
    Write-Host "  Installing dependencies..." -ForegroundColor Gray
    & pip install -r (Join-Path $svcDir "requirements.txt") -t $packageDir --quiet

    # Copy handler
    Copy-Item (Join-Path $svcDir "handler.py") -Destination $packageDir

    # Create ZIP file
    Write-Host "  Creating ZIP archive..." -ForegroundColor Gray
    Push-Location $packageDir

    # Use Compress-Archive (native PowerShell)
    Get-ChildItem -File -Recurse | Compress-Archive -DestinationPath $zipFile -Force

    Pop-Location

    # Clean up package directory
    Remove-Item -Recurse -Force $packageDir

    # Verify ZIP was created
    if (Test-Path $zipFile) {
        $size = [math]::Round((Get-Item $zipFile).Length / 1MB, 2)
        Write-Host "  Created function.zip ($size MB)" -ForegroundColor Green
    } else {
        Write-Host "  Failed to create function.zip" -ForegroundColor Red
    }

    Write-Host ""
}

Write-Host "All Lambda functions packaged successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. cd terraform" -ForegroundColor White
Write-Host "  2. terraform init" -ForegroundColor White
Write-Host "  3. terraform plan -var=`"environment=prod`"" -ForegroundColor White
Write-Host "  4. terraform apply -var=`"environment=prod`"" -ForegroundColor White

