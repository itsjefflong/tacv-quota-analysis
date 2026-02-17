"""
TACV Guardrail Validation
=========================
Validates recommended TACV against organizational quota plan guardrails.
"""

from typing import Any, Dict

from core.config import (
    BCR_MAX_PERCENT,
    CHURN_MAX_PERCENT,
    GROWTH_REVIEW_PERCENT,
    MIN_TACV_AMOUNT,
)
from core.utils import format_currency


def validate_guardrails(
    recommended_tacv: float,
    fields: Dict[str, Any],
    guardrail_context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Validate recommended TACV against quota plan guardrails.

    Returns a dict with pass/fail status and details for each guardrail.
    """
    results: Dict[str, Any] = {
        'checks': [],
        'passed': 0,
        'failed': 0,
        'warnings': 0,
        'not_applicable': 0,
    }

    territory_target = guardrail_context.get('territory_tacv_target')
    account_type = guardrail_context.get('account_type', 'Expansion')
    is_declining = guardrail_context.get('is_declining_account', False)
    prior_fy_actuals = fields.get('prior_fy_actuals')
    prior_renewal_base = fields.get('prior_renewal_base')

    # ── 1. BCR Check: Account TACV ≤ 25% of Territory Target ──
    if territory_target and territory_target > 0:
        bcr = (recommended_tacv / territory_target) * 100
        bcr_passed = bcr <= BCR_MAX_PERCENT

        results['checks'].append({
            'name': f'Max BCR ≤ {BCR_MAX_PERCENT}%',
            'status': 'pass' if bcr_passed else 'fail',
            'icon': '✅' if bcr_passed else '❌',
            'value': f"{bcr:.1f}%",
            'threshold': f'≤ {BCR_MAX_PERCENT}%',
            'detail': f"Account represents {bcr:.1f}% of territory TACV target ({format_currency(territory_target)})",
            'negotiable': False,
        })
        results['passed' if bcr_passed else 'failed'] += 1
    else:
        results['checks'].append({
            'name': f'Max BCR ≤ {BCR_MAX_PERCENT}%',
            'status': 'na',
            'icon': '➖',
            'value': 'N/A',
            'threshold': f'≤ {BCR_MAX_PERCENT}%',
            'detail': 'Territory TACV target not provided – cannot calculate BCR',
            'negotiable': False,
        })
        results['not_applicable'] += 1

    # ── 2. Minimum TACV ≥ $1M ──
    min_tacv_passed = recommended_tacv >= MIN_TACV_AMOUNT

    results['checks'].append({
        'name': f'Minimum TACV ≥ {format_currency(MIN_TACV_AMOUNT)}',
        'status': 'pass' if min_tacv_passed else 'warning',
        'icon': '✅' if min_tacv_passed else '⚠️',
        'value': format_currency(recommended_tacv),
        'threshold': f'≥ {format_currency(MIN_TACV_AMOUNT)}',
        'detail': f'TACV quota must be ≥ {format_currency(MIN_TACV_AMOUNT)} when assigning renewal quota for Acquisition, Hybrid, or Expansion accounts',
        'negotiable': True,
    })
    results['passed' if min_tacv_passed else 'warnings'] += 1

    # ── 3. TACV ≥ FY Consumption (for Expansion/Hybrid) ──
    if account_type in ['Expansion', 'Hybrid'] and prior_fy_actuals and prior_fy_actuals > 0:
        consumption_passed = recommended_tacv >= prior_fy_actuals
        pct_of_consumption = (recommended_tacv / prior_fy_actuals) * 100

        results['checks'].append({
            'name': f'TACV ≥ Prior FY Consumption ({account_type})',
            'status': 'pass' if consumption_passed else 'warning',
            'icon': '✅' if consumption_passed else '⚠️',
            'value': f"{pct_of_consumption:.0f}% of FY actuals",
            'threshold': '≥ 100%',
            'detail': f"Recommended {format_currency(recommended_tacv)} vs Prior FY Actuals {format_currency(prior_fy_actuals)}",
            'negotiable': True,
        })
        results['passed' if consumption_passed else 'warnings'] += 1
    elif account_type in ['Expansion', 'Hybrid']:
        results['checks'].append({
            'name': f'TACV ≥ Prior FY Consumption ({account_type})',
            'status': 'na',
            'icon': '➖',
            'value': 'N/A',
            'threshold': '≥ 100%',
            'detail': 'Prior FY Actuals not provided – cannot validate consumption floor',
            'negotiable': True,
        })
        results['not_applicable'] += 1

    # ── 4. Churn Risk Flag (Declining Account Awareness) ──
    if is_declining:
        if territory_target and territory_target > 0:
            churn_pct = (recommended_tacv / territory_target) * 100
            churn_passed = churn_pct <= CHURN_MAX_PERCENT

            results['checks'].append({
                'name': f'Declining Account ≤ {CHURN_MAX_PERCENT}% of Territory',
                'status': 'pass' if churn_passed else 'warning',
                'icon': '✅' if churn_passed else '⚠️',
                'value': f"{churn_pct:.1f}%",
                'threshold': f'≤ {CHURN_MAX_PERCENT}%',
                'detail': f"⚠️ Flagged as declining account (consecutive downsells). Represents {churn_pct:.1f}% of territory TACV.",
                'negotiable': True,
            })
            results['passed' if churn_passed else 'warnings'] += 1
        else:
            results['checks'].append({
                'name': f'Declining Account ≤ {CHURN_MAX_PERCENT}% of Territory',
                'status': 'warning',
                'icon': '⚠️',
                'value': 'Flagged',
                'threshold': f'≤ {CHURN_MAX_PERCENT}%',
                'detail': '⚠️ Account flagged as declining (consecutive downsells). Provide territory target to validate concentration.',
                'negotiable': True,
            })
            results['warnings'] += 1

    # ── 5. Growth Reasonability Check ──
    if prior_renewal_base and prior_renewal_base > 0:
        growth_pct = ((recommended_tacv - prior_renewal_base) / prior_renewal_base) * 100

        if growth_pct > GROWTH_REVIEW_PERCENT:
            results['checks'].append({
                'name': 'Growth Reasonability',
                'status': 'info',
                'icon': 'ℹ️',
                'value': f"+{growth_pct:.0f}%",
                'threshold': f'Review if >{GROWTH_REVIEW_PERCENT}%',
                'detail': f"High growth scenario: {format_currency(recommended_tacv)} vs prior base {format_currency(prior_renewal_base)}. Verify expansion drivers.",
                'negotiable': True,
            })

    return results
