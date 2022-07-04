#!/usr/bin/env python

import json
from collections import defaultdict
from urllib.parse import urljoin

import httpx
import trio
from bs4 import BeautifulSoup
from tqdm import tqdm

BASE_URL = "https://guix.gnu.org"


def parse_section_links(page):
    return [
        (page_link.get_text(), page_link['href'])
        for page_link in page.find("section", class_="letter-selector").find(
                "div", class_="selector-box-padded"
        ).find_all("a")
    ]


async def get_bs4(client, url):
    return BeautifulSoup((await client.get(url)).content, 'html.parser')

async def get_landing_page(client):
    return await get_bs4(client, urljoin(BASE_URL, "/en/packages/"))

def parse_sub_links(page):
    return [(link.get_text(), link['href']) for link in page.find_all("a")]

def parse_page_nav(page):
    return parse_sub_links(page.find_all("nav", class_="page-selector")[0])

def parse_packages(page):
    return [
        {
            "title": title[0].get_text() if (title := link.find_all("h3", "item-summary")) else link.get_text(),
            "description": desc[0].get_text() if (desc := link.find_all("p", "item-summary")) else "",
            "link": link['href'],
        }
    for link in page.find("section", class_="page").find("div", class_="sheet").find_all("a", recursive=False)
    ]

async def get_section_page(client, section, page, path, report_channel):
    async with report_channel:
        data = parse_packages(await get_bs4(client, urljoin(BASE_URL, path)))
        await report_channel.send((section, page, data))

async def get_section(client, section, sub_path, report_channel):
    async with report_channel:
        page1 = await get_bs4(client, urljoin(BASE_URL, sub_path))
        section_nav = parse_page_nav(page1)
        await report_channel.send((section, 1, parse_packages(page1)))
        async with trio.open_nursery() as nursery:
            for page, link in section_nav:
                if int(page) == 1:
                    continue
                nursery.start_soon(get_section_page, client, section, page, link, report_channel.clone())

async def reporter(data_channel):
    data = defaultdict(dict)
    async with data_channel:
        async for (section, page, packages) in data_channel:
            data[section][page] = packages

    with open("data.json", "w+") as data_file:
        json.dump(dict(data), data_file)

async def amain():
    async with httpx.AsyncClient() as client:
        async with trio.open_nursery() as nursery:
            report_channel, receive_channel = trio.open_memory_channel(0)
            async with report_channel, receive_channel:
                landing_page = await get_landing_page(client)
                for section_link in parse_section_links(landing_page):
                    nursery.start_soon(get_section, client, *section_link, report_channel.clone())
                nursery.start_soon(reporter, receive_channel.clone())

def main():
    # from time import sleep
    # for char in tqdm(["a", "b", "c", "d"], position=0):
    #     sleep(0.25)
    #     for char2 in tqdm(["a", "b", "c", "d"], leave=char=="d", position=1):
    #         sleep(0.25)

    # from time import sleep

    # from tqdm.auto import trange

    # for i in trange(4, desc='1st loop'):
    #     for j in trange(5, desc='2nd loop'):
    #         for k in trange(50, desc='3rd loop', leave=False):
                # sleep(0.01)
    trio.run(amain)

if __name__ == "__main__":
    main()
