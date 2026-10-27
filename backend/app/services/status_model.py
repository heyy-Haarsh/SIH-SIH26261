"""One definition of "where is this application?" shared by every role and dashboard.

The database still holds legacy status values from earlier demo data. Instead of each screen
deciding for itself which statuses count as "in the queue" (which produced dashboards that
disagreed with each other), every metric and filter goes through ``stage_of``.

Stages answer "whose turn is it?":

* ``draft``               – applicant has not submitted yet
* ``awaiting_scrutiny``   – submitted/resubmitted, waiting for an officer to pick it up
* ``under_scrutiny``      – an officer is working on it
* ``awaiting_applicant``  – clarification requested, the applicant must respond
* ``decided``             – the officer recorded a recommendation/rejection
"""

from collections import OrderedDict

from app.models.enums import ApplicationStatus as S

STAGE_DRAFT = "draft"
STAGE_AWAITING_SCRUTINY = "awaiting_scrutiny"
STAGE_UNDER_SCRUTINY = "under_scrutiny"
STAGE_AWAITING_APPLICANT = "awaiting_applicant"
STAGE_DECIDED = "decided"

STAGE_LABELS: "OrderedDict[str, str]" = OrderedDict(
    [
        (STAGE_DRAFT, "Draft"),
        (STAGE_AWAITING_SCRUTINY, "Awaiting scrutiny"),
        (STAGE_UNDER_SCRUTINY, "Under scrutiny"),
        (STAGE_AWAITING_APPLICANT, "Awaiting applicant"),
        (STAGE_DECIDED, "Decided"),
    ]
)

_STAGE_BY_STATUS: dict[str, str] = {
    S.DRAFT.value: STAGE_DRAFT,
    S.SUBMITTED.value: STAGE_AWAITING_SCRUTINY,
    S.PROCESSING.value: STAGE_AWAITING_SCRUTINY,
    S.RESUBMITTED.value: STAGE_AWAITING_SCRUTINY,
    S.AWAITING_REVIEW.value: STAGE_AWAITING_SCRUTINY,
    S.UNDER_SCRUTINY.value: STAGE_UNDER_SCRUTINY,
    S.UNDER_REVIEW.value: STAGE_UNDER_SCRUTINY,
    S.MANUAL_REVIEW.value: STAGE_UNDER_SCRUTINY,
    S.CLARIFICATION_REQUIRED.value: STAGE_AWAITING_APPLICANT,
    S.DEFICIENCY.value: STAGE_AWAITING_APPLICANT,
    S.RECOMMENDED.value: STAGE_DECIDED,
    S.REJECTED.value: STAGE_DECIDED,
    S.APPROVED.value: STAGE_DECIDED,
}

# The officer's own workload: it is their turn. Applications waiting on the applicant are
# deliberately excluded — an officer cannot act on them until the applicant responds.
OFFICER_QUEUE_STAGES = (STAGE_AWAITING_SCRUTINY, STAGE_UNDER_SCRUTINY)


def _value(status) -> str:
    return str(getattr(status, "value", status))


def stage_of(status) -> str:
    """Stage for any status, including legacy ones. Unknown values are treated as awaiting
    scrutiny so an application can never silently disappear from every queue."""
    return _STAGE_BY_STATUS.get(_value(status), STAGE_AWAITING_SCRUTINY)


def statuses_in_stage(stage: str) -> list[str]:
    return [s for s, st in _STAGE_BY_STATUS.items() if st == stage]
