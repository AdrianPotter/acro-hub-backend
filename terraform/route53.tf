# ── Route 53 Hosted Zone ──────────────────────────────────────────────────────
# Using existing hosted zone created by domain registrar

data "aws_route53_zone" "acro_hub" {
  zone_id = "Z04501911GNFDYM9PBX6Y"
}

# ── ACM Certificate for api.acrohub.org ─────────────────────────────────────
# Must be in us-east-1 for edge-optimised API Gateway; use regional for REGIONAL endpoints.
# This project uses REGIONAL API Gateway, so the certificate can be in the same region.

resource "aws_acm_certificate" "api" {
  domain_name       = "api.${var.domain_name}"
  validation_method = "DNS"

  subject_alternative_names = [
    "api.${var.domain_name}",
  ]

  lifecycle {
    create_before_destroy = true
  }
}

# ── DNS validation records ────────────────────────────────────────────────────

resource "aws_route53_record" "acm_validation" {
  for_each = {
    for dvo in aws_acm_certificate.api.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  zone_id = data.aws_route53_zone.acro_hub.zone_id
  name    = each.value.name
  type    = each.value.type
  ttl     = 60
  records = [each.value.record]
}

# ── Certificate Validation ────────────────────────────────────────────────────

resource "aws_acm_certificate_validation" "api" {
  certificate_arn         = aws_acm_certificate.api.arn
  validation_record_fqdns = [for r in aws_route53_record.acm_validation : r.fqdn]
}

# ── A record pointing api.acrohub.org → API Gateway ───────────────────────

resource "aws_route53_record" "api" {
  zone_id = data.aws_route53_zone.acro_hub.zone_id
  name    = "api.${var.domain_name}"
  type    = "A"

  alias {
    name                   = aws_api_gateway_domain_name.acro_hub.regional_domain_name
    zone_id                = aws_api_gateway_domain_name.acro_hub.regional_zone_id
    evaluate_target_health = false
  }
}
