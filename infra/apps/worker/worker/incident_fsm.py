from typing import Tuple

from apps.sentryml_core.models import IncidentSeverity


# -------------------------
# INCIDENT FSM
# -------------------------

Action = str


def incident_fsm(
    current_severity: IncidentSeverity,
    new_severity: IncidentSeverity,
) -> Tuple[IncidentSeverity, Action]:
    """
    Decide next incident severity and action.
    """

    if current_severity == IncidentSeverity.NONE:
        if new_severity == IncidentSeverity.NONE:
            return IncidentSeverity.NONE, "noop"
        if new_severity == IncidentSeverity.WARN:
            return IncidentSeverity.WARN, "open"
        if new_severity == IncidentSeverity.CRITICAL:
            return IncidentSeverity.CRITICAL, "open"

    if current_severity == IncidentSeverity.WARN:
        if new_severity == IncidentSeverity.NONE:
            return IncidentSeverity.NONE, "resolve"
        if new_severity == IncidentSeverity.WARN:
            return IncidentSeverity.WARN, "update"
        if new_severity == IncidentSeverity.CRITICAL:
            return IncidentSeverity.CRITICAL, "escalate"

    if current_severity == IncidentSeverity.CRITICAL:
        if new_severity == IncidentSeverity.NONE:
            return IncidentSeverity.NONE, "resolve"
        if new_severity == IncidentSeverity.WARN:
            return IncidentSeverity.WARN, "downgrade"
        if new_severity == IncidentSeverity.CRITICAL:
            return IncidentSeverity.CRITICAL, "update"

    raise RuntimeError("Invalid FSM transition")
