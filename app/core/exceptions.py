class SalesforceMasterServiceException(Exception):
    """Base exception for all service errors."""
    pass


class SalesforceAuthError(SalesforceMasterServiceException):
    """Raised when authentication to Salesforce fails."""
    def __init__(self, message: str, details: str = None):
        super().__init__(message)
        self.details = details


class SalesforceAPIError(SalesforceMasterServiceException):
    """Raised when a Salesforce API call fails."""
    def __init__(self, message: str, status_code: int = None, details: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class StorageError(SalesforceMasterServiceException):
    """Raised when an object storage (MinIO) operation fails."""
    pass


class JobNotFoundError(SalesforceMasterServiceException):
    """Raised when requested scan_id does not exist."""
    pass


class JobStateConflictError(SalesforceMasterServiceException):
    """Raised when an invalid state transition is requested."""
    pass
