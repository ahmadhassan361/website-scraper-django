# Product Sync System Documentation

## Overview

The Product Sync System is a comprehensive solution for managing product synchronization between scraped vendor data and your e-commerce website. It intelligently matches products using SKU transformations, applies vendor-specific configurations, and streamlines the import/export workflow.

## System Architecture

### Database Models

#### 1. VendorConfiguration
Stores vendor-specific settings for each website/source.

**Fields:**
- `website` - OneToOne relationship with Website model
- `vendor_id` - Vendor ID for website upload CSV
- `sku_prefix` - Prefix added to SKU (e.g., "RLC-", "IBSLA")
- `markup_percentage` - Price adjustment percentage
- `default_category_id` - Default category for products
- `default_product_type_id` - Default product type (default: 3)
- `track_inventory` - Default inventory tracking setting
- `sell_out_of_stock` - Default out-of-stock selling policy
- `is_active` - Enable/disable this configuration

**Methods:**
- `apply_sku_transform(original_sku)` - Adds vendor prefix to SKU
- `remove_sku_prefix(prefixed_sku)` - Removes prefix to get original SKU
- `apply_price_markup(original_price)` - Applies markup percentage

#### 2. ProductSyncStatus
Tracks synchronization status for each product.

**Fields:**
- `product` - OneToOne relationship with Product
- `on_website` - Boolean indicating if product is on website
- `website_sku` - SKU format as it appears on website (with prefix)
- `website_product_id` - Product ID from website export
- `status` - Sync status: 'new', 'synced', 'updated', 'removed'
- `last_synced_at` - Last sync timestamp
- `last_export_at` - Last export timestamp
- `selected_for_export` - User selection flag
- Custom overrides: `custom_category_id`, `custom_price`, `custom_track_inventory`, `custom_sell_out_of_stock`

**Methods:**
- `mark_on_website(website_sku, website_product_id)` - Mark as synced
- `mark_as_new()` - Mark as not on website

#### 3. WebsiteImportLog
Logs website product import operations.

**Fields:**
- `filename` - Imported CSV filename
- `status` - Import status: 'pending', 'processing', 'completed', 'failed'
- `celery_task_id` - Background task ID
- Statistics: `total_rows`, `processed_rows`, `matched_products`, `new_products_found`, `skipped_rows`
- `progress_percentage` - Import progress (0-100)
- `error_message` - Error details if failed
- `uploaded_by` - User who initiated import

## Core Components

### 1. Utility Classes (`scraper/sync_utils.py`)

#### SKUMatcher
Smart SKU matching between database and website products.

**Key Methods:**
```python
# Extract vendor prefix from SKU
prefix, original_sku = SKUMatcher.extract_vendor_prefix("RLC-22-N")
# Returns: ("RLC-", "22-N")

# Find vendor by prefix
vendor_config = SKUMatcher.find_vendor_by_prefix("RLC-")

# Match product from website export
product = SKUMatcher.match_product_by_sku("RLC-22-N", website_product_id="12345")

# Fuzzy match by name (fallback)
product = SKUMatcher.fuzzy_match_by_name("Product Name", website_name="vendor")
```

#### CSVParser
Handles CSV file operations.

**Key Methods:**
```python
# Parse website export CSV
products = CSVParser.parse_website_export('export-from-website.csv')
# Returns: [{'id': '1', 'name': '...', 'sku': '...', ...}, ...]

# Generate upload CSV
count = CSVParser.generate_upload_csv(products_list, 'upload-products-to-website.csv')
```

#### ProductTransformer
Transforms products for website upload.

**Key Method:**
```python
# Transform product with vendor configuration
row_data = ProductTransformer.transform_for_upload(product)
# Returns: {'SKU': 'RLC-22-N', 'Title': '...', 'List Price': '15.99', ...}
```

#### SyncStatistics
Calculates sync statistics.

**Key Methods:**
```python
# Overall statistics
stats = SyncStatistics.get_sync_stats()
# Returns: {'total_products': 1000, 'on_website': 500, 'new_products': 500, ...}

# Per-vendor statistics
vendor_stats = SyncStatistics.get_vendor_stats()
# Returns: [{'website': <Website>, 'total_products': 100, 'on_website': 50, ...}, ...]
```

### 2. Celery Tasks (`scraper/tasks.py`)

#### import_website_products_task
Background task to import products from website export CSV.

**Process:**
1. Parse CSV file
2. For each row, match product by SKU (with prefix removal)
3. Create/update ProductSyncStatus
4. Identify products in DB but not in import (new products)
5. Update statistics and progress

**Usage:**
```python
task = import_website_products_task.delay(import_log_id, file_path)
```

#### export_products_to_website_task
Background task to export selected products to website upload CSV.

**Process:**
1. Get selected products
2. For each product:
   - Apply vendor SKU transformation
   - Apply price markup
   - Use vendor defaults or custom overrides
   - Generate CSV row
3. Create upload CSV file
4. Update sync status timestamps

**Usage:**
```python
task = export_products_to_website_task.delay(product_ids, filename)
```

### 3. Views (`scraper/sync_views.py`)

#### Vendor Management
- `vendor_management` - List all vendors and configurations
- `vendor_config_edit` - Create/edit vendor configuration

#### Product Sync Dashboard
- `product_sync_dashboard` - Main dashboard with filters and pagination
- `toggle_product_selection` - Toggle single product selection
- `bulk_select_products` - Bulk select/deselect products

#### Import/Export Operations
- `import_website_products` - Upload and import website export CSV
- `import_status` - Check import progress (AJAX)
- `export_selected_products` - Export selected products
- `export_status` - Check export progress (AJAX)
- `download_export` - Download generated CSV
- `import_history` - View import history

## Workflow

### Complete Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRODUCT SYNC WORKFLOW                         │
└─────────────────────────────────────────────────────────────────┘

1. SETUP VENDOR CONFIGURATION
   ├── Navigate to: /scraper/vendors/
   ├── Click "Configure" for each vendor/website
   ├── Set:
   │   ├── Vendor ID (for CSV export)
   │   ├── SKU Prefix (e.g., "RLC-", "IBSLA")
   │   ├── Markup Percentage (e.g., 15% markup)
   │   ├── Default Category ID
   │   └── Inventory settings
   └── Save configuration

2. IMPORT WEBSITE PRODUCTS (Check what's currently on website)
   ├── Export products from your website as CSV
   │   └── Format: ID, Name, Sku, Barcode, ISBN
   ├── Navigate to: /scraper/sync/
   ├── Click "Import Website Products"
   ├── Upload CSV file
   ├── System automatically:
   │   ├── Matches products by SKU (removes prefixes)
   │   ├── Marks matched products as "on_website"
   │   ├── Identifies new products (in DB but not on website)
   │   └── Updates ProductSyncStatus for all
   └── View import results

3. REVIEW & SELECT PRODUCTS
   ├── View Product Sync Dashboard at: /scraper/sync/
   ├── Filter products:
   │   ├── By Website/Vendor
   │   ├── By Status (New/Synced/Selected)
   │   └── By Search (Name/SKU/Category)
   ├── Select products for export:
   │   ├── Individual selection (checkbox)
   │   ├── Bulk "Select All New Products"
   │   ├── Bulk "Select All"
   │   └── Bulk "Deselect All"
   └── Review selected count

4. EXPORT PRODUCTS TO WEBSITE
   ├── Click "Export Selected Products"
   ├── System generates CSV with:
   │   ├── Transformed SKUs (with vendor prefix)
   │   ├── Adjusted prices (with markup)
   │   ├── Vendor ID
   │   ├── Default settings from vendor config
   │   └── Custom overrides if set
   ├── Download: upload-products-to-website-YYYYMMDD_HHMMSS.csv
   └── Upload CSV to your website

5. MONITOR & MAINTAIN
   ├── View import history at: /scraper/sync/import-history/
   ├── Admin panel shows detailed sync status
   └── Re-import website exports periodically to keep sync status updated
```

### Example Scenarios

#### Scenario 1: Adding New Vendor Products

```bash
# Step 1: Scrape products from vendor (existing functionality)
# Products are added to Product model

# Step 2: Configure vendor (one-time setup)
Website: ritelite.com
Vendor ID: 5
SKU Prefix: RLC-
Markup: 15%
Category ID: 42

# Step 3: Import current website products
# Upload export-from-website.csv
# System matches: RLC-22-N (website) → 22-N (database)
# Result: Product with SKU "22-N" marked as "on_website"

# Step 4: Select new products
# Filter: Status = "New" (not on website)
# Select all new products from ritelite

# Step 5: Export
# System generates:
# SKU: 22-N → RLC-22-N
# Price: $10.00 → $11.50 (15% markup)
# Vendor ID: 5
# etc.

# Step 6: Upload to website
# Use generated CSV to bulk upload products
```

#### Scenario 2: Updating Product Prices

```bash
# Step 1: Change vendor configuration
# Update Markup: 15% → 20%

# Step 2: Select products to update
# Filter by vendor
# Select products

# Step 3: Export with new prices
# System applies 20% markup
# Products re-exported with updated prices
```

## API Endpoints

### Vendor Management
- `GET /scraper/vendors/` - List vendors
- `GET/POST /scraper/vendors/<id>/edit/` - Edit vendor config

### Product Sync
- `GET /scraper/sync/` - Sync dashboard
- `POST /scraper/sync/toggle-selection/` - Toggle product selection
- `POST /scraper/sync/bulk-select/` - Bulk select/deselect
- `POST /scraper/sync/import/` - Upload import CSV
- `GET /scraper/sync/import/<id>/status/` - Check import status
- `POST /scraper/sync/export/` - Export selected products
- `GET /scraper/sync/export/<task_id>/status/` - Check export status
- `GET /scraper/sync/download/<filename>/` - Download CSV
- `GET /scraper/sync/import-history/` - View import history

## CSV Formats

### Input: export-from-website.csv
```csv
ID,Name,Sku,Barcode,ISBN
12345,Product Name,RLC-22-N,123456789,
12346,Another Product,IBSLA123,,9781234567890
```

### Output: upload-products-to-website-YYYYMMDD_HHMMSS.csv
```csv
SKU,Title,Categories,List Price,Length,Height,Width,Weight,Description,Short Desc,Product Type Id,Sell Out of stock,Track Inventory,Vendor id,Release Date,Media
RLC-22-N,Product Name,42,11.50,,,,,"Product description",,3,TRUE,TRUE,5,,https://example.com/image.jpg
```

## Admin Panel

Access Django admin at `/admin/` to view and manage:

### VendorConfiguration
- View all vendor configurations
- Edit vendor settings
- Activate/deactivate vendors

### ProductSyncStatus
- View sync status for all products
- Filter by status, website selection
- Update custom overrides

### WebsiteImportLog
- View all import operations
- Monitor progress and statistics
- View error messages

## Testing

### Test Workflow

1. **Create Vendor Configuration**
```python
from scraper.models import Website, VendorConfiguration

website = Website.objects.get(name='ritelite')
config = VendorConfiguration.objects.create(
    website=website,
    vendor_id=5,
    sku_prefix='RLC-',
    markup_percentage=15.00,
    default_category_id='42',
    track_inventory=True,
    sell_out_of_stock=True
)
```

2. **Test SKU Matching**
```python
from scraper.sync_utils import SKUMatcher

# Test prefix extraction
prefix, sku = SKUMatcher.extract_vendor_prefix('RLC-22-N')
# Expected: ('RLC-', '22-N')

# Test product matching
product = SKUMatcher.match_product_by_sku('RLC-22-N')
# Expected: Product with sku='22-N' from ritelite website
```

3. **Test Product Transformation**
```python
from scraper.sync_utils import ProductTransformer
from scraper.models import Product

product = Product.objects.get(sku='22-N', website='ritelite')
row = ProductTransformer.transform_for_upload(product)
# Expected: {'SKU': 'RLC-22-N', 'List Price': '11.50', ...}
```

4. **Test CSV Export**
```python
from scraper.sync_utils import CSVParser
from scraper.models import Product

products = Product.objects.filter(website='ritelite')[:10]
count = CSVParser.generate_upload_csv(list(products), 'test-export.csv')
# Check generated file
```

## Troubleshooting

### Products Not Matching During Import
**Issue:** Products in website export not matching database products

**Solutions:**
1. Check SKU prefix configuration
2. Verify SKU format in database matches (case-sensitive)
3. Check vendor configuration is active
4. Review import log for skipped rows

### Price Not Applying Markup
**Issue:** Exported prices don't reflect markup percentage

**Solutions:**
1. Verify vendor configuration markup_percentage is set
2. Check product.price format (should be like "$10.00")
3. Ensure vendor configuration is active
4. Check for custom_price override in ProductSyncStatus

### Export Generates No Products
**Issue:** Export CSV is empty or has no products

**Solutions:**
1. Verify products are selected (selected_for_export=True)
2. Check vendor configuration exists and is active
3. Review product website names match vendor configuration
4. Check logs for transformation errors

## Next Steps

### Phase 6: Templates (To Be Implemented)

The following templates need to be created:

1. **scraper/vendor_management.html** - Vendor list and configuration UI
2. **scraper/vendor_config_edit.html** - Vendor configuration form
3. **scraper/product_sync_dashboard.html** - Main sync dashboard with filters
4. **scraper/import_history.html** - Import history view

### Recommended Template Structure:
```html
<!-- Example: vendor_management.html -->
{% extends 'components/base.html' %}
{% block content %}
<div class="container">
    <h1>Vendor Management</h1>
    
    <table class="table">
        <thead>
            <tr>
                <th>Website</th>
                <th>Vendor ID</th>
                <th>SKU Prefix</th>
                <th>Markup</th>
                <th>Products</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for vendor in vendors %}
            <tr>
                <td>{{ vendor.website.name }}</td>
                <td>{{ vendor.vendor_config.vendor_id|default:"Not configured" }}</td>
                <td>{{ vendor.vendor_config.sku_prefix|default:"None" }}</td>
                <td>{{ vendor.vendor_config.markup_percentage|default:"0" }}%</td>
                <td>{{ vendor.product_count }}</td>
                <td>
                    <a href="{% url 'scraper:vendor_config_edit' vendor.website.id %}" class="btn btn-primary">Configure</a>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

## Support & Maintenance

### Regular Maintenance Tasks

1. **Weekly:** Import website export to update sync status
2. **Monthly:** Review vendor configurations for pricing updates
3. **As Needed:** Bulk export new products from vendors

### Monitoring

Check these metrics regularly:
- Total products in database
- Products on website vs. new products
- Import success rates
- Export counts

Access via:
- Product Sync Dashboard: `/scraper/sync/`
- Admin Panel: `/admin/scraper/productsyncstatus/`
- Import History: `/scraper/sync/import-history/`

## Contact & Support

For issues or questions:
1. Check logs in Django admin
2. Review Celery task logs
3. Check database for sync status discrepancies
4. Review this documentation

---

**Version:** 1.0  
**Last Updated:** 2026-03-13  
**Status:** Core Implementation Complete (Templates Pending)
