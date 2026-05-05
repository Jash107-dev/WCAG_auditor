from celery import shared_task
from analyzer.engine import analyze_page

@shared_task
def async_analyze_page(page_id):
    """
    Celery task to asynchronously analyze a single page.
    """
    analyze_page(page_id)
