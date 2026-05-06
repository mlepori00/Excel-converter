import sys, asyncio, json
asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
from scrapling.fetchers import StealthyFetcher

# Use German locale for CHF prices
page = StealthyFetcher.fetch(
    'https://www.galaxus.ch/de/s8/search?q=190665668964',
    headless=True, network_idle=True
)
print('URL:', page.url)

for script in page.css('script[type="application/ld+json"]'):
    try:
        data = json.loads(script.text)
        if data.get('@type') == 'Product':
            print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception:
        pass
