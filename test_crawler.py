import requests
from bs4 import BeautifulSoup

test_urls = [
    "https://results.eci.gov.in/ResultAcGenMay2026/",
    "https://www.python.org",
    "https://example.com",
    "https://www.w3.org"
]

for url in test_urls:
    print(f"\n{'='*60}")
    print(f"Testing: {url}")
    print('='*60)
    try:
        resp = requests.get(url, timeout=10)
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        all_links = soup.find_all("a", href=True)
        print(f"Total <a> tags with href: {len(all_links)}")
        if len(all_links) > 0:
            print(f"First 3 links:")
            for i, a in enumerate(all_links[:3]):
                href = a["href"]
                print(f"  {i+1}. {href}")
    except Exception as e:
        print(f"Error: {e}")
