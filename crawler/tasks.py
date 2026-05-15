import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def crawl_website_task(self, start_url, project_id, scope="full", use_llm=False):
    """
    Celery task — crawl a website and run accessibility analysis.
    Runs asynchronously so the web request returns immediately.
    """
    try:
        from crawler.crawler import crawl
        logger.info(f"[Celery] Starting crawl: {start_url} (project {project_id})")
        crawl(start_url=start_url, project_id=project_id, scope=scope, use_llm=use_llm)
        logger.info(f"[Celery] Crawl complete for project {project_id}")
        return f"Crawl completed for project {project_id}"
    except Exception as exc:
        logger.error(f"[Celery] Crawl failed for project {project_id}: {exc}")
        raise self.retry(exc=exc)
