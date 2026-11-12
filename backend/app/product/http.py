import asyncio
import json
from time import perf_counter

from starlette.datastructures import Headers, MutableHeaders

from app.core.config import MAX_MULTIPART_BYTES
from app.core.errors import ApiError
from app.product.db import new_id

CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
UPLOAD_ROUTES = {"/api/documents", "/api/public/v1/audit"}
PUBLIC_AUDIT_ROUTE = "/api/public/v1/audit"


def audit_timeout_error() -> ApiError:
    return ApiError(408, "request_timeout", "The audit took too long. Try a smaller document.")


class ProductHTTP:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        state = scope["app"].state
        path = scope["path"]
        method = scope["method"]
        request_id = new_id()
        started = perf_counter()
        status = 500
        response_started = False
        headers = Headers(scope=scope)

        async def respond(message):
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                status = message["status"]
                response_started = True
                response = MutableHeaders(scope=message)
                response.setdefault("X-Content-Type-Options", "nosniff")
                response.setdefault("X-Frame-Options", "DENY")
                response.setdefault("Referrer-Policy", "no-referrer")
                response.setdefault("Content-Security-Policy", CSP)
                response.setdefault("Cache-Control", "no-store")
                response["X-Request-ID"] = request_id
                if state.secure_cookies:
                    response.setdefault("Strict-Transport-Security", "max-age=31536000")
            await send(message)

        async def dispatch():
            if method in {"POST", "PUT", "PATCH", "DELETE"}:
                limit = MAX_MULTIPART_BYTES if path.rstrip("/") in UPLOAD_ROUTES else 64 * 1024
                messages = []
                count = 0
                length = headers.get("content-length")
                if length is not None and (not length.isascii() or not length.isdigit() or len(length) > 10):
                    raise ApiError(400, "invalid_request", "The request has an invalid length.")
                if length and int(length) > limit:
                    raise ApiError(413, "file_too_large", "This request exceeds the allowed size.")
                while True:
                    incoming = await receive()
                    if incoming["type"] == "http.disconnect":
                        return
                    count += len(incoming.get("body", b""))
                    if count > limit:
                        raise ApiError(413, "file_too_large", "This request exceeds the allowed size.")
                    if incoming.get("body") or not incoming.get("more_body"):
                        messages.append(incoming)
                    if not incoming.get("more_body"):
                        break
                queued = iter(messages)

                async def replay():
                    message = next(queued, None)
                    return message if message is not None else await receive()

                await self.app(scope, replay, respond)
            else:
                await self.app(scope, receive, respond)

        try:
            if path.startswith(("/api/", "/r/")):
                address = scope["client"][0] if scope.get("client") else "unknown"
                state.ip_limits.hit(address, state.ip_requests_per_minute, 60)
            if method == "POST" and path.rstrip("/") == PUBLIC_AUDIT_ROUTE:
                timeout = state.public_audit_timeout
                scope.setdefault("state", {})["public_audit_deadline"] = started + timeout
                try:
                    async with asyncio.timeout(timeout):
                        await dispatch()
                except TimeoutError:
                    if not response_started:
                        raise audit_timeout_error() from None
            else:
                await dispatch()
        except ApiError as error:
            await error.response()(scope, receive, respond)
        except Exception:
            state.logger.error(json.dumps({"event": "request_failed", "request_id": request_id}))
            if state.report_error:
                state.report_error("A11yra request failed", level="error")
            if not response_started:
                await ApiError(500, "server_error", "The server could not complete the request.").response()(
                    scope, receive, respond,
                )
        finally:
            state.requests[status] += 1
            # Route templates exclude tokens, names, query strings and document text.
            route = getattr(scope.get("route"), "path", None)
            state.logger.info(json.dumps({"event": "request", "request_id": request_id, "method": method,
                                          "route": route or "unmatched", "status": status,
                                          "duration_ms": round((perf_counter() - started) * 1000, 1)}))
