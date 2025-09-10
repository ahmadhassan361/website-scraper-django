import requests
import time
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import random
import os
from urllib.parse import urljoin

def load_kaftorjudaica_product_urls():
    BASE_URL = "https://www.kaftorjudaica.com/"
    products = []
    url = "https://www.kaftorjudaica.com/search.asp?Keyword=a&image1.x=0&image1.y=0&pg=1"

    while url:
        print(f"Scraping {url}")
        r = requests.get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Find the main product table (fixed width = 765)
        main_table = soup.find("table", {"width": "765"})
        if not main_table:
            print("No product table found")
            break

        # Collect product images, titles, SKUs, prices
        # Each row group is: images row -> titles row -> SKU row -> prices row
        rows = main_table.find_all("tr", recursive=False)
        
        # We skip the first tr (it has pagination at top), then process in sets of 4 rows
        for i in range(1, len(rows), 4):
            try:
                img_row = rows[i]
                title_row = rows[i+1]
                sku_row = rows[i+2]
                price_row = rows[i+3]
            except IndexError:
                break

            img_cells = img_row.find_all("td", width="182")
            title_cells = title_row.find_all("td", width="182")
            sku_cells = sku_row.find_all("td", width="182")
            price_cells = price_row.find_all("td", width="182")

            for j in range(len(img_cells)):
                product = {}

                # image + link
                img_tag = img_cells[j].find("img")
                a_tag = img_cells[j].find("a")
                if img_tag:
                    product["image"] = urljoin(BASE_URL, img_tag["src"])
                if a_tag:
                    product["link"] = urljoin(BASE_URL, a_tag["href"])

                # title
                if j < len(title_cells):
                    product["title"] = title_cells[j].get_text(strip=True)

                # sku
                if j < len(sku_cells):
                    product["sku"] = sku_cells[j].get_text(strip=True)

                # price
                if j < len(price_cells):
                    price_text = price_cells[j].get_text(" ", strip=True)
                    if "Our Price:" in price_text:
                        product["price"] = price_text.split("Our Price:")[-1].strip()
                    else:
                        product["price"] = None

                products.append(product)

        # find next page link
        next_link = main_table.find("a", string=">>")
        if next_link:
            url = urljoin(BASE_URL, next_link["href"])
        else:
            url = None

    return products

def load_craftsandmore_product_urls():
    """
    Load links from the craftsandmore.txt file into a Python list.
    """
    base_dir = os.path.dirname(__file__)  # directory of load_xml_data.py
    file_path = os.path.join(base_dir, "craftsandmore.txt")

    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def load_mefoarjudaica_product_urls():
    product_links = []

    # Step 1: Fetch main sitemap
    response = requests.get("https://mefoarjudaica.com/sitemap/categories")
    soup = BeautifulSoup(response.content, "html.parser")

    # Find the "Categories" section
    categories_h2 = soup.find("h3", string="Categories")
    categories_ul = categories_h2.find_next("ul")

    category_links = []
    for li in categories_ul.find_all("li", recursive=False):  # only top-level li
        a = li.find("a", recursive=False)
        if a:
            category_links.append(a["href"])

    # Step 2: Iterate over category links
    print(category_links)
    for category_url in category_links:
        next_page = category_url

        while next_page:
            print(len(product_links))
            # Sleep before request (1–3 seconds random)
            time.sleep(random.uniform(1, 3))

            res = requests.get(next_page)
            soup_obj = BeautifulSoup(res.content, "html.parser")

            # Grab all products on this page
            # Grab all products on this page
            products = soup_obj.select("div.prod-item")
            for product in products:
                a_tag = product.select_one("h4.prod-name a")
                if a_tag and "href" in a_tag.attrs:
                    product_links.append(a_tag["href"])


            # Find next page
            li = soup_obj.find("li", class_="pagination-item pagination-item--next")
            if li:
                a = li.find("a")
                if a and "href" in a.attrs:
                    next_page = a["href"]
                else:
                    next_page = None
            else:
                next_page = None

    return product_links

def load_ozvehadar_product_urls():
    product_links = []

    # Step 1: Fetch main sitemap
    response = requests.get("https://ozvehadar.us/sitemap/categories")
    soup = BeautifulSoup(response.content, "html.parser")

    # Find the "Categories" section
    categories_h2 = soup.find("h2", string="Categories")
    categories_ul = categories_h2.find_next("ul")

    category_links = []
    for li in categories_ul.find_all("li", recursive=False):  # only top-level li
        a = li.find("a", recursive=False)
        if a:
            category_links.append(a["href"])

    # Step 2: Iterate over category links
    for category_url in category_links:
        next_page = category_url

        while next_page:
            # Sleep before request (1–3 seconds random)
            time.sleep(random.uniform(1, 3))

            res = requests.get(next_page)
            soup_obj = BeautifulSoup(res.content, "html.parser")

            # Grab all products on this page
            products = soup_obj.select("ul.productGrid li.product")
            for product in products:
                a_tag = product.select_one("h3.card-title a")
                if a_tag and "href" in a_tag.attrs:
                    product_links.append(a_tag["href"])

            # Find next page
            li = soup_obj.find("li", class_="pagination-item pagination-item--next")
            if li:
                a = li.find("a")
                if a and "href" in a.attrs:
                    next_page = a["href"]
                else:
                    next_page = None
            else:
                next_page = None

    return product_links


def load_shaijudaica_product_urls():
    namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    items_links = []

    # Step 1: Fetch main sitemap
    response = requests.get("https://www.shaijudaica.co.il/sitemap.xml")
    response.raise_for_status()
    root = ET.fromstring(response.content)

    # Step 2: Extract sub-sitemap URLs
    sitemap_links = [loc.text for loc in root.findall('.//ns:loc', namespace)]

    # Step 3: Fetch each sub-sitemap and extract item links
    for sitemap_url in sitemap_links:
        sub_resp = requests.get(sitemap_url)
        sub_resp.raise_for_status()
        sub_root = ET.fromstring(sub_resp.content)
        
        for loc in sub_root.findall('.//ns:loc', namespace):
            url = loc.text.strip()
            if url.startswith("https://www.shaijudaica.co.il/items"):
                items_links.append(url)

    return items_links




def load_ritelite_product_urls():
    base_url = "https://ritelite.com"
    page_url = "https://ritelite.com/Products/Listings/Season/?pgsize=All"

    # Fetch page
    response = requests.get(page_url)
    response.raise_for_status()  # Raise error if failed

    # Parse HTML
    soup = BeautifulSoup(response.text, "html.parser")

    # Find the UL containing product cards
    ul = soup.find("ul", class_="thumbnails row")
    if not ul:
        print("No product list found.")
        return []

    urls = []
    for li in ul.find_all("li", class_="span3 plist itemcart"):
        # Find the anchor tag with product link
        a_tag = li.find("a", href=True)
        if a_tag:
            href = a_tag["href"]
            # Format: replace the double slash with '/Category/'
            formatted_href = href.replace("//", "/Category/", 1)
            full_url = base_url + formatted_href
            urls.append(full_url)

    return urls

def load_meiros_sitemap_product_urls():
    url = "https://meiros.com/wp-sitemap-posts-product-1.xml"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Failed to fetch sitemap: {response.status_code}")
        return []

    soup = BeautifulSoup(response.content, 'xml')  # Proper XML parser
    links = [loc.text for loc in soup.find_all('loc')]
    return links
def load_jewisheducationaltoys_sitemap_product_urls():
    url = "https://www.jewisheducationaltoys.com/sitemap.xml"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Failed to fetch sitemap: {response.status_code}")
        return []

    soup = BeautifulSoup(response.content, 'xml')  # Proper XML parser
    links = [loc.text for loc in soup.find_all('loc')]
    filtered_links = [link for link in links if 'https://www.jewisheducationaltoys.com/JET' in link]
    return filtered_links


def load_legacyjudaica_sitemap_product_urls():
    url = "https://legacyjudaica.com/sitemap.xml"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Failed to fetch sitemap: {response.status_code}")
        return []

    soup = BeautifulSoup(response.content, 'xml')
    all_links = [loc.text for loc in soup.find_all('loc')]

    # Filter to get only product URLs (after the specified URL pattern)
    product_links = []
    start_collecting = False

    for link in all_links:
        if 's452-hamsa-copy' in link or start_collecting:
            start_collecting = True
            if '/s' in link and '-' in link.split('/')[-1]:
                product_links.append(link)

    return product_links


def load_simchonim_sitemap_product_urls():
    url = "https://simchonim.com/product-sitemap.xml"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Failed to fetch sitemap: {response.status_code}")
        return []

    soup = BeautifulSoup(response.content, 'xml')

    product_links = []
    for url_tag in soup.find_all('url'):
        loc = url_tag.find('loc')
        if loc:
            product_links.append(loc.text.strip())

    return product_links

