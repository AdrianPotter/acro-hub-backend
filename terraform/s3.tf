# ── S3 Bucket ─────────────────────────────────────────────────────────────────

resource "aws_s3_bucket" "videos" {
  bucket = "${var.app_name}-videos-${var.environment}"

  tags = {
    Name = "${var.app_name}-videos-${var.environment}"
  }
}

# ── Versioning ────────────────────────────────────────────────────────────────

resource "aws_s3_bucket_versioning" "videos" {
  bucket = aws_s3_bucket.videos.id

  versioning_configuration {
    status = "Enabled"
  }
}

# ── Server-Side Encryption ────────────────────────────────────────────────────

resource "aws_s3_bucket_server_side_encryption_configuration" "videos" {
  bucket = aws_s3_bucket.videos.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ── Block Public Access ───────────────────────────────────────────────────────

resource "aws_s3_bucket_public_access_block" "videos" {
  bucket = aws_s3_bucket.videos.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── CORS Configuration ────────────────────────────────────────────────────────

resource "aws_s3_bucket_cors_configuration" "videos" {
  bucket = aws_s3_bucket.videos.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT"]
    allowed_origins = [
      "https://${var.domain_name}",
      "https://www.${var.domain_name}",
    ]
    expose_headers  = ["ETag"]
    max_age_seconds = 3600
  }
}

# ── Lifecycle Rules ───────────────────────────────────────────────────────────

resource "aws_s3_bucket_lifecycle_configuration" "videos" {
  bucket = aws_s3_bucket.videos.id

  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
