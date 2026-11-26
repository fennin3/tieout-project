"""Approve or reject matches that are waiting for review."""

import logging
import re
import uuid

from django.utils import timezone

from recon.exceptions import ReviewError
from recon.models import Match

logger = logging.getLogger(__name__)

ACTION_STATES = {"approve": Match.State.APPROVED, "reject": Match.State.REJECTED}
SHORT_ID_PATTERN = re.compile(r"^[0-9a-f-]{4,36}$")


def review_match(match_id: str, action: str, reviewer: str, reason: str) -> Match:
    """Record an approve or reject decision on a pending_review match."""
    if action not in ACTION_STATES:
        raise ReviewError(f"invalid action {action!r}, expected approve or reject")
    match = _find_match(match_id)
    if match.state != Match.State.PENDING_REVIEW:
        raise ReviewError(f"match {match.id} is {match.state}, only pending_review can be reviewed")

    match.state = ACTION_STATES[action]
    match.reviewed_at = timezone.now()
    match.reviewed_by = reviewer
    match.reason = reason
    match.save(update_fields=["state", "reviewed_at", "reviewed_by", "reason"])
    logger.info("match %s %s by %s", match.id, match.state, reviewer)
    return match


def _find_match(match_id: str) -> Match:
    # show_matches prints a short id, so a unique leading fragment of the UUID is accepted.
    try:
        full_id = uuid.UUID(match_id)
    except ValueError:
        if not SHORT_ID_PATTERN.match(match_id.lower()):
            raise ReviewError(f"invalid match id {match_id!r}") from None
        candidates = list(Match.objects.filter(id__startswith=match_id.lower())[:2])
    else:
        candidates = list(Match.objects.filter(id=full_id))

    if not candidates:
        raise ReviewError(f"match {match_id} not found")
    if len(candidates) > 1:
        raise ReviewError(f"match id {match_id} is ambiguous, use the full id")
    return candidates[0]
