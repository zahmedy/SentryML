import pytest

from apps.sentryml_core.models import IncidentSeverity
from apps.worker.worker.run_once import (
    severity_for_psi,
    eligible_for_monitoring,
)


@pytest.mark.parametrize(
    "psi,warn,critical,expected",
    [
        (0.05, 0.1, 0.2, IncidentSeverity.NONE),
        (0.1, 0.1, 0.2, IncidentSeverity.WARN),
        (0.15, 0.1, 0.2, IncidentSeverity.WARN),
        (0.2, 0.1, 0.2, IncidentSeverity.CRITICAL),
        (0.5, 0.1, 0.2, IncidentSeverity.CRITICAL),
    ],
)
def test_severity_for_psi(psi, warn, critical, expected):
    assert severity_for_psi(psi, warn, critical) == expected


def test_eligible_for_monitoring_missing_scores():
    baseline, current = eligible_for_monitoring([None, None], [None], min_samples=1)
    assert baseline == []
    assert current == []


def test_eligible_for_monitoring_not_enough_samples():
    baseline, current = eligible_for_monitoring([0.1], [0.2], min_samples=2)
    assert baseline == []
    assert current == []


def test_eligible_for_monitoring_enough_samples():
    baseline, current = eligible_for_monitoring([0.1, 0.2], [0.3, 0.4], min_samples=2)
    assert baseline == [0.1, 0.2]
    assert current == [0.3, 0.4]
