import requests
import time
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

# load products waterdale collection
def load_waterdalecollection_xml_sitemap():
    # Constants
    SITEMAP_URL = "https://waterdalecollection.com/sitemap_products_1.xml?from=776755019891&to=9973389459744"
    PRODUCT_URL_PREFIX = "https://waterdalecollection.com/products"
    
    # Namespaces for XML parsing
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'image': 'http://www.google.com/schemas/sitemap-image/1.1'
    }

    # Step 1: Fetch and parse XML
    response = requests.get(SITEMAP_URL)
    response.raise_for_status()
    root = ET.fromstring(response.content)

    # Step 2: Extract product info
    product_data = []
    for url in root.findall('ns:url', ns):
        loc = url.find('ns:loc', ns)
        
        # Filter by desired product URL prefix
        if loc is not None and loc.text.startswith(PRODUCT_URL_PREFIX):
            image_loc = url.find('image:image/image:loc', ns)
            image_title = url.find('image:image/image:title', ns)

            product_data.append({
                'product_url': loc.text,
                'image_url': image_loc.text if image_loc is not None else None,
                'image_title': image_title.text if image_title is not None else None
            })
    print(f"Found {len(product_data)} product URLs")

    return product_data

# load products btshalom
def load_btshalom_xml_sitemap():
    # Constants
    SITEMAP_URL = "https://btshalom.com/sitemap_products_1.xml?from=6610093211810&to=8858920321242"
    PRODUCT_URL_PREFIX = "https://btshalom.com/products"
    
    # Namespaces for XML parsing
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'image': 'http://www.google.com/schemas/sitemap-image/1.1'
    }

    # Step 1: Fetch and parse XML
    response = requests.get(SITEMAP_URL)
    response.raise_for_status()
    root = ET.fromstring(response.content)

    # Step 2: Extract product info
    product_data = []
    for url in root.findall('ns:url', ns):
        loc = url.find('ns:loc', ns)
        
        # Filter by desired product URL prefix
        if loc is not None and loc.text.startswith(PRODUCT_URL_PREFIX):
            image_loc = url.find('image:image/image:loc', ns)
            image_title = url.find('image:image/image:title', ns)

            product_data.append({
                'product_url': loc.text,
                'image_url': image_loc.text if image_loc is not None else None,
                'image_title': image_title.text if image_title is not None else None
            })
    print(f"Found {len(product_data)} product URLs")

    return product_data


# load products malchutjudaica
def load_malchutjudaica_xml_sitemap():
    # Constants
    SITEMAP_URL = "https://malchutjudaica.com/sitemap_products_1.xml?from=8060898836796&to=10017008648508"
    PRODUCT_URL_PREFIX = "https://malchutjudaica.com/products"
    
    # Namespaces for XML parsing
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'image': 'http://www.google.com/schemas/sitemap-image/1.1'
    }

    # Step 1: Fetch and parse XML
    response = requests.get(SITEMAP_URL)
    response.raise_for_status()
    root = ET.fromstring(response.content)

    # Step 2: Extract product info
    product_data = []
    for url in root.findall('ns:url', ns):
        loc = url.find('ns:loc', ns)
        
        # Filter by desired product URL prefix
        if loc is not None and loc.text.startswith(PRODUCT_URL_PREFIX):
            image_loc = url.find('image:image/image:loc', ns)
            image_title = url.find('image:image/image:title', ns)

            product_data.append({
                'product_url': loc.text,
                'image_url': image_loc.text if image_loc is not None else None,
                'image_title': image_title.text if image_title is not None else None
            })
    print(f"Found {len(product_data)} product URLs")

    return product_data

# feldart
def loa_feldart_xml_sitemap():
    # Constants
    SITEMAP_URL = "https://feldart.com/sitemap_products_1.xml?from=8455120978205&to=9833477046557"
    PRODUCT_URL_PREFIX = "https://feldart.com/products"
    
    # Namespaces for XML parsing
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'image': 'http://www.google.com/schemas/sitemap-image/1.1'
    }

    # Step 1: Fetch and parse XML
    response = requests.get(SITEMAP_URL)
    response.raise_for_status()
    root = ET.fromstring(response.content)

    # Step 2: Extract product info
    product_data = []
    for url in root.findall('ns:url', ns):
        loc = url.find('ns:loc', ns)
        
        # Filter by desired product URL prefix
        if loc is not None and loc.text.startswith(PRODUCT_URL_PREFIX):
            image_loc = url.find('image:image/image:loc', ns)
            image_title = url.find('image:image/image:title', ns)

            product_data.append({
                'product_url': loc.text,
                'image_url': image_loc.text if image_loc is not None else None,
                'image_title': image_title.text if image_title is not None else None
            })
    print(f"Found {len(product_data)} product URLs")

    return product_data

# menuchapublishers
def loa_menuchapublishers_xml_sitemap():
    # Constants
    SITEMAP_URL = "https://menuchapublishers.com/sitemap_products_1.xml?from=2006408724580&to=8662171484388"
    PRODUCT_URL_PREFIX = "https://menuchapublishers.com/products"
    
    # Namespaces for XML parsing
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'image': 'http://www.google.com/schemas/sitemap-image/1.1'
    }

    # Step 1: Fetch and parse XML
    response = requests.get(SITEMAP_URL)
    response.raise_for_status()
    root = ET.fromstring(response.content)

    # Step 2: Extract product info
    product_data = []
    for url in root.findall('ns:url', ns):
        loc = url.find('ns:loc', ns)
        
        # Filter by desired product URL prefix
        if loc is not None and loc.text.startswith(PRODUCT_URL_PREFIX):
            image_loc = url.find('image:image/image:loc', ns)
            image_title = url.find('image:image/image:title', ns)

            product_data.append({
                'product_url': loc.text,
                'image_url': image_loc.text if image_loc is not None else None,
                'image_title': image_title.text if image_title is not None else None
            })
    print(f"Found {len(product_data)} product URLs")

    return product_data

