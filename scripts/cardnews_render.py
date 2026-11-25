"""카드 HTML(card-1~5.html)을 크롬으로 찍어 같은 이름의 PNG로 저장.

사용: python scripts/cardnews_render.py <폴더> [크롬 경로]
"""
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright


async def main(folder: Path, chrome: str | None):
    async with async_playwright() as p:
        kw = {"args": ["--no-sandbox"]}
        if chrome:
            kw["executable_path"] = chrome
        b = await p.chromium.launch(**kw)
        pg = await b.new_page(viewport={"width": 1080, "height": 800}, device_scale_factor=1)
        for f in sorted(folder.glob("card-*.html")):
            await pg.goto(f.resolve().as_uri())
            await pg.wait_for_timeout(400)
            el = await pg.query_selector("body > *")
            await el.screenshot(path=str(f.with_suffix(".png")))
            print(f.name, await el.bounding_box())
        await b.close()


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else None))
