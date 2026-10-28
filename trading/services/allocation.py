from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from trading.models import BotConfiguration, MarketSnapshot, PaperPortfolio, PaperWallet
from trading.services.strategy_profiles import is_commodity_symbol


@dataclass(frozen=True, slots=True)
class AllocationDecision:
    asset_class: str
    allowed: bool
    current_exposure: Decimal
    cap_amount: Decimal
    available_amount: Decimal
    reason: str


class CommodityAllocationService:
    def __init__(self, configuration: BotConfiguration) -> None:
        self.cap_fraction: Decimal = configuration.commodity_allocation_cap_fraction

    def evaluate(
        self,
        portfolio: PaperPortfolio,
        wallet: PaperWallet,
        symbol: str,
    ) -> AllocationDecision:
        if not is_commodity_symbol(symbol):
            return AllocationDecision(
                asset_class="crypto",
                allowed=True,
                current_exposure=Decimal("0"),
                cap_amount=Decimal("0"),
                available_amount=wallet.balance,
                reason="asset class allocation unrestricted",
            )

        position_value: Decimal = Decimal("0")
        commodity_exposure: Decimal = Decimal("0")
        for position in portfolio.positions.filter(
            quote_asset=wallet.asset, quantity__gt=0
        ):
            latest_price: Decimal | None = (
                MarketSnapshot.objects.filter(symbol=position.symbol)
                .order_by("-captured_at")
                .values_list("last_price", flat=True)
                .first()
            )
            price: Decimal = latest_price or position.average_entry_price
            value: Decimal = position.quantity * price
            position_value += value
            if is_commodity_symbol(position.symbol):
                commodity_exposure += value

        equity: Decimal = max(Decimal("0"), wallet.balance + position_value)
        cap_amount: Decimal = equity * self.cap_fraction
        available: Decimal = max(Decimal("0"), cap_amount - commodity_exposure)
        allowed: bool = available > 0
        reason: str = (
            "commodity allocation capacity available"
            if allowed
            else (
                "commodity allocation cap reached: "
                f"exposure={commodity_exposure:.2f} {wallet.asset}, "
                f"cap={cap_amount:.2f} {wallet.asset}"
            )
        )
        return AllocationDecision(
            asset_class="commodity",
            allowed=allowed,
            current_exposure=commodity_exposure,
            cap_amount=cap_amount,
            available_amount=available,
            reason=reason,
        )
