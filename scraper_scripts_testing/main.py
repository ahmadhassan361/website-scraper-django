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
# if __name__ == "__main__":
#     product_urls = grab_product_urls()
#     for url in product_urls:
#         print(url)
url = "https://ritelite.com/Products/ProductView/Category/STICKR/5259"
category = url.split("Category/")[1].split("/")[0]
print(category)  # STICKR
