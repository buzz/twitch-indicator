class NotAuthorizedException(Exception):
    """Raised when API returns 401 Unauthorized or no token is available."""
