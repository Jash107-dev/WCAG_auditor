from django.urls import path
from reporting import views

urlpatterns = [
    path("page/<int:page_id>/", views.page_report, name="page_report"),
    path("ada/<int:project_id>/", views.ada_statement, name="ada_statement"),
    path("export/pdf/<int:project_id>/", views.export_pdf, name="export_pdf"),
]
