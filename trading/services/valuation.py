from decimal import Decimal

from trading.models import MarketSnapshot, PaperPortfolio, PaperWallet
from trading.services.trade_policy import Exposure


def portfolio_exposures(
    portfolio: PaperPortfolio, asset: str, fee: Decimal, slippage: Decimal
) -> list[Exposure]:
    values: list[Exposure] = []
    for position in portfolio.positions.filter(quote_asset=asset, quantity__gt=0):
        price: Decimal = (
            MarketSnapshot.objects.filter(symbol=position.symbol)
            .order_by("-captured_at")
            .values_list("last_price", flat=True)
            .first()
        ) or position.average_entry_price
        value = position.quantity * price
        stop = max(
            position.stop_loss_price or Decimal("0"),
            position.trailing_stop_price or Decimal("0"),
        )
        risk = max(Decimal("0"), price - stop) * position.quantity + value * (
            fee * 2 + slippage * 2
        )
        values.append(Exposure(position.symbol, value, risk))
    return values
