from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone

from trading.models import BotConfiguration, OrderBookSnapshot, Trade


@dataclass(frozen=True, slots=True)
class PaperExecution:
    requested_quantity: Decimal
    filled_quantity: Decimal
    reference_price: Decimal
    execution_price: Decimal
    gross_notional: Decimal
    fee_amount: Decimal
    net_cash_change: Decimal
    slippage_amount: Decimal
    slippage_bps: Decimal
    simulated_latency_ms: int
    liquidity_fraction: Decimal


class PaperExecutionService:
    BPS: Decimal = Decimal("10000")

    def __init__(self, configuration: BotConfiguration) -> None:
        self.fee_fraction: Decimal = configuration.paper_fee_fraction
        self.base_slippage_bps: Decimal = configuration.paper_slippage_bps
        self.latency_ms: int = configuration.paper_latency_ms
        self.max_participation: Decimal = configuration.paper_max_book_participation

    def execute(
        self,
        symbol: str,
        side: str,
        requested_quantity: Decimal,
        fallback_bid: Decimal,
        fallback_ask: Decimal,
    ) -> PaperExecution | None:
        book: OrderBookSnapshot | None = OrderBookSnapshot.objects.filter(
            symbol=symbol
        ).first()
        if book is None or book.captured_at < timezone.now() - timedelta(minutes=10):
            return None
        levels: list[tuple[Decimal, Decimal]] = self._levels(book, side)
        reference: Decimal = self._reference_price(
            book, side, fallback_bid, fallback_ask
        )
        if requested_quantity <= 0 or reference <= 0:
            return None
        liquid_quantity: Decimal = sum(
            (quantity for _price, quantity in levels), Decimal("0")
        )
        fill_limit: Decimal = liquid_quantity * self.max_participation
        filled: Decimal = (
            min(requested_quantity, fill_limit) if liquid_quantity > 0 else Decimal("0")
        )
        if filled <= 0:
            return None
        book_price: Decimal = self._walk_book(levels, filled, reference)
        latency_slippage: Decimal = (
            self.base_slippage_bps * Decimal(self.latency_ms) / Decimal("1000")
        )
        direction: Decimal = Decimal("1") if side == Trade.Side.BUY else Decimal("-1")
        execution_price: Decimal = book_price * (
            Decimal("1") + direction * latency_slippage / self.BPS
        )
        gross: Decimal = filled * execution_price
        fee: Decimal = gross * self.fee_fraction
        net: Decimal = -(gross + fee) if side == Trade.Side.BUY else gross - fee
        signed_slippage: Decimal = (execution_price - reference) * direction
        slippage_bps: Decimal = signed_slippage / reference * self.BPS
        return PaperExecution(
            requested_quantity=requested_quantity,
            filled_quantity=filled,
            reference_price=reference,
            execution_price=execution_price,
            gross_notional=gross,
            fee_amount=fee,
            net_cash_change=net,
            slippage_amount=signed_slippage * filled,
            slippage_bps=slippage_bps,
            simulated_latency_ms=self.latency_ms,
            liquidity_fraction=filled / requested_quantity,
        )

    @staticmethod
    def _levels(
        book: OrderBookSnapshot | None, side: str
    ) -> list[tuple[Decimal, Decimal]]:
        raw: list[list[str]] = (
            (book.asks if side == Trade.Side.BUY else book.bids) if book else []
        )
        levels = [
            (Decimal(str(level[0])), Decimal(str(level[1])))
            for level in raw
            if len(level) >= 2
        ]
        return sorted(
            (
                (price, quantity)
                for price, quantity in levels
                if price > 0 and quantity > 0
            ),
            key=lambda pair: pair[0],
            reverse=side == Trade.Side.SELL,
        )

    @staticmethod
    def _reference_price(
        book: OrderBookSnapshot | None,
        side: str,
        fallback_bid: Decimal,
        fallback_ask: Decimal,
    ) -> Decimal:
        value: Decimal | None = (
            book.best_ask
            if book and side == Trade.Side.BUY
            else book.best_bid if book else None
        )
        return value or (fallback_ask if side == Trade.Side.BUY else fallback_bid)

    @staticmethod
    def _walk_book(
        levels: list[tuple[Decimal, Decimal]], quantity: Decimal, fallback: Decimal
    ) -> Decimal:
        remaining: Decimal = quantity
        value: Decimal = Decimal("0")
        for price, available in levels:
            take: Decimal = min(remaining, available)
            value += take * price
            remaining -= take
            if remaining <= 0:
                break
        if remaining > 0:
            value += remaining * fallback
        return value / quantity
