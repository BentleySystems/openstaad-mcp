"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

One-time token delivery via the OneTimeSecret v2 guest API.

Uses only Python stdlib (urllib + json) — no extra dependencies.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_DEFAULT_OTS_BASE_URL = "https://uk.onetimesecret.com"
_CONCEAL_PATH = "/api/v2/guest/secret/conceal"
_DEFAULT_TTL = 86400  # 24 hours


@dataclass(frozen=True)
class OTSResult:
    """Successful result from the OTS conceal call."""

    share_url: str
    secret_identifier: str


def deliver_token_via_ots(
    token: str,
    recipient_email: str | None = None,
    *,
    ots_base_url: str = _DEFAULT_OTS_BASE_URL,
    ttl: int = _DEFAULT_TTL,
    timeout_seconds: int = 15,
) -> OTSResult:
    """Push *token* to OTS as a one-time secret and return a share URL.

    Uses the **guest** endpoint (``/api/v2/guest/secret/conceal``) which
    requires no authentication — no OTS account or API key needed.

    If *recipient_email* is provided **and** the OTS instance supports
    guest email delivery, the link is also emailed.  When omitted (the
    default), only the share URL is returned — the caller is responsible
    for presenting it to the user.

    Returns an :class:`OTSResult` on success.
    Raises :class:`OTSDeliveryError` on any failure.
    """
    parsed = urlparse(ots_base_url)
    share_domain = parsed.hostname or parsed.netloc

    secret_data: dict[str, object] = {
        "kind": "conceal",
        "share_domain": share_domain,
        "secret": token,
        "ttl": ttl,
    }
    if recipient_email:
        secret_data["recipient"] = recipient_email

    payload = json.dumps({"secret": secret_data}).encode("utf-8")

    url = ots_base_url.rstrip("/") + _CONCEAL_PATH
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise OTSDeliveryError(
            f"OTS returned HTTP {exc.code}: {detail[:200]}"
        ) from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise OTSDeliveryError(f"OTS request failed: {exc}") from exc

    # Extract share URL from the v2 guest response.
    # The API returns ``record.secret.key`` and ``record.share_domain``
    # but no pre-built URL.  We construct it ourselves, preferring the
    # ``share_domain`` echoed back by the server when it is non-null.
    try:
        record = body["record"]
        secret_obj = record["secret"]
        secret_key = secret_obj["key"]
        secret_id = secret_obj.get("identifier", secret_key)
    except (KeyError, TypeError) as exc:
        raise OTSDeliveryError(
            f"Unexpected OTS response structure: {exc}"
        ) from exc

    if not secret_key:
        raise OTSDeliveryError("OTS response did not contain a secret key")

    resp_domain = record.get("share_domain")  # str | null per spec
    if resp_domain:
        share_url = f"https://{resp_domain}/secret/{secret_key}"
    else:
        share_url = f"{ots_base_url.rstrip('/')}/secret/{secret_key}"

    return OTSResult(share_url=share_url, secret_identifier=secret_id)


class OTSDeliveryError(Exception):
    """Raised when the OTS secret-delivery call fails for any reason."""
