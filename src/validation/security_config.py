"""
Security configuration for validation API.

Centralizes security settings for:
- CORS policy
- Rate limiting
- Security headers
- Error handling
"""

from typing import List

from pydantic import BaseModel


class SecuritySettings(BaseModel):
    """Security configuration settings."""

    # CORS Configuration
    cors_allowed_origins: List[str] = [
        "http://localhost:3000",  # React dev server
        "http://localhost:8000",  # Local API server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_allow_headers: List[str] = ["*"]
    cors_max_age: int = 600  # 10 minutes

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60  # 60 requests per minute per IP
    rate_limit_burst: int = 10  # Allow burst of 10 requests

    # Security Headers
    enable_security_headers: bool = True
    x_frame_options: str = "DENY"  # Prevent clickjacking
    x_content_type_options: str = "nosniff"  # Prevent MIME sniffing
    x_xss_protection: str = "1; mode=block"  # XSS protection (legacy browsers)
    referrer_policy: str = "strict-origin-when-cross-origin"
    permissions_policy: str = "geolocation=(), microphone=(), camera=()"

    # Content Security Policy (CSP)
    enable_csp: bool = True
    csp_default_src: List[str] = ["'self'"]
    csp_script_src: List[str] = ["'self'"]
    csp_style_src: List[str] = ["'self'", "'unsafe-inline'"]  # Allow inline styles for frontend
    csp_img_src: List[str] = ["'self'", "data:", "https:"]
    csp_connect_src: List[str] = ["'self'"]
    csp_font_src: List[str] = ["'self'"]
    csp_object_src: List[str] = ["'none'"]
    csp_frame_ancestors: List[str] = ["'none'"]  # Prevent embedding

    # HSTS (HTTP Strict Transport Security)
    enable_hsts: bool = False  # Enable in production with HTTPS
    hsts_max_age: int = 31536000  # 1 year
    hsts_include_subdomains: bool = True
    hsts_preload: bool = False

    # Error Handling
    show_error_details: bool = True  # Set to False in production
    log_error_details: bool = True

    # Audit Logging
    enable_audit_log: bool = True
    audit_log_sensitive_operations: bool = True  # Log C/F grade alerts, manual triggers


# Singleton instance
_security_settings: SecuritySettings | None = None


def get_security_settings() -> SecuritySettings:
    """Get security settings singleton."""
    global _security_settings
    if _security_settings is None:
        _security_settings = SecuritySettings()
    return _security_settings


def get_csp_header() -> str:
    """
    Build Content-Security-Policy header value.

    Returns:
        str: CSP header value
    """
    settings = get_security_settings()

    if not settings.enable_csp:
        return ""

    directives = [
        f"default-src {' '.join(settings.csp_default_src)}",
        f"script-src {' '.join(settings.csp_script_src)}",
        f"style-src {' '.join(settings.csp_style_src)}",
        f"img-src {' '.join(settings.csp_img_src)}",
        f"connect-src {' '.join(settings.csp_connect_src)}",
        f"font-src {' '.join(settings.csp_font_src)}",
        f"object-src {' '.join(settings.csp_object_src)}",
        f"frame-ancestors {' '.join(settings.csp_frame_ancestors)}",
    ]

    return "; ".join(directives)


def get_hsts_header() -> str:
    """
    Build HTTP Strict Transport Security (HSTS) header value.

    Returns:
        str: HSTS header value
    """
    settings = get_security_settings()

    if not settings.enable_hsts:
        return ""

    parts = [f"max-age={settings.hsts_max_age}"]

    if settings.hsts_include_subdomains:
        parts.append("includeSubDomains")

    if settings.hsts_preload:
        parts.append("preload")

    return "; ".join(parts)
