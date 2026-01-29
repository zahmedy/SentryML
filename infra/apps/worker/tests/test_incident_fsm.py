import pytest

from apps.sentryml_core.models import IncidentSeverity
from apps.worker.worker.incident_fsm import incident_fsm


@pytest.mark.parametrize(
    "current_state,new_severity,expected_state,expected_action",
    [
        # NONE
        (IncidentSeverity.NONE, IncidentSeverity.NONE, IncidentSeverity.NONE, "noop"),
        (IncidentSeverity.NONE, IncidentSeverity.WARN, IncidentSeverity.WARN, "open"),
        (IncidentSeverity.NONE, IncidentSeverity.CRITICAL, IncidentSeverity.CRITICAL, "open"),

        # WARN
        (IncidentSeverity.WARN, IncidentSeverity.NONE, IncidentSeverity.NONE, "resolve"),
        (IncidentSeverity.WARN, IncidentSeverity.WARN, IncidentSeverity.WARN, "update"),
        (IncidentSeverity.WARN, IncidentSeverity.CRITICAL, IncidentSeverity.CRITICAL, "escalate"),

        # CRITICAL
        (IncidentSeverity.CRITICAL, IncidentSeverity.NONE, IncidentSeverity.NONE, "resolve"),
        (IncidentSeverity.CRITICAL, IncidentSeverity.WARN, IncidentSeverity.WARN, "downgrade"),
        (IncidentSeverity.CRITICAL, IncidentSeverity.CRITICAL, IncidentSeverity.CRITICAL, "update"),
    ],
)
def test_incident_fsm(
    current_state,
    new_severity,
    expected_state,
    expected_action,
):
    next_state, action = incident_fsm(current_state, new_severity)

    assert next_state == expected_state
    assert action == expected_action


def test_incident_fsm_invalid_transition():
    with pytest.raises(RuntimeError):
        incident_fsm("invalid", IncidentSeverity.WARN)  # type: ignore[arg-type]
