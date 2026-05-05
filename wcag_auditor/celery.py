import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wcag_auditor.settings')

app = Celery('wcag_auditor')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()
