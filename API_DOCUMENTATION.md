# Product Export API Documentation

## Overview

This REST API provides endpoints for exporting product data from the scraper system to third-party systems. The API is optimized for large datasets (100k+ products) with efficient pagination and filtering options.

## Base URL

```
http://your-domain.com/scraper/api/
```

## Authentication

The API uses **Static Token Authentication** to secure all endpoints.

### Getting Your API Token

The API token is configured in your `.env` file:
```bash
API_AUTH_TOKEN=sk_live_your_secret_api_token_change_this_in_production_abc123xyz789
```

**IMPORTANT:** Change this to a secure random token in production!

Generate a secure token:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### How to Authenticate

You can authenticate in two ways:

#### Option 1: Authorization Header (Recommended)
```bash
curl -H "Authorization: Bearer YOUR_API_TOKEN" \
     "http://localhost:8000/scraper/api/products/"
```

#### Option 2: X-API-Key Header
```bash
curl -H "X-API-Key: YOUR_API_TOKEN" \
     "http://localhost:8000/scraper/api/products/"
```

### Authentication Errors

**401 Unauthorized (No token provided):**
```json
{
  "detail": "Authentication credentials were not provided."
}
```

**403 Forbidden (Invalid token):**
```json
{
  "detail": "Invalid API token"
}
```

---

## Endpoints

### 1. List All Products (Paginated)

Get a paginated list of all products.

**Endpoint:** `GET /scraper/api/products/`

**Query Parameters:**
- `page_size` (optional): Number of results per page (default: 1000, max: 5000)
- `cursor` (optional): Pagination cursor for next/previous page
- `website` (optional): Filter by website name
- `in_stock` (optional): Filter by stock status (true/false)
- `search` (optional): Search in name, SKU, description, category, vendor
- `ordering` (optional): Order results (e.g., 'name', '-created_at', 'price')

**Example Request:**
```bash
curl -H "Authorization: Bearer YOUR_API_TOKEN" \
     "http://localhost:8000/scraper/api/products/?page_size=1000"
```

**Example Response:**
```json
{
  "next": "http://localhost:8000/scraper/api/products/?cursor=cD0yMDIz...",
  "previous": null,
  "results": [
    {
      "id": 1,
      "product_variant_id": "waterdalecollection_12345",
      "website": "waterdalecollection",
      "name": "Sample Product",
      "sku": "SKU-001",
      "price": "$29.99",
      "category": "Judaica",
      "vendor": "Vendor Name",
      "in_stock": true,
      "in_stock_display": "Yes",
      "description": "Product description here...",
      "image_link": "https://example.com/image.jpg",
      "link": "https://example.com/product",
      "created_at": "2024-01-15T10:30:00Z",
      "created_at_formatted": "2024-01-15 10:30:00",
      "updated_at": "2024-01-20T14:45:00Z",
      "updated_at_formatted": "2024-01-20 14:45:00"
    }
  ]
}
```

---

### 2. Get Single Product

Get details of a specific product by ID.

**Endpoint:** `GET /scraper/api/products/{id}/`

**Example Request:**
```bash
curl "http://localhost:8000/scraper/api/products/123/"
```

**Example Response:**
```json
{
  "id": 123,
  "product_variant_id": "waterdalecollection_12345",
  "website": "waterdalecollection",
  "name": "Sample Product",
  "sku": "SKU-001",
  "price": "$29.99",
  "category": "Judaica",
  "vendor": "Vendor Name",
  "in_stock": true,
  "in_stock_display": "Yes",
  "description": "Product description...",
  "image_link": "https://example.com/image.jpg",
  "link": "https://example.com/product",
  "created_at": "2024-01-15T10:30:00Z",
  "created_at_formatted": "2024-01-15 10:30:00",
  "updated_at": "2024-01-20T14:45:00Z",
  "updated_at_formatted": "2024-01-20 14:45:00"
}
```

---

### 3. Filter Products by Website

Get products filtered by a specific website.

**Endpoint:** `GET /scraper/api/products/by_website/`

**Query Parameters:**
- `website` (required): Website name to filter by
- `page_size` (optional): Number of results per page

**Example Request:**
```bash
curl "http://localhost:8000/scraper/api/products/by_website/?website=waterdalecollection&page_size=500"
```

---

### 4. Get Summary Statistics

Get summary statistics about all products.

**Endpoint:** `GET /scraper/api/products/summary/`

**Example Request:**
```bash
curl "http://localhost:8000/scraper/api/products/summary/"
```

**Example Response:**
```json
{
  "total_products": 85000,
  "in_stock": 72000,
  "out_of_stock": 13000,
  "websites": [
    {
      "website": "waterdalecollection",
      "product_count": 5000,
      "is_active": true
    },
    {
      "website": "btshalom",
      "product_count": 3500,
      "is_active": true
    }
  ],
  "api_info": {
    "default_page_size": 1000,
    "max_page_size": 5000,
    "pagination_type": "cursor",
    "supported_filters": ["website", "in_stock", "search"],
    "supported_ordering": ["id", "name", "created_at", "updated_at", "price", "website"]
  }
}
```

---

### 5. Get Available Websites

Get a list of all websites being scraped.

**Endpoint:** `GET /scraper/api/products/websites/`

**Example Request:**
```bash
curl "http://localhost:8000/scraper/api/products/websites/"
```

**Example Response:**
```json
[
  {
    "id": 1,
    "name": "waterdalecollection",
    "url": "https://waterdalecollection.com",
    "is_active": true,
    "product_count": 5000
  },
  {
    "id": 2,
    "name": "btshalom",
    "url": "https://btshalom.com",
    "is_active": true,
    "product_count": 3500
  }
]
```

---

### 6. Bulk Stream Export (For Very Large Datasets)

Stream all products in JSON format. Memory-efficient for very large datasets.

**Endpoint:** `GET /scraper/api/bulk-export/stream/`

**Query Parameters:**
- `website` (optional): Filter by website name

**Example Request:**
```bash
curl "http://localhost:8000/scraper/api/bulk-export/stream/?website=waterdalecollection" > products.json
```

**Response Format:**
```json
{
  "products": [
    {...},
    {...},
    ...
  ],
  "total": 85000
}
```

**Note:** This endpoint streams the response, making it memory-efficient for datasets with 100k+ products.

---

## Pagination Explained

### Cursor Pagination (Default)

The API uses cursor-based pagination for optimal performance with large datasets.

**Advantages:**
- Efficient for large datasets
- Consistent results even when data changes
- Better performance than offset-based pagination

**How to Use:**
1. Make initial request: `GET /scraper/api/products/`
2. Get `next` URL from response
3. Use `next` URL for subsequent requests
4. Continue until `next` is `null`

**Example:**
```python
import requests

url = "http://localhost:8000/scraper/api/products/?page_size=1000"
all_products = []

while url:
    response = requests.get(url)
    data = response.json()
    
    all_products.extend(data['results'])
    url = data['next']  # Get next page URL

print(f"Total products fetched: {len(all_products)}")
```

---

## Filtering Examples

### 1. Get Only In-Stock Products
```bash
curl "http://localhost:8000/scraper/api/products/?in_stock=true&page_size=1000"
```

### 2. Get Products from Specific Website
```bash
curl "http://localhost:8000/scraper/api/products/?website=waterdalecollection"
```

### 3. Search Products
```bash
curl "http://localhost:8000/scraper/api/products/?search=menorah"
```

### 4. Combine Multiple Filters
```bash
curl "http://localhost:8000/scraper/api/products/?website=btshalom&in_stock=true&search=candle"
```

### 5. Order Results
```bash
# Newest first
curl "http://localhost:8000/scraper/api/products/?ordering=-created_at"

# Alphabetically by name
curl "http://localhost:8000/scraper/api/products/?ordering=name"

# By price (descending)
curl "http://localhost:8000/scraper/api/products/?ordering=-price"
```

---

## Integration Examples

### Python Example

```python
import requests

class ProductAPIClient:
    def __init__(self, base_url, api_token):
        self.base_url = base_url
        self.headers = {
            'Authorization': f'Bearer {api_token}'
        }
    
    def get_all_products(self, website=None, page_size=1000):
        """Fetch all products with pagination"""
        url = f"{self.base_url}/scraper/api/products/?page_size={page_size}"
        if website:
            url += f"&website={website}"
        
        all_products = []
        
        while url:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            all_products.extend(data['results'])
            url = data.get('next')
            
            print(f"Fetched {len(all_products)} products so far...")
        
        return all_products
    
    def get_summary(self):
        """Get summary statistics"""
        url = f"{self.base_url}/scraper/api/products/summary/"
        response = requests.get(url, headers=self.headers)
        return response.json()

# Usage
API_TOKEN = "your-secret-api-token-here"
client = ProductAPIClient("http://localhost:8000", API_TOKEN)

# Get all products from specific website
products = client.get_all_products(website="waterdalecollection")
print(f"Total products: {len(products)}")

# Get summary
summary = client.get_summary()
print(f"Total products in system: {summary['total_products']}")
```

### JavaScript Example

```javascript
async function fetchAllProducts(website = null, pageSize = 1000) {
    const baseUrl = 'http://localhost:8000/scraper/api/products/';
    let url = `${baseUrl}?page_size=${pageSize}`;
    
    if (website) {
        url += `&website=${website}`;
    }
    
    const allProducts = [];
    
    while (url) {
        const response = await fetch(url);
        const data = await response.json();
        
        allProducts.push(...data.results);
        url = data.next;
        
        console.log(`Fetched ${allProducts.length} products so far...`);
    }
    
    return allProducts;
}

// Usage
fetchAllProducts('waterdalecollection')
    .then(products => {
        console.log(`Total products: ${products.length}`);
        // Process products
    });
```

### cURL Batch Download Example

```bash
#!/bin/bash
# Script to download all products in batches

BASE_URL="http://localhost:8000/scraper/api/products/"
PAGE_SIZE=5000
OUTPUT_DIR="./product_exports"

mkdir -p $OUTPUT_DIR

# Get first page
NEXT_URL="${BASE_URL}?page_size=${PAGE_SIZE}"
PAGE=1

while [ ! -z "$NEXT_URL" ]; do
    echo "Downloading page $PAGE..."
    
    # Download page
    curl -s "$NEXT_URL" > "${OUTPUT_DIR}/products_page_${PAGE}.json"
    
    # Extract next URL
    NEXT_URL=$(cat "${OUTPUT_DIR}/products_page_${PAGE}.json" | jq -r '.next // empty')
    
    PAGE=$((PAGE + 1))
    sleep 1  # Be nice to the server
done

echo "Download complete! Downloaded $((PAGE - 1)) pages"
```

---

## Performance Tips

### 1. For Large Datasets (100k+ products)
- Use cursor pagination (default)
- Set `page_size` to maximum (5000) for fewer requests
- Consider using the bulk stream endpoint for one-time full exports

### 2. For Incremental Updates
- Filter by `updated_at` using ordering: `?ordering=-updated_at`
- Use website filter if syncing specific vendors

### 3. Rate Limiting
- Anonymous users: 1000 requests/hour
- Authenticated users: 10000 requests/hour
- Add delays between requests to avoid hitting limits

---

## Error Handling

### Common Error Responses

**400 Bad Request:**
```json
{
  "error": "Please provide website parameter"
}
```

**404 Not Found:**
```json
{
  "error": "Website 'invalid_name' not found"
}
```

**429 Too Many Requests:**
```json
{
  "detail": "Request was throttled. Expected available in 3600 seconds."
}
```

---

## Best Practices

1. **Use Cursor Pagination**: Always use cursor pagination for large datasets
2. **Set Appropriate Page Size**: Use 1000-5000 depending on your needs
3. **Handle Errors**: Implement retry logic for network failures
4. **Monitor Rate Limits**: Respect rate limits and add delays if needed
5. **Cache Data**: Cache responses when appropriate to reduce API calls
6. **Filter Early**: Use filters to reduce the amount of data transferred
7. **Stream for Bulk**: Use the stream endpoint for one-time full exports

---

## Changelog

### Version 1.0 (Current)
- Initial release
- Cursor-based pagination
- Website filtering
- Stock status filtering
- Search functionality
- Bulk stream export
- Summary statistics

---

## Support

For issues or questions:
- Check the API summary endpoint for current configuration
- Review error messages for specific issues
- Monitor API response times and adjust pagination accordingly
