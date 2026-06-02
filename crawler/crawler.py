import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from core.models import Page, Project
from analyzer.engine import analyze_page
from crawler.fetcher import fetch_page

SCOPE_SINGLE   = "single"
SCOPE_MAIN     = "main"
SCOPE_FULL     = "full"

MAX_PAGES_HARD_CAP = 500


def normalize_url(base_url, link):
    full_url = urljoin(base_url, link)
    if '#' in full_url:
        full_url = full_url.split('#')[0]
    if full_url.endswith('/') and full_url.count('/') > 3:
        full_url = full_url.rstrip('/')
    return full_url


def is_internal_url(url, domain):
    parsed = urlparse(url)
    url_domain = parsed.netloc.replace('www.', '')
    base_domain = domain.replace('www.', '')
    return url_domain == base_domain


def is_navigational_link(href):
    skip_prefixes = ('#', 'javascript:', 'mailto:', 'tel:', 'ftp:', 'data:')
    return not any(href.startswith(p) for p in skip_prefixes)


def get_main_links(start_url, html, domain):
    soup = BeautifulSoup(html, 'html.parser')
    links = set()

    for container in soup.find_all(['nav', 'header']):
        for a in container.find_all('a', href=True):
            href = a['href'].strip()
            if not href or not is_navigational_link(href):
                continue
            normalized = normalize_url(start_url, href)
            if is_internal_url(normalized, domain):
                links.add(normalized)

    if not links:
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            if not href or not is_navigational_link(href):
                continue
            normalized = normalize_url(start_url, href)
            if is_internal_url(normalized, domain):
                links.add(normalized)

    return list(links)


def crawl(start_url, project_id=None, scope=SCOPE_FULL, use_llm=False):
    if not start_url.startswith(('http://', 'https://')):
        start_url = 'https://' + start_url

    domain = urlparse(start_url).netloc
    print(f"Starting crawl | domain={domain} | scope={scope}")

    if project_id:
        proj = Project.objects.get(id=project_id)
    else:
        proj, _ = Project.objects.get_or_create(
            domain=start_url,
            defaults={"wcag_level": "AA", "status": "pending"}
        )

    proj.status = "crawling"
    proj.pages_crawled = 0
    proj.total_pages = 0
    proj.stop_requested = False
    proj.save()

    visited = set()

    if scope == SCOPE_SINGLE:
        queue = [start_url]

    elif scope == SCOPE_MAIN:
        try:
            homepage_html, _, _ = fetch_page(start_url)
        except Exception as e:
            print(f"Failed to fetch homepage: {e}")
            proj.status = "crawled"
            proj.save()
            return
        main_links = get_main_links(start_url, homepage_html, domain)
        queue = [start_url] + [l for l in main_links if l != start_url]
        print(f"Main scope: found {len(queue)} links from navigation")

    else:
        queue = [start_url]

    queued = set(queue)
    proj.total_pages = len(queue) if scope != SCOPE_FULL else MAX_PAGES_HARD_CAP
    proj.save()

    while queue:
        if scope == SCOPE_FULL and len(visited) >= MAX_PAGES_HARD_CAP:
            print(f"Reached hard cap of {MAX_PAGES_HARD_CAP} pages")
            break
        if scope in (SCOPE_SINGLE, SCOPE_MAIN) and len(visited) >= len(queued):
            break

        proj.refresh_from_db()
        if proj.stop_requested:
            print(f"Stop requested — halting crawl after {len(visited)} pages")
            proj.status = "crawled"
            proj.current_page = ""
            proj.pages_crawled = len(visited)
            proj.save()
            return

        url = queue.pop(0)
        if url in visited:
            continue

        visited.add(url)
        proj.current_page = url
        proj.pages_crawled = len(visited)
        proj.total_pages = max(proj.total_pages, len(visited) + len(queue))
        proj.save()

        print(f"Crawling ({len(visited)}): {url}")

        try:
            html, fetch_method, http_status = fetch_page(url)
            print(f"  Fetched via {fetch_method} ({len(html)} chars) [HTTP {http_status}]")

            pg, created = Page.objects.update_or_create(
                project=proj, url=url,
                defaults={"html_snapshot": html, "status": "pending", "llm_status": "pending", "http_status": http_status}
            )

            try:
                analyze_page(pg.id, use_llm=use_llm)
            except Exception as e:
                print(f"  Analysis error on {url}: {e}")
                pg.status = "error"
                pg.save()

            if scope == SCOPE_FULL:
                soup = BeautifulSoup(html, "html.parser")
                added = 0
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    if not href or not is_navigational_link(href):
                        continue
                    new_link = normalize_url(url, href)
                    if new_link in visited or new_link in queued:
                        continue
                    if not is_internal_url(new_link, domain):
                        continue
                    queue.append(new_link)
                    queued.add(new_link)
                    added += 1
                if added:
                    print(f"  → Discovered {added} new links are (queue: {len(queue)})")

        except Exception as e:
            print(f"  Error fetching {url}: {e}")

    proj.status = "crawled"
    proj.current_page = ""
    proj.pages_crawled = len(visited)
    proj.save()
    print(f"Crawl complete. Visited {len(visited)} pages.")
