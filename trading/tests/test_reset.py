from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from trading.models import (
    BotConfiguration,
    PaperPortfolio,
    MarketSnapshot,
    Trade,
    Strategy,
)
from trading.services.reset import reset_paper_data


class PaperResetTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_superuser(
            "reset-admin", password="test-password"
        )
        self.client.force_login(self.user)
        self.config = BotConfiguration.objects.create(
            name="default", initial_tmn_balance=1000000, risk_halted=True
        )
        self.portfolio = PaperPortfolio.objects.create(
            name="test", initial_balance=100, cash_balance=100
        )
        MarketSnapshot.objects.create(symbol="BTCTMN", last_price=100)

    def test_confirmation_required_and_get_is_not_destructive(self) -> None:
        self.assertEqual(self.client.get(reverse("trading:reset_bot")).status_code, 405)
        self.client.post(
            reverse("trading:reset_bot"),
            {"confirmation": "RESET", "password": "wrong"},
        )
        self.assertEqual(PaperPortfolio.objects.count(), 1)

    @patch("trading.services.reset.call_command")
    def test_reset_preserves_users_settings_and_release_but_clears_history(
        self, backup
    ) -> None:
        response = self.client.post(
            reverse("trading:reset_bot"),
            {"confirmation": "RESET", "password": "test-password"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PaperPortfolio.objects.count(), 0)
        self.assertEqual(MarketSnapshot.objects.count(), 0)
        self.config.refresh_from_db()
        self.assertTrue(self.config.enabled)
        self.assertFalse(self.config.risk_halted)
        self.assertEqual(self.config.initial_tmn_balance, 1000000)
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())
        backup.assert_called_once()

    @patch(
        "trading.services.reset.call_command", side_effect=RuntimeError("backup failed")
    )
    def test_failed_backup_prevents_deletion(self, backup) -> None:
        with self.assertRaises(RuntimeError):
            reset_paper_data()
        self.assertEqual(MarketSnapshot.objects.count(), 1)

    @override_settings(TRADING_MODE="live")
    def test_real_mode_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            reset_paper_data()

    def test_staff_without_superuser_cannot_reset(self) -> None:
        self.user.is_superuser = False
        self.user.save()
        self.assertEqual(
            self.client.post(reverse("trading:reset_bot")).status_code, 403
        )
