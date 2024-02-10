class ApiException(Exception):
    """Base class for API related exceptions."""


class NotAuthorizedException(ApiException):
    """Exception raised when the request is not authorized (HTTP 401)."""


class RateLimitExceededException(ApiException):
    """Exception raised when the rate limit is exceeded (HTTP 429)."""
