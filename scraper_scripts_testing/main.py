import requests
from bs4 import BeautifulSoup

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

# # Example usage:
import requests
import time
import random
from bs4 import BeautifulSoup

# def load_shaijudaica_product_urls():
#     product_links = []

#     # Step 1: Fetch main sitemap
#     response = requests.get("https://ozvehadar.us/sitemap/categories")
#     soup = BeautifulSoup(response.content, "html.parser")

#     # Find the "Categories" section
#     categories_h2 = soup.find("h2", string="Categories")
#     categories_ul = categories_h2.find_next("ul")

#     category_links = []
#     for li in categories_ul.find_all("li", recursive=False):  # only top-level li
#         a = li.find("a", recursive=False)
#         if a:
#             category_links.append(a["href"])

#     # Step 2: Iterate over category links
#     for category_url in category_links:
#         next_page = category_url

#         while next_page:
#             # Sleep before request (1–3 seconds random)
#             time.sleep(random.uniform(1, 3))

#             res = requests.get(next_page)
#             soup_obj = BeautifulSoup(res.content, "html.parser")

#             # Grab all products on this page
#             products = soup_obj.select("ul.productGrid li.product")
#             for product in products:
#                 a_tag = product.select_one("h3.card-title a")
#                 if a_tag and "href" in a_tag.attrs:
#                     product_links.append(a_tag["href"])

#             # Find next page
#             li = soup_obj.find("li", class_="pagination-item pagination-item--next")
#             if li:
#                 a = li.find("a")
#                 if a and "href" in a.attrs:
#                     next_page = a["href"]
#                 else:
#                     next_page = None
#             else:
#                 next_page = None

#     return product_links
def extract_ozvehadar_product_info():
        """
        Extract product information from ozvehadar.us product page HTML using BeautifulSoup
        
        Args:
            soup: BeautifulSoup object of the product page
            product_url: URL of the product page
            website_name: Name of the website
            
        Returns:
            dict: Product information dictionary
        """
    # try:
        response = requests.get("https://ozvehadar.us/talmud-bavli-mesivta-shinun-blue/")
        soup = BeautifulSoup(response.content, "html.parser")
        title_tag = soup.find('h1', class_='productView-title')
        title = title_tag.get_text(strip=True) if title_tag else None

        # Description
        desc_div = soup.find(id="tab-description")
        description = desc_div.get_text(separator=' ', strip=True) if desc_div else None

        # Price
        price_span = soup.find("span", class_="price price--withoutTax")
        price = price_span.get_text(strip=True) if price_span else None

        # SKU
        sku_span = soup.find("dd", {"data-product-sku": True})
        sku = sku_span.get_text(strip=True) if sku_span else None

        # Image URL
        # From <img src="">
        image_links = set()
        image_urls  = []
        for a in soup.find_all("a", href=True):
            if a["href"].endswith((".png", ".jpg", ".jpeg", ".webp")):
                image_links.add(a["href"])

        # From <img src="">
        for img in soup.find_all("img", src=True):
            if img["src"].endswith((".png", ".jpg", ".jpeg", ".webp")):
                image_links.add(img["src"])

        # From <img data-lazy="">
        for img in soup.find_all("img", {"data-lazy": True}):
            if img["data-lazy"].endswith((".png", ".jpg", ".jpeg", ".webp")):
                image_links.add(img["data-lazy"])
        image_urls = list(image_links)

        
        category = ''
        lis = soup.select("ol.breadcrumbs li")

        # Get second last li
        second_last = lis[-2] if len(lis) > 2 else None

        # Extract the text (strip spaces)
        category = ''
        if second_last:
            category = second_last.get_text(strip=True)
        
        
        # Generate unique product variant ID (using URL + SKU)
        # product_variant_id = f"{website_name}_{hash(product_url)}"
        
        # Check if product is in stock (assume in stock if price exists)
        in_stock = bool(price)
        
        product_info = {
            # 'product_variant_id': product_variant_id,
            'name': title,
            'sku': sku,
            'price': price,
            'vendor': '',
            'category': category,  # Use vendor as category since there's no separate category
            'description': description,
            'in_stock': in_stock,
            # 'link': product_url,
            'image_link': ",".join(image_urls[:2]),
            # 'website': website_name
        }
        
        return product_info
        
    # except Exception as e:
    #     print(f"Error extracting legacyjudaica product info: {e}")
    #     return None

if __name__ == "__main__":
    print(extract_ozvehadar_product_info())
#     print(load_shaijudaica_product_urls())