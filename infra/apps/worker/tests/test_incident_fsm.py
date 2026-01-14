import pytest

from apps.worker.worker.incident_fsm import incident_fsm


@pytest.mark.parametrize(
    "current_state,new_severity,expected_state,expected_action",
    [
        # NONE
        ("none", "ok", "none", "noop"),
        ("none", "warn", "warn", "open"),
        ("none", "critical", "critical", "open"),

        # WARN
        ("warn", "ok", "none", "resolve"),
        ("warn", "warn", "warn", "update"),
        ("warn", "critical", "critical", "escalate"),

        # CRITICAL
        ("critical", "ok", "none", "resolve"),
        ("critical", "warn", "warn", "downgrade"),
        ("critical", "critical", "critical", "update"),
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
