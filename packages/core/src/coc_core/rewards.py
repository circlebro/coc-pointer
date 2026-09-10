"""When a month's CWL results can no longer change.

The bonus draw is run by the admin in the browser, on the reward tab, and it may only run
once the scores are final: otherwise a later attack could change who was even a candidate.
"""

from __future__ import annotations

from collections.abc import Iterable

from coc_core.models import War


def cwl_is_settled(cwl_wars: Iterable[War]) -> bool:
    """True when no further attack can change the month's CWL scores.

    Every round of the season must be on hand, and each of those wars must be finished or
    have every attack used up. A war still open with attacks left could change the ranking.
    """
    wars = list(cwl_wars)
    if not wars:
        return False
    total = next((w.total_rounds for w in wars if w.total_rounds), None)
    if total is None or len(wars) < total:
        return False
    return all(not w.in_progress or w.attacks_made >= w.attack_slots for w in wars)
