import requests
import time
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

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

