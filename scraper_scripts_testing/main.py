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
# def extract_ozvehadar_product_info():
#         """
#         Extract product information from ozvehadar.us product page HTML using BeautifulSoup
        
#         Args:
#             soup: BeautifulSoup object of the product page
#             product_url: URL of the product page
#             website_name: Name of the website
            
#         Returns:
#             dict: Product information dictionary
#         """
#     # try:
#         response = requests.get("https://ozvehadar.us/talmud-bavli-mesivta-shinun-blue/")
#         soup = BeautifulSoup(response.content, "html.parser")
#         title_tag = soup.find('h1', class_='productView-title')
#         title = title_tag.get_text(strip=True) if title_tag else None

#         # Description
#         desc_div = soup.find(id="tab-description")
#         description = desc_div.get_text(separator=' ', strip=True) if desc_div else None

#         # Price
#         price_span = soup.find("span", class_="price price--withoutTax")
#         price = price_span.get_text(strip=True) if price_span else None

#         # SKU
#         sku_span = soup.find("dd", {"data-product-sku": True})
#         sku = sku_span.get_text(strip=True) if sku_span else None

#         # Image URL
#         # From <img src="">
#         image_links = set()
#         image_urls  = []
#         for a in soup.find_all("a", href=True):
#             if a["href"].endswith((".png", ".jpg", ".jpeg", ".webp")):
#                 image_links.add(a["href"])

#         # From <img src="">
#         for img in soup.find_all("img", src=True):
#             if img["src"].endswith((".png", ".jpg", ".jpeg", ".webp")):
#                 image_links.add(img["src"])

#         # From <img data-lazy="">
#         for img in soup.find_all("img", {"data-lazy": True}):
#             if img["data-lazy"].endswith((".png", ".jpg", ".jpeg", ".webp")):
#                 image_links.add(img["data-lazy"])
#         image_urls = list(image_links)

        
#         category = ''
#         lis = soup.select("ol.breadcrumbs li")

#         # Get second last li
#         second_last = lis[-2] if len(lis) > 2 else None

#         # Extract the text (strip spaces)
#         category = ''
#         if second_last:
#             category = second_last.get_text(strip=True)
        
        
#         # Generate unique product variant ID (using URL + SKU)
#         # product_variant_id = f"{website_name}_{hash(product_url)}"
        
#         # Check if product is in stock (assume in stock if price exists)
#         in_stock = bool(price)
        
#         product_info = {
#             # 'product_variant_id': product_variant_id,
#             'name': title,
#             'sku': sku,
#             'price': price,
#             'vendor': '',
#             'category': category,  # Use vendor as category since there's no separate category
#             'description': description,
#             'in_stock': in_stock,
#             # 'link': product_url,
#             'image_link': ",".join(image_urls[:2]),
#             # 'website': website_name
#         }
        
#         return product_info
        
#     # except Exception as e:
#     #     print(f"Error extracting legacyjudaica product info: {e}")
#     #     return None
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
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://www.kaftorjudaica.com/"

def load_kaftorjudaica_product_urls():
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


if __name__ == "__main__":
    start_url = "https://www.kaftorjudaica.com/search.asp?Keyword=a&image1.x=0&image1.y=0&pg=1"
    results = load_kaftorjudaica_product_urls(start_url)
    for r in results[:5]:
        print(r)
    print(f"\nTotal products scraped: {len(results)}")

# if __name__ == "__main__":
#     print(load_mefoarjudaica_product_urls())
#     print(load_shaijudaica_product_urls())