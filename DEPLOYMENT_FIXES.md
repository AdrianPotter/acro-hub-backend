# Deployment Issues - Fixed

## Summary of Issues and Fixes

### 1. ✅ Lambda Function ZIP Error - FIXED

**Error:**
```
Error: creating Lambda Function (acro-hub-events-prod): operation error Lambda: CreateFunction, 
https response error StatusCode: 400, RequestID: 9c706638-58b1-4dcc-a0a8-1b8211a9f311, 
InvalidParameterValueException: Could not unzip uploaded file. Please check your file, then try to upload again.
```

**Root Cause:**
The Windows PowerShell packaging command in README.md was using `tar -czf` which creates a **gzipped tar archive** (`.tar.gz`), not a ZIP file. Lambda functions require actual ZIP files.

**Fix Applied:**
Updated the README.md to use PowerShell's native `Compress-Archive` cmdlet:

```powershell
foreach ($svc in @("auth", "moves", "videos", "events")) {
  cd lambdas/$svc
  pip install -r requirements.txt -t package/
  Copy-Item handler.py package/
  Compress-Archive -Path package/* -DestinationPath function.zip -Force
  Remove-Item -Recurse -Force package
  cd ../..
}
```

**Action Required:**
1. Delete all existing `function.zip` files:
   ```powershell
   Remove-Item C:\Users\adria\Documents\GitHub\acro-hub-backend\lambdas\*\function.zip
   ```

2. Re-package all Lambda functions using the corrected command above

3. Run `terraform apply` again

---

### 2. ✅ API Gateway Missing Format Argument - ALREADY FIXED

**Error:**
```
Error: Missing required argument
  on api_gateway.tf line 877, in resource "aws_api_gateway_stage" "acro_hub":
 877:   access_log_settings {
The argument "format" is required, but no definition was found.
```

**Status:**
This has already been fixed in `api_gateway.tf` at line 879. The `format` attribute is present with a comprehensive log format.

No action required.

---

### 3. ✅ Route53 Zone References - FIXED

**Issue:**
The Route53 configuration was using a data source (`data "aws_route53_zone"`) to reference the existing hosted zone with ID `Z04501911GNFDYM9PBX6Y`, but some references were still using the old resource syntax `aws_route53_zone.acro_hub` instead of `data.aws_route53_zone.acro_hub`.

**Fix Applied:**
Updated all references in:
- `terraform/route53.tf` (2 locations)
- `terraform/outputs.tf` (1 location)

All zone references now correctly point to the data source.

---

### 4. ℹ️ S3 Bucket Creation Error - TRANSIENT

**Error:**
```
aws: [ERROR]: An error occurred (OperationAborted) when calling the CreateBucket operation: 
A conflicting conditional operation is currently in progress against this resource. Please try again.
```

**Root Cause:**
This is a transient AWS error that occurs when:
- A bucket was recently deleted and the deletion is still propagating
- Multiple terraform operations are running simultaneously
- AWS S3 has an internal lock on the bucket name

**Solutions:**
1. **Wait 5-10 minutes** and try again
2. If the bucket exists but terraform doesn't know about it, import it:
   ```powershell
   cd terraform
   terraform import aws_s3_bucket.videos acro-hub-videos-prod
   ```
3. If you need to destroy and recreate, ensure you wait after deletion:
   ```powershell
   terraform destroy -target=aws_s3_bucket.videos
   # Wait 5 minutes
   terraform apply
   ```

---

### 5. ℹ️ Compress-Archive Performance

**Question:** Why is the Compress-Archive command taking so long?

**Explanation:**
`Compress-Archive` can be slow when compressing many small files (like Python dependencies). This is normal behavior for PowerShell on Windows.

**Performance Tips:**

1. **Use Python's zipfile module** (faster for Python packages):
   ```powershell
   foreach ($svc in @("auth", "moves", "videos", "events")) {
     cd lambdas/$svc
     pip install -r requirements.txt -t package/
     Copy-Item handler.py package/
     python -m zipfile -c function.zip package/*
     Remove-Item -Recurse -Force package
     cd ../..
   }
   ```

2. **Use 7-Zip** if installed (fastest):
   ```powershell
   foreach ($svc in @("auth", "moves", "videos", "events")) {
     cd lambdas/$svc
     pip install -r requirements.txt -t package/
     Copy-Item handler.py package/
     7z a -tzip function.zip .\package\*
     Remove-Item -Recurse -Force package
     cd ../..
   }
   ```

3. **Be patient** - First time packaging can take 1-3 minutes per Lambda due to dependency downloads. Subsequent runs are faster.

---

## Deployment Checklist

Before deploying, ensure:

- [ ] All Lambda functions are packaged with proper ZIP files (not tar.gz)
- [ ] Route53 zone ID `Z04501911GNFDYM9PBX6Y` is already created at your registrar
- [ ] AWS credentials are configured
- [ ] Terraform state bucket exists (`acro-hub-terraform-state`)
- [ ] Environment variable is set correctly (`dev` or `prod`)

**Deploy Command:**
```powershell
cd terraform
terraform init
terraform plan -var="environment=prod"
terraform apply -var="environment=prod"
```

---

## Files Modified

1. ✅ `README.md` - Updated Windows packaging command
2. ✅ `terraform/route53.tf` - Fixed data source references (2 locations)
3. ✅ `terraform/outputs.tf` - Fixed data source reference (1 location)
4. ✅ `terraform/api_gateway.tf` - Already had correct format attribute

All fixes have been applied and validated.

