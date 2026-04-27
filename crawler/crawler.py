import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from core.models import Page, Project


def normalize_url(base_url, link):
    return urljoin(base_url, link)


def is_valid_url(url, domain):
    return urlparse(url).netloc == domain


def crawl(project_id, start_url, max_pages=10):
    project = Project.objects.get(id=project_id)
    visited_urls = set()
    domain = urlparse(start_url).netloc
    queue = [start_url]

    while queue and len(visited_urls) < max_pages:
        url = queue.pop(0)

        if url in visited_urls:
            continue

        print(f"Crawling: {url}")
        visited_urls.add(url)

        try:
            response = requests.get(url, timeout=5)

            page = Page.objects.filter(project=project, url=url).first()
            if page:
                page.html_snapshot = response.text
                page.status = "done"
                page.save()
            else:
                Page.objects.create(
                    project=project,
                    url=url,
                    html_snapshot=response.text,
                    status="done"
                )

            soup = BeautifulSoup(response.text, 'html.parser')

            for a_tag in soup.find_all('a', href=True):
                link = normalize_url(url, a_tag['href'])
                if link not in visited_urls and is_valid_url(link, domain):
                    queue.append(link)

        except Exception as e:
            print(f"Error crawling {url}: {e}")

    project.status = "crawled"
    project.save()
