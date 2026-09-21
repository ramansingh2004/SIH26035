"""Transport-neutral application errors."""


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def denied() -> AppError:
    return AppError(403, "PERMISSION_DENIED", "Permission or scope denied")


def missing() -> AppError:
    return AppError(404, "RESOURCE_NOT_FOUND", "Resource not found")
