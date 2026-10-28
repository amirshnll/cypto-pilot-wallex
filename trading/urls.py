from django.urls import path

from . import views

app_name = "trading"

urlpatterns = [path("", views.health, name="health")]
urlpatterns += [path("ready/", views.ready, name="ready")]
urlpatterns += [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/settings/", views.settings_view, name="settings"),
    path("dashboard/settings/reset/", views.reset_bot, name="reset_bot"),
    path("dashboard/run/", views.run_bot, name="run_bot"),
    path("dashboard/export/trades.csv", views.export_trades, name="export_trades"),
    path("dashboard/export/reports.csv", views.export_reports, name="export_reports"),
    path("dashboard/alerts/read/", views.mark_alerts_read, name="mark_alerts_read"),
]
