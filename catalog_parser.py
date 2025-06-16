# https://rusneb.ru/local/tools/exalead/getFiles.php?book_id=000200_000018_RU_NLR_BIBL_A_012520083

# https://rusneb.ru/catalog/000200_000018_RU_NLR_DRGNLR_3107/?volumes=page-1

# <div class="cards-results__item">
#                             <a class="cards-results__link search-result__content-main-read-button search-result__content-main-read-button__read pull-right" href="/catalog/000200_000018_RU_NLR_BIBL_A_012520083" title="Открыть">
#                                 Открыть                            </a>
#                                                     </div>

# 000200_000018_RU_NLR_DRGNLR_3107

from typing import List, Dict
from bs4 import BeautifulSoup
import asyncio

import httpx

from client_manager import ClientManager


def parse_catalog_page(html_content: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html_content, "html.parser")
    items = []
    for card in soup.select(".cards-results__item"):
        link = card.select_one("a.cards-results__link")
        if link:
            href = link.get("href", "")
            if href is not None:
                href = href.split("/catalog/")[1]
                items.append(href)

    return items


async def fetch_catalogs(client: httpx.AsyncClient, catalog_id: str):
    url = f"https://rusneb.ru/catalog/{catalog_id}/?volumes=page-"
    current_page = 1
    while True:
        response = await client.get(f"{url}{current_page}")
        if response.status_code != 200:
            break
        html_content = response.text
        items = parse_catalog_page(html_content)
        if not items:
            break
        for item in items:
            yield item
        current_page += 1


async def process_catalogs(client_manager: ClientManager, catalog_id: str):
    counter = 0
    async with client_manager.get_client() as client:
        async for item in fetch_catalogs(client, catalog_id):
            counter += 1
            print(f"Item {counter}: {item}")
    print(f"Total items found: {counter}")


if __name__ == "__main__":
    catalog_id = "000200_000018_RU_NLR_DRGNLR_3107"
    client_manager = ClientManager()
    asyncio.run(process_catalogs(client_manager, catalog_id))
