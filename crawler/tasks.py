from celery import shared_task
from crawler.crawler import crawl

@shared_task
def crawl_website_task(start_url, project_id, max_pages, domain_only):
    crawl(start_url=start_url, project_id=project_id, max_pages=max_pages, domain_only=domain_only)
    return f"Crawl completed for project {project_id}"
