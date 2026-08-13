"""Pure RICE/ICE scoring + framework-selection functions (Milestone 4) -
deterministic arithmetic, never fabricated. A missing input yields None,
never a guessed number."""

from app.services.ai.agents.specialists.product_management.shared.decision_record import DecisionFramework
from app.services.ai.agents.specialists.product_management.product_decision.scoring import (
    ice_score,
    rice_score,
    select_framework,
)


# --- rice_score --------------------------------------------------------------------------------


def test_rice_score_computes_when_all_inputs_given():
    score = rice_score(reach=1000, impact=2, confidence=0.8, effort=4)
    assert score == (1000 * 2 * 0.8) / 4


def test_rice_score_is_none_when_any_input_missing():
    assert rice_score(None, 2, 0.8, 4) is None
    assert rice_score(1000, None, 0.8, 4) is None
    assert rice_score(1000, 2, None, 4) is None
    assert rice_score(1000, 2, 0.8, None) is None


def test_rice_score_is_none_when_effort_is_zero():
    assert rice_score(1000, 2, 0.8, 0) is None


# --- ice_score ---------------------------------------------------------------------------------


def test_ice_score_computes_when_all_inputs_given():
    score = ice_score(impact=8, confidence=7, ease=6)
    assert score == (8 + 7 + 6) / 3


def test_ice_score_is_none_when_any_input_missing():
    assert ice_score(None, 7, 6) is None
    assert ice_score(8, None, 6) is None
    assert ice_score(8, 7, None) is None


# --- select_framework ----------------------------------------------------------------------------


def test_selects_sunset_checklist_for_deprecation_language():
    assert select_framework("Should we sunset the legacy API?", 0) == DecisionFramework.SUNSET_CHECKLIST
    assert select_framework("Time to deprecate this feature", 0) == DecisionFramework.SUNSET_CHECKLIST


def test_selects_build_vs_buy_for_sourcing_language():
    assert select_framework("Should we outsource this to a vendor?", 0) == DecisionFramework.BUILD_VS_BUY


def test_selects_cost_of_delay_for_sequencing_language():
    assert select_framework("What is the cost of delay here?", 0) == DecisionFramework.COST_OF_DELAY


def test_selects_kano_for_delight_language():
    assert select_framework("Is this a delight feature per Kano?", 0) == DecisionFramework.KANO


def test_selects_rice_when_more_than_two_options_and_no_other_signal():
    assert select_framework("Which feature should we prioritize?", 3) == DecisionFramework.RICE


def test_defaults_to_ice_when_nothing_more_specific_indicated():
    assert select_framework("Should we do this?", 0) == DecisionFramework.ICE
    assert select_framework("Should we do this?", 2) == DecisionFramework.ICE
