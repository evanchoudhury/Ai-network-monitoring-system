"""Budget & resource governance.

The platform is designed to run with **zero** mandatory external AI spend: all
core analysis (anomaly detection, claim extraction, spam scoring) uses
deterministic rules and local ML. These controls exist so that *if* an operator
opts into an external LLM, usage stays inside configured limits.

Key guarantees
--------------
* ``check_and_reserve`` must be called before any billable model request.
* Costs recorded by the deterministic pipeline are 0 and clearly flagged as
  estimates vs provider-reported.
* On any error evaluating a mandatory budget check we FAIL CLOSED (deny the
  operation) when ``budget_fail_closed`` is set.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.logging import get_logger
from app.models import AIUsage

logger = get_logger("sentinel.budget")


class BudgetExceeded(Exception):
    """Raised when a billable operation would exceed a configured budget."""


@dataclass
class BudgetStatus:
    day_requests: int
    day_tokens: int
    day_cost_usd: float
    month_cost_usd: float
    limits: dict
    within_budget: bool
    notes: list[str]


def _day_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def _month_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, now


def get_status(db: Session, now: datetime | None = None) -> BudgetStatus:
    now = now or datetime.now(timezone.utc)
    day_start, day_end = _day_bounds(now)
    month_start, _ = _month_bounds(now)

    day_row = db.execute(
        select(
            func.coalesce(func.sum(AIUsage.requests), 0),
            func.coalesce(func.sum(AIUsage.input_tokens + AIUsage.output_tokens), 0),
            func.coalesce(func.sum(AIUsage.estimated_cost_usd), 0.0),
        ).where(AIUsage.created_at >= day_start, AIUsage.created_at < day_end)
    ).one()
    month_cost = db.scalar(
        select(func.coalesce(func.sum(AIUsage.estimated_cost_usd), 0.0)).where(
            AIUsage.created_at >= month_start
        )
    )

    day_requests, day_tokens, day_cost = int(day_row[0]), int(day_row[1]), float(day_row[2])
    month_cost = float(month_cost or 0.0)

    notes: list[str] = []
    within = True
    if day_requests >= settings.budget_max_model_requests_per_day:
        within = False
        notes.append("Daily model-request limit reached.")
    if day_tokens >= settings.budget_max_tokens_per_day:
        within = False
        notes.append("Daily token limit reached.")
    if day_cost >= settings.budget_daily_usd:
        within = False
        notes.append("Daily cost budget reached.")
    if month_cost >= settings.budget_monthly_usd:
        within = False
        notes.append("Monthly cost budget reached.")

    return BudgetStatus(
        day_requests=day_requests,
        day_tokens=day_tokens,
        day_cost_usd=round(day_cost, 6),
        month_cost_usd=round(month_cost, 6),
        limits={
            "daily_usd": settings.budget_daily_usd,
            "monthly_usd": settings.budget_monthly_usd,
            "max_requests_per_day": settings.budget_max_model_requests_per_day,
            "max_tokens_per_day": settings.budget_max_tokens_per_day,
        },
        within_budget=within,
        notes=notes,
    )


def check_and_reserve(
    db: Session,
    *,
    estimated_tokens: int = 0,
    estimated_cost_usd: float = 0.0,
) -> BudgetStatus:
    """Verify a prospective billable operation fits within budget.

    Raises ``BudgetExceeded`` if it does not, or if the check itself fails and
    ``budget_fail_closed`` is enabled.
    """
    try:
        status = get_status(db)
    except Exception as exc:  # noqa: BLE001
        logger.error("Budget check failed", extra={"extra_fields": {"error": str(exc)}})
        if settings.budget_fail_closed:
            raise BudgetExceeded("Budget check failed; failing closed.") from exc
        # Fail open only if explicitly configured.
        return BudgetStatus(0, 0, 0.0, 0.0, {}, True, ["Budget check errored; failing open"])

    if not status.within_budget:
        raise BudgetExceeded("; ".join(status.notes) or "Budget exceeded")

    projected_tokens = status.day_tokens + estimated_tokens
    projected_cost = status.day_cost_usd + estimated_cost_usd
    if projected_tokens > settings.budget_max_tokens_per_day:
        raise BudgetExceeded("Operation would exceed the daily token budget.")
    if projected_cost > settings.budget_daily_usd:
        raise BudgetExceeded("Operation would exceed the daily cost budget.")
    if status.day_requests + 1 > settings.budget_max_model_requests_per_day:
        raise BudgetExceeded("Operation would exceed the daily request budget.")
    return status


def record_usage(
    db: Session,
    *,
    provider: str,
    operation: str,
    model: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    requests: int = 1,
    estimated_cost_usd: float = 0.0,
    provider_reported: bool = False,
    commit: bool = True,
) -> AIUsage:
    usage = AIUsage(
        provider=provider,
        operation=operation,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        requests=requests,
        estimated_cost_usd=estimated_cost_usd,
        provider_reported=provider_reported,
    )
    db.add(usage)
    if commit:
        db.commit()
        db.refresh(usage)
    return usage
