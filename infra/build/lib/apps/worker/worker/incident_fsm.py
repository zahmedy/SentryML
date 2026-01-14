from typing import Literal, Tuple


# -------------------------
# INCIDENT FSM
# -------------------------

State = Literal["none", "warn", "critical"]
Severity = Literal["ok", "warn", "critical"]
Action = Literal["noop", "open", "escalate", "downgrade", "update", "resolve"]


def incident_fsm(
    current_state: State,
    new_severity: Severity,
) -> Tuple[State, Action]:
    """
    Decide next incident state and action.
    """

    if current_state == "none":
        if new_severity == "ok":
            return "none", "noop"
        if new_severity == "warn":
            return "warn", "open"
        if new_severity == "critical":
            return "critical", "open"

    if current_state == "warn":
        if new_severity == "ok":
            return "none", "resolve"
        if new_severity == "warn":
            return "warn", "update"
        if new_severity == "critical":
            return "critical", "escalate"

    if current_state == "critical":
        if new_severity == "ok":
            return "none", "resolve"
        if new_severity == "warn":
            return "warn", "downgrade"
        if new_severity == "critical":
            return "critical", "update"

    raise RuntimeError("Invalid FSM transition")