from django.urls import path
from core import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/<int:project_id>/", views.dashboard, name="dashboard"),
    path("crawl-status/<int:project_id>/", views.crawl_status, name="crawl_status"),
    path("projects/", views.projects_list, name="projects"),
    path("scans/", views.scans_list, name="scans"),
    path("pages/", views.pages_list, name="pages"),
    path("issues/", views.issues_all, name="issues_all"),
    path("issues/<int:project_id>/", views.issues_list, name="issues"),
    path("rules/", views.rules_list, name="rules"),
    path("reports/", views.reports_list, name="reports"),
    path("settings/", views.settings_page, name="settings"),
]
