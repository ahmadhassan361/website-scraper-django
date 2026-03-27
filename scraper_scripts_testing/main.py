import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from time import sleep
import requests
from bs4 import BeautifulSoup



def load_feldheim_xml_data():
    file_path = "./feldheim.xml"

    with open(file_path, "rb") as f:
        soup = BeautifulSoup(f, "xml")

    results = []

    for url_tag in soup.find_all("url"):
        image_tag = url_tag.find("image:image")

        # skip if no image
        if not image_tag:
            continue

        page_loc = url_tag.find("loc")
        image_loc = image_tag.find("image:loc")
        image_title = image_tag.find("image:title")

        results.append({
            "link": page_loc.get_text(strip=True) if page_loc else None,
            "image": image_loc.get_text(strip=True) if image_loc else None,
            "title": image_title.get_text(strip=True) if image_title else None,
        })

    return results

# Example usage
if __name__ == "__main__":
    data = load_feldheim_xml_data()
    print(f"Total: {len(data)}")
    print(data[:3])