import requests
import time
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

# Constants
SITEMAP_URL = "https://waterdalecollection.com/sitemap_products_1.xml?from=776755019891&to=9973389459744"
PRODUCT_URL_PREFIX = "https://waterdalecollection.com/products"
HEADERS = {'User-Agent': 'Mozilla/5.0'}

def load_xml_sitemap():
    # Step 1: Download and parse XML
    response = requests.get(SITEMAP_URL)
    response.raise_for_status()

    # Parse XML with namespace
    root = ET.fromstring(response.content)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

    # Step 2: Extract product URLs
    product_links = [
        url.find('ns:loc', ns).text
        for url in root.findall('ns:url', ns)
        if url.find('ns:loc', ns) is not None and url.find('ns:loc', ns).text.startswith(PRODUCT_URL_PREFIX)
    ]

    print(f"Found {len(product_links)} product URLs")

    return product_links
