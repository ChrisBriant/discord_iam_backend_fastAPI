#Custom exceptions for use in error handling

class APIRetrievalError(Exception):
    """Exception raised when an API data retrieval fails."""
    def __init__(self, status_code=None, message=None):
        self.status_code = status_code
        self.message = message

        super().__init__(message)