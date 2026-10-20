"""ETag and conditional GET for the data routes.

The ETag is a digest of the exact body, so the same answer always carries the same tag.
"""

from datetime import datetime
from hashlib import sha256

from fastapi import Request, Response, status
from pydantic import BaseModel

ETAG_HEX_CHARS = 32
NO_CACHE = "no-cache"
IMMUTABLE = "public, max-age=31536000, immutable"


def cache_control(requested: datetime | None, answered: datetime, *, complete: bool = True) -> str:
    """``immutable`` for a settled answer: an ``as_of`` was asked and echoed back as the answer.

    Persistence answers an ``as_of`` after its knowledge horizon at the horizon, so an answer
    whose ``meta.as_of`` differs from the request can still change and must be revalidated.
    An answer with an unchecked value is not settled even when ``as_of`` matches.
    """
    if requested is not None and requested == answered and complete:
        return IMMUTABLE
    return NO_CACHE


def json_with_etag(
    request: Request, model: BaseModel, *, cache_control: str = NO_CACHE
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
