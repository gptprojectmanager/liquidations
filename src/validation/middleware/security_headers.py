"""
Security headers middleware for FastAPI.

Adds security-related HTTP headers to all responses.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.validation.security_config import get_csp_header, get_hsts_header, get_security_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to responses.

    Headers added:
    - X-Frame-Options: Prevent clickjacking
    - X-Content-Type-Options: Prevent MIME sniffing
    - X-XSS-Protection: XSS protection for legacy browsers
    - Referrer-Policy: Control referrer information
    - Permissions-Policy: Control browser features
    - Content-Security-Policy: Control resource loading
    - Strict-Transport-Security: Force HTTPS (if enabled)
    """

    async def dispatch(self, request: Request, call_next):
        """Process request and add security headers to response."""
        settings = get_security_settings()

        # Call the next middleware/endpoint
        response: Response = await call_next(request)

        # Add security headers if enabled
        if settings.enable_security_headers:
            # Prevent clickjacking
            response.headers["X-Frame-Options"] = settings.x_frame_options

            # Prevent MIME sniffing
            response.headers["X-Content-Type-Options"] = settings.x_content_type_options

            # XSS protection (legacy browsers)
            response.headers["X-XSS-Protection"] = settings.x_xss_protection

            # Referrer policy
            response.headers["Referrer-Policy"] = settings.referrer_policy

            # Permissions policy
            response.headers["Permissions-Policy"] = settings.permissions_policy

            # Content Security Policy
            if settings.enable_csp:
                csp = get_csp_header()
                if csp:
                    response.headers["Content-Security-Policy"] = csp

            # HTTP Strict Transport Security (only over HTTPS)
            if settings.enable_hsts and request.url.scheme == "https":
                hsts = get_hsts_header()
                if hsts:
                    response.headers["Strict-Transport-Security"] = hsts

        return response
