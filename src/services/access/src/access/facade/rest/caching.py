"""ETag and conditional GET for the data routes.

The ETag is a digest of the exact body, so the same answer always carries the same tag.
"""

from hashlib import sha256

from fastapi import Request, Response, status
from pydantic import BaseModel

ETAG_HEX_CHARS = 32


def json_with_etag(
    request: Request, model: BaseModel, *, cache_control: str = "no-cache"
) -> Response:
    """The model as JSON with an ``ETag``; ``304`` without a body if the client already has it."""
    body = model.model_dump_json().encode()
    etag = f'"{sha256(body).hexdigest()[:ETAG_HEX_CHARS]}"'
    headers = {"ETag": etag, "Cache-Control": cache_control}
    if _matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return Response(body, media_type="application/json", headers=headers)


def _matches(if_none_match: str | None, etag: str) -> bool:
    if if_none_match is None:
        return False
    candidates = [candidate.strip() for candidate in if_none_match.split(",")]
    return any(candidate == "*" or _strip_weak(candidate) == etag for candidate in candidates)


def _strip_weak(tag: str) -> str:
    return tag[2:] if tag.startswith("W/") else tag
