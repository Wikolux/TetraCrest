"""Pure RICE/ICE scoring + framework-selection functions (Milestone 6) -
deterministic arithmetic, independently defined from Product Decision's
own scoring.py (Milestone 4), never imported from it.
"""

from app.services.ai.agents.specialists.product_management.shared.decision_record import DecisionFramework
from app.services.ai.agents.specialists.product_management.strategy_portfolio.scoring import (
    ice_score,
    rice_score,
    select_framework,
)


def test_rice_score_computes_when_all_inputs_given():
    assert rice_score(reach=1000, impact=2, confidence=0.8, effort=4) == (1000 * 2 * 0.8) / 4


def test_rice_score_is_none_when_any_input_missing():
    assert rice_score(None, 2, 0.8, 4) is None
    assert rice_score(1000, 2, 0.8, 0) is None


def test_ice_score_computes_when_all_inputs_given():
    assert ice_score(impact=8, confidence=7, ease=6) == (8 + 7 + 6) / 3


def test_ice_score_is_none_when_any_input_missing():
    assert ice_score(None, 7, 6) is None


def test_selects_sunset_checklist_for_deprecation_language():
    assert select_framework("Should we sunset this product line?", 0) == DecisionFramework.SUNSET_CHECKLIST


def test_selects_build_vs_buy_for_investment_language():
    assert select_framework("Should we double down and invest further?", 0) == DecisionFramework.BUILD_VS_BUY


def test_selects_cost_of_delay_for_sequencing_language():
    assert select_framework("What is the cost of delay here?", 0) == DecisionFramework.COST_OF_DELAY


def test_selects_kano_for_delight_language():
    assert select_framework("Is this a delight feature per Kano?", 0) == DecisionFramework.KANO


def test_selects_rice_when_more_than_two_options_and_no_other_signal():
    assert select_framework("Which initiative should we prioritize?", 3) == DecisionFramework.RICE


def test_defaults_to_ice_when_nothing_more_specific_indicated():
    assert select_framework("Should we do this?", 0) == DecisionFramework.ICE
