from fastapi import Request
from fastapi.responses import JSONResponse


class EnterpriseException(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def enterprise_exception_handler(request: Request, exc: EnterpriseException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})
