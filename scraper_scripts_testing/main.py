import requests
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
HEADERS = {'User-Agent': 'Mozilla/5.0'}

page = requests.get("https://malchutjudaica.com/products/poly-cotton-kids-round-neck-1-hole-ashkenaz-tzitzis", headers=HEADERS, timeout=30)
page.raise_for_status()
soup = BeautifulSoup(page.content, 'html.parser')

# Extract product data
price = soup.select_one('sale-price')
price_text = price.get_text(strip=True).replace('Sale price', '').strip() if price else None

# SKU
sku = soup.select_one('variant-sku')
sku_text = sku.get_text(strip=True).replace('SKU:', '').strip() if sku else None

description_div = soup.select_one('div.product-info__description .prose')
description_text = description_div.get_text(separator=' ', strip=True) if description_div else None

print(price_text, sku_text, description_text)
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
