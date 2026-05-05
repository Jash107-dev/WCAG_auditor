import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from core.models import Page, Project
from analyzer.analyzer import run_analyzer


def normalize_url(base_url, link):
    full_url = urljoin(base_url, link)
    return full_url


def is_valid_url(url, domain):
    parsed = urlparse(url)
    return parsed.netloc == domain


def crawl(start_url, project_id=None, max_pages=10, domain_only=True):

    visited = set()
    queue = [start_url]
    domain = urlparse(start_url).netloc

    if project_id:
        proj = Project.objects.get(id=project_id)
    else:
        proj, created = Project.objects.get_or_create(
            domain=start_url,
            defaults={"wcag_level": "A", "status": "pending"}
        )

    while queue and len(visited) < max_pages:
        url = queue.pop(0)

        if url in visited:
            continue

        visited.add(url)
        print("crawling now: " + url)

        try:
            resp = requests.get(url, timeout=5)
            html = resp.text

            existing_page = Page.objects.filter(project=proj, url=url).first()

            if existing_page:
                existing_page.html_snapshot = html
                existing_page.status = "pending"
                existing_page.save()
                pg = existing_page
            else:
                pg = Page.objects.create(
                    project=proj,
                    url=url,
                    html_snapshot=html,
                    status="pending"
                )

            run_analyzer(pg)

            soup = BeautifulSoup(html, "html.parser")
            all_links = soup.find_all("a", href=True)

            for a in all_links:
                new_link = normalize_url(url, a["href"])
                if new_link in visited:
                    continue
                if domain_only and not is_valid_url(new_link, domain):
                    continue
                queue.append(new_link)

        except Exception as e:
            print("error on page " + url + " : " + str(e))

    proj.status = "crawled"
    proj.save()
    print("done crawling!")
