import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
import random
from bs4 import BeautifulSoup
import httpx

# BROWSER_HEADERS_LIST = [
#     # Chrome on Windows
#     {
#         'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.112 Safari/537.36',
#         'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
#         'Accept-Language': 'en-US,en;q=0.9',
#         'Accept-Encoding': 'gzip, deflate, br',
#         'Connection': 'keep-alive',
#         'Upgrade-Insecure-Requests': '1',
#         'Sec-Fetch-Site': 'none',
#         'Sec-Fetch-Mode': 'navigate',
#         'Sec-Fetch-User': '?1',
#         'Sec-Fetch-Dest': 'document',
#         'Referer': '',
#         'Origin': '',
#     },

#     # Firefox on Windows
#     {
#         'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
#         'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
#         'Accept-Language': 'en-US,en;q=0.5',
#         'Accept-Encoding': 'gzip, deflate, br',
#         'Connection': 'keep-alive',
#         'Upgrade-Insecure-Requests': '1',
#         'Sec-Fetch-Dest': 'document',
#         'Sec-Fetch-Mode': 'navigate',
#         'Sec-Fetch-Site': 'none',
#         'Sec-Fetch-User': '?1',
#         'Referer': '',
#         'Origin': '',
#     },

#     # Safari on macOS
#     {
#         'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
#         'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
#         'Accept-Language': 'en-us',
#         'Connection': 'keep-alive',
#         'Upgrade-Insecure-Requests': '1',
#         'Referer': '',
#         'Origin': '',
#     },

#     # Edge on Windows
#     {
#         'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.112 Safari/537.36 Edg/125.0.2535.67',
#         'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
#         'Accept-Language': 'en-US,en;q=0.9',
#         'Accept-Encoding': 'gzip, deflate, br',
#         'Connection': 'keep-alive',
#         'Upgrade-Insecure-Requests': '1',
#         'Sec-Fetch-Site': 'none',
#         'Sec-Fetch-Mode': 'navigate',
#         'Sec-Fetch-User': '?1',
#         'Sec-Fetch-Dest': 'document',
#         'Referer': '',
#         'Origin': '',
#     },
# ]


# def get_base_url(url):
#     parsed = urlparse(url)
#     return f"{parsed.scheme}://{parsed.netloc}/"

# url = "https://menuchapublishers.com/products/living-inspired"
# headers = BROWSER_HEADERS_LIST[2]
# headers['Referer'] = get_base_url(url)
# headers['Origin'] = get_base_url(url)
# page = requests.get(url, headers=headers, timeout=30)
# page.raise_for_status()
# soup = BeautifulSoup(page.content, 'html.parser')

# # Extract product data
# price = soup.select_one('.price')
# price_text = price.text.strip() if price else None

# sku = soup.find('td', id='isbn')
# sku_text = sku.text.strip() if sku else None

# author_tag = soup.select_one('div.spec-author-prd a.spec-authors')
# author = author_tag.text.strip() if author_tag else None

# description_div = soup.select_one('div.product-description-full')
# full_description = description_div.text.strip() if description_div else None

# page = requests.get(url, headers=headers, timeout=30)
# # page.raise_for_status()

# soup = BeautifulSoup(page, 'html.parser')
# print(soup.title.text if soup.title else "No title found")
# price = soup.select_one('.price')
# price_text = price.text.strip() if price else None

# sku = soup.find('td', id='isbn')
# sku_text = sku.text.strip() if sku else None

# author_tag = soup.select_one('div.spec-author-prd a.spec-authors')
# author = author_tag.text.strip() if author_tag else None

# description_div = soup.select_one('div.product-description-full')
# paragraphs = description_div.find_all('p')
# full_description = ' '.join(p.get_text(separator=' ', strip=True) for p in paragraphs)

# print(price_text, sku_text, author, full_description)
# def get_base_url(url):
#     parsed = urlparse(url)
#     return f"{parsed.scheme}://{parsed.netloc}/"
# Header = BROWSER_HEADERS_LIST[0] #0,1
# Header['Origin'] = get_base_url(
#     "https://feldart.com/products/hadlakos-neiros-artwork-card"
# )
# Header['Referer'] = get_base_url("" \
# "https://feldart.com/products/hadlakos-neiros-artwork-card")
# page = requests.get("https://feldart.com/products/hadlakos-neiros-artwork-card", headers=Header, timeout=30)
# page.raise_for_status()
# if page.headers.get('Content-Encoding') in ['br', 'gzip', 'deflate']:
#     page.encoding = 'utf-8'  # Force correct decoding
# html = page.text
# print(html)
# soup = BeautifulSoup(html, 'html.parser')

# Extract product data
# price = soup.select_one('sale-price')
# price_text = price.get_text(strip=True).replace('Sale price', '').strip() if price else None

# # SKU
# sku = soup.select_one('variant-sku')
# sku_text = sku.get_text(strip=True).replace('SKU:', '').strip() if sku else None

# print(price_text, sku_text, description_text, description_text2)
# Constantsimport requests
# import requests
# import xml.etree.ElementTree as ET

# SITEMAP_URL = "https://waterdalecollection.com/sitemap_products_1.xml?from=776755019891&to=9973389459744"
# PRODUCT_URL_PREFIX = "https://waterdalecollection.com/products"

# # Namespaces for XML parsing
# ns = {
#     'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
#     'image': 'http://www.google.com/schemas/sitemap-image/1.1'
# }

# # Step 1: Fetch and parse XML
# response = requests.get(SITEMAP_URL)
# response.raise_for_status()
# root = ET.fromstring(response.content)

# # Step 2: Extract product info
# product_data = []
# for url in root.findall('ns:url', ns):
#     loc = url.find('ns:loc', ns)
    
#     # Filter by desired product URL prefix
#     if loc is not None and loc.text.startswith(PRODUCT_URL_PREFIX):
#         image_loc = url.find('image:image/image:loc', ns)
#         image_title = url.find('image:image/image:title', ns)

#         product_data.append({
#             'product_url': loc.text,
#             'image_url': image_loc.text if image_loc is not None else None,
#             'image_title': image_title.text if image_title is not None else None
#         })

# # Optional: Preview first few results
# for product in product_data[:5]:
#     print(product)
# def load_simchonim_sitemap_product_urls():
#     url = "https://simchonim.com/product-sitemap.xml"
#     response = requests.get(url)
    
#     if response.status_code != 200:
#         print(f"Failed to fetch sitemap: {response.status_code}")
#         return []

#     # Parse HTML content since it's in HTML format with table rows
#     soup = BeautifulSoup(response.content, 'xml')
    
#     # Find all links in table rows
#     product_links = []
#     table_rows = soup.find_all('tr')
    
#     for idx, row in enumerate(table_rows):
#         # Skip the first row/link as requested
#         if idx == 0:
#             continue
            
#         # Find anchor tag in the row
#         link_elem = row.find('a')
#         if link_elem and link_elem.get('href'):
#             product_links.append(link_elem.get('href'))
    
#     return product_links
import requests
from bs4 import BeautifulSoup

def load_meiros_sitemap_product_urls():
    url = "https://meiros.com/wp-sitemap-posts-product-1.xml"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Failed to fetch sitemap: {response.status_code}")
        return []

    soup = BeautifulSoup(response.content, 'xml')  # Proper XML parser
    links = [loc.text for loc in soup.find_all('loc')]
    return links


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

# print(load_legacyjudaica_sitemap_product_urls())
# print(load_meiros_sitemap_product_urls())
print(load_simchonim_sitemap_product_urls())