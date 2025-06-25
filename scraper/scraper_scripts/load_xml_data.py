import requests
import time
import xml.etree.ElementTree as ET
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

