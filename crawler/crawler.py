import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from core.models import Page, Project
from analyzer.analyzer import run_analyzer

def normalize_url(base_url, link):
    full_url = urljoin(base_url, link)
    if '#' in full_url:
        full_url = full_url.split('#')[0]
    if full_url.endswith('/') and full_url.count('/') > 3:
        full_url = full_url.rstrip('/')
    return full_url

def is_valid_url(url, domain):
    parsed = urlparse(url)
    url_domain = parsed.netloc
    domain_normalized = domain.replace('www.', '')
    url_domain_normalized = url_domain.replace('www.', '')
    return url_domain_normalized == domain_normalized

def crawl(start_url, project_id=None, max_pages=10, domain_only=True):
    visited = set()
    queue = [start_url]
    queued = set([start_url])
    domain = urlparse(start_url).netloc
    print(f"Starting crawl for domain: {domain}")
    print(f"Domain only mode: {domain_only}")
    print(f"Max pages: {max_pages}")
    if project_id:
        proj = Project.objects.get(id=project_id)
    else:
        proj, created = Project.objects.get_or_create(domain=start_url, defaults={"wcag_level": "A", "status": "pending"})
    proj.total_pages = max_pages
    proj.status = "crawling"
    proj.save()
    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        proj.current_page = url
        proj.pages_crawled = len(visited)
        proj.save()
        print(f"crawling now: {url} ({len(visited)}/{max_pages})")
        try:
            resp = requests.get(url, timeout=10)
            html = resp.text
            existing_page = Page.objects.filter(project=proj, url=url).first()
            if existing_page:
                existing_page.html_snapshot = html
                existing_page.status = "pending"
                existing_page.save()
                pg = existing_page
            else:
                pg = Page.objects.create(project=proj, url=url, html_snapshot=html, status="pending")
            try:
                run_analyzer(pg)
            except Exception as analyzer_error:
                print(f"analyzer error on {url}: {str(analyzer_error)}")
                pg.status = "error"
                pg.save()
            soup = BeautifulSoup(html, "html.parser")
            all_links = soup.find_all("a", href=True)
            links_added = 0
            for a in all_links:
                href = a["href"].strip()
                if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                    continue
                new_link = normalize_url(url, href)
                if new_link in visited or new_link in queued:
                    continue
                if domain_only:
                    if not is_valid_url(new_link, domain):
                        continue
                queue.append(new_link)
                queued.add(new_link)
                links_added += 1
            print(f"  → Added {links_added} new links to queue (total: {len(queue)})")
        except Exception as e:
            print("error on page " + url + " : " + str(e))
    proj.status = "crawled"
    proj.current_page = ""
    proj.save()
    print(f"done crawling! Visited {len(visited)} pages")
