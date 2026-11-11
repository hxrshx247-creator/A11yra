from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status,
            content={"error": {"code": self.code, "message": self.message}},
        )
