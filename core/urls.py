from django.urls import path
from core import views
from core import auth_views

urlpatterns = [
    # Auth
    path("login/", auth_views.login_view, name="login"),
    path("register/", auth_views.register_view, name="register"),
    path("logout/", auth_views.logout_view, name="logout"),
    path("forgot-password/", auth_views.forgot_password_view, name="forgot_password"),
    path("terms/", auth_views.terms_view, name="terms"),
    path("privacy/", auth_views.privacy_view, name="privacy"),

    path("", views.home, name="home"),
    path("dashboard/<int:project_id>/", views.dashboard, name="dashboard"),
    path("crawl-status/<int:project_id>/", views.crawl_status, name="crawl_status"),
    path("stop-crawl/<int:project_id>/", views.stop_crawl, name="stop_crawl"),
    path("projects/", views.projects_list, name="projects"),
    path("scans/", views.scans_list, name="scans"),
    path("pages/", views.pages_list, name="pages"),
    path("issues/", views.issues_all, name="issues_all"),
    path("issues/<int:project_id>/", views.issues_list, name="issues"),
    path("rules/", views.rules_list, name="rules"),
    path("reports/", views.reports_list, name="reports"),
    path("settings/", views.settings_page, name="settings"),
    path("export/csv/<int:project_id>/", views.export_csv, name="export_csv"),
    # LLM endpoints
    path("llm/status/", views.llm_status_api, name="llm_status"),
    path("llm/analyze/<int:project_id>/", views.trigger_llm_analysis, name="trigger_llm"),
    path("llm/stop/<int:project_id>/", views.stop_llm_analysis, name="stop_llm"),
    # Re-scan
    path("rescan/<int:project_id>/", views.rescan_project, name="rescan"),
    # Issue dismissal
    path("issue/dismiss/<int:issue_id>/", views.dismiss_issue, name="dismiss_issue"),
    path("issue/undismiss/<int:issue_id>/", views.undismiss_issue, name="undismiss_issue"),
]
