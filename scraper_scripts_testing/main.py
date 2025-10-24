import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

# def grab_product_urls():
#     base_url = "https://ritelite.com"
#     page_url = "https://ritelite.com/Products/Listings/Season/?pgsize=All"

#     # Fetch page
#     response = requests.get(page_url)
#     response.raise_for_status()  # Raise error if failed

#     # Parse HTML
#     soup = BeautifulSoup(response.text, "html.parser")

#     # Find the UL containing product cards
#     ul = soup.find("ul", class_="thumbnails row")
#     if not ul:
#         print("No product list found.")
#         return []

#     urls = []
#     for li in ul.find_all("li", class_="span3 plist itemcart"):
#         # Find the anchor tag with product link
#         a_tag = li.find("a", href=True)
#         if a_tag:
#             href = a_tag["href"]
#             # Format: replace the double slash with '/Category/'
#             formatted_href = href.replace("//", "/Category/", 1)
#             full_url = base_url + formatted_href
#             urls.append(full_url)

#     return urls

def get_zionjudaica_urls():
    sitemap_urls = [
        "https://zionjudaica.com/product-sitemap.xml",
        "https://zionjudaica.com/product-sitemap2.xml",
        "https://zionjudaica.com/product-sitemap3.xml",
    ]
    
    all_urls = []

    for sitemap in sitemap_urls:
        try:
            response = requests.get(sitemap, timeout=10)
            response.raise_for_status()

            root = ET.fromstring(response.content)
            
            for url_tag in root.findall(".//{*}url/{*}loc"):
                url = url_tag.text.strip()

                # Skip images and unwanted URLs
                if (
                    "/shop/" not in url
                    and not url.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
                    and "/wp-content/" not in url
                ):
                    all_urls.append(url)

        except Exception as e:
            print(f"Error fetching {sitemap}: {e}")
    
    return all_urls
if __name__ == "__main__":
    urls = get_zionjudaica_urls()
    print(f"Total product URLs found: {len(urls)}")
    print(urls[:10])

    response = requests.get("https://zionjudaica.com/product/memorial-lamp-replacement-bulb-2/")
    soup = BeautifulSoup(response.content, "html.parser")
    title_tag = soup.select_one("h1.fusion-title-heading")
    title = title_tag.get_text(strip=True) if title_tag else None

    # Description
    description = ''
    desc_div = soup.select_one("#productContent p")
    description = desc_div.get_text(strip=True) if desc_div else None

    # Price
    
    
    price = (soup.select_one("p.price ins bdi") or soup.select_one("p.price bdi")).get_text(strip=True)

    # SKU
    sku_span = soup.select_one(".sku")
    sku = sku_span.get_text(strip=True) if sku_span else None

    

    # Image URL
    image_link = ''

    image = soup.select_one(".woocommerce-product-gallery__image a[href]")
    image_link = image["href"] if image else ''

    

    category = soup.select("ol.awb-breadcrumb-list li a span")[-1].get_text(strip=True)
            
    print(title, description, sku, price, category, image_link)
# if __name__ == "__main__":
#     print(load_mefoarjudaica_product_urls())
#     print(load_shaijudaica_product_urls())