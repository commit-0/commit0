import asyncio
import os
import sys

import fitz
import requests
import yaml

from pyppeteer import launch
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from PyPDF2 import PdfMerger


def convert_to_raw_github_url(github_url):
    base_url = "https://raw.githubusercontent.com/"

    # Split the provided URL into parts
    parts = github_url.split("/")

    # Ensure the URL is of the correct form
    if not (len(parts) >= 5 and parts[2] == "github.com"):
        raise ValueError("Provided URL is not a valid GitHub URL")

    # Extract the user, repository, branch, and file path
    user = parts[3]
    repo = parts[4]
    branch = parts[6] if len(parts) > 6 else "master"
    file_path = "/".join(parts[7:])

    # Form the raw URL
    raw_url = f"{base_url}{user}/{repo}/{branch}/{file_path}"

    return raw_url


# Function to clean PDFs
def is_page_blank(page) -> bool:
    text = page.get_text("text")
    return not text.strip()


def remove_blank_pages(pdf_path) -> None:
    document = fitz.open(pdf_path)
    if document.page_count < 2:
        print(f"No empty page to remove in {pdf_path}")
        return

    output_document = fitz.open()
    for i in range(document.page_count):
        page = document.load_page(i)
        if not is_page_blank(page):
            output_document.insert_pdf(document, from_page=i, to_page=i)

    output_document.save(pdf_path)
    output_document.close()
    document.close()
    print(f"Saved PDF without blank pages: {pdf_path}")


def clean_pdf_directory(docs) -> None:
    for doc in docs:
        remove_blank_pages(doc)


async def generate_pdf(page, url, output_dir):
    try:
        await page.goto(url, {"waitUntil": "networkidle2"})

        out_name = f"{urlparse(url).path.replace('/', '_').strip('_')}.pdf"
        if out_name == ".pdf":
            out_name = "base.pdf"
        pdf_path = os.path.join(output_dir, out_name)

        pdf_options = {
            "path": pdf_path,
            "printBackground": True,
            "format": "A4",
            "margin": {
                "top": "0px",
                "bottom": "0px",
                "left": "0px",
                "right": "0px",
            },
        }

        await page.pdf(pdf_options)
        print(f"Saved PDF: {pdf_path}")
    except Exception as e:
        print(f"Error creating PDF for {url}: {e}")
    return pdf_path


def is_valid_link(link, base_url):
    parsed_url = urlparse(link)
    # this is section title, not actual webpage
    if parsed_url.fragment:
        return None
    if not parsed_url.scheme:
        return urljoin(base_url, link)
    if parsed_url.netloc == urlparse(base_url).netloc:
        return link
    return None


async def crawl_website(browser, base_url, output_dir):
    page = await browser.newPage()
    visited = set()
    to_visit = [base_url]
    sequence = []

    while to_visit:
        current_url = to_visit.pop(0)
        if "pydantic" in base_url:
            if (
                "changelog" in current_url
                or "people" in current_url
                or "integrations" in current_url
                or "migration" in current_url
                or "why" in current_url
            ):
                continue
        elif "fastapi" in base_url:
            if "changelog" in current_url or "people" in current_url:
                continue
            splitted = current_url.replace("https://", "")
            splitted = [x for x in splitted.split("/") if x != ""]
            # this is doc in another language..
            if len(splitted) > 1 and splitted[1] in [
                "az",
                "bn",
                "de",
                "es",
                "fa",
                "fr",
                "he",
                "hu",
                "id",
                "it",
                "ja",
                "ko",
                "pl",
                "pt",
                "ru",
                "tr",
                "uk",
                "ur",
                "vi",
                "yo",
                "zh",
                "zh-hant",
                "em",
                "?q=",
            ]:
                print(f"Skip URL: {current_url}")
                continue
        elif "seaborn" in base_url:
            if ".png" in current_url:
                continue
        if current_url in visited:
            continue

        print(f"Crawling URL: {current_url}")
        visited.add(current_url)
        try:
            response = await page.goto(current_url, {"waitUntil": "domcontentloaded"})
            if response.status == 404:
                print(f"404 Not Found: {current_url}")
                continue
            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")

            links = soup.find_all("a", href=True)
            for link in links:
                full_url = is_valid_link(link["href"], base_url)
                if (
                    full_url
                    and full_url not in visited
                    and full_url.startswith(base_url)
                ):
                    to_visit.append(full_url)

            pdf = await generate_pdf(page, current_url, output_dir)
            sequence.append(pdf)
        except Exception as e:
            print(f"Error crawling {current_url}: {e}")
    return sequence


def merge_pdfs(docs, output_filename) -> None:
    merger = PdfMerger()
    for pdf in docs:
        merger.append(pdf)
    merger.write(output_filename)
    merger.close()


async def scrape_spec(base_url, output_dir, name) -> None:
    output_dir = os.path.join("pdfs", name)
    # the link is already a PDF
    splitted = [x for x in base_url.split("/") if x != ""]
    if splitted[-1] == "pdf":
        response = requests.get(base_url)
        with open(os.path.join("pdfs", f"{name}.pdf"), "wb") as pdf_file:
            pdf_file.write(response.content)
        return
    browser = await launch(args=["--no-sandbox"])
    os.makedirs(output_dir, exist_ok=True)
    pdfs = await crawl_website(browser, base_url, output_dir)
    await browser.close()

    # Clean the generated PDFs to remove any blank pages
    clean_pdf_directory(pdfs)
    # merge all pdfs together
    merge_pdfs(pdfs, os.path.join("pdfs", f"{name}.pdf"))


def main():
    with open(sys.argv[1], "r") as f:
        ds = yaml.safe_load(f)
    for idx, one in ds.items():
        base_url = one["specification"]
        lib_name = one["name"].split("/")[-1]
        os.makedirs(output_dir, exist_ok=True)
        asyncio.get_event_loop().run_until_complete(
            scrape_spec(base_url, "pdfs", lib_name)
        )
        print("Done:", one["name"])


if __name__ == "__main__":
    main()
