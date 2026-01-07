

import pytest

from app.payouts.state_machine import assert_transition, InvalidTransition


def test_valid_transitions():
    assert_transition("PENDING", "SENT")
    assert_transition("PENDING", "FAILED")
    assert_transition("SENT", "CONFIRMED")
    assert_transition("SENT", "FAILED")


def test_invalid_transition_skipping_states():
    with pytest.raises(InvalidTransition):
        assert_transition("PENDING", "CONFIRMED")


def test_terminal_states_cannot_transition():
    with pytest.raises(InvalidTransition):
        assert_transition("CONFIRMED", "FAILED")
    with pytest.raises(InvalidTransition):
        assert_transition("FAILED", "CONFIRMED")
