# Product Sync System - Quick Setup Guide

## 🚀 Quick Start

Follow these steps to get the Product Sync System up and running:

### Step 1: Run Migrations

```bash
python manage.py migrate
```

This will create the necessary database tables:
- `VendorConfiguration`
- `ProductSyncStatus`
- `WebsiteImportLog`

### Step 2: Start Celery Worker

The system uses Celery for background tasks (import/export operations).

```bash
# Terminal 1: Start Celery worker
celery -A core worker -l info

# Terminal 2: Start Django server
python manage.py runserver
```

### Step 3: Access the System

Open your browser and navigate to:

```
http://localhost:8000/scraper/vendors/
```

## 📋 Complete Workflow Example

### 1. Configure a Vendor

**URL:** `http://localhost:8000/scraper/vendors/`

- Click "Configure" for a vendor (e.g., ritelite.com)
- Fill in the form:
  - **Vendor ID:** `5` (from your website's vendor system)
  - **SKU Prefix:** `RLC-` (text added before SKU)
  - **Markup Percentage:** `15` (15% price increase)
  - **Default Category ID:** `42` (category on your website)
  - **Track Inventory:** Checked
  - **Sell Out of Stock:** Checked
- Click "Save Configuration"

**What this does:**
- Products from ritelite will have SKUs transformed: `22-N` → `RLC-22-N`
- Prices will be marked up: `$10.00` → `$11.50` (15% increase)
- All products will be assigned to category 42 by default

### 2. Import Website Products

**Purpose:** Check which products are already on your website

**URL:** `http://localhost:8000/scraper/sync/`

1. Export products from your website as CSV
   - Expected format:
   ```csv
   ID,Name,Sku,Barcode,ISBN
   12345,Product Name,RLC-22-N,,
   12346,Another Product,IBSLA123,,
   ```

2. Click "Import Website Products" button
3. Upload the CSV file
4. Click "Start Import"
5. Wait for completion (progress bar shows status)

**What this does:**
- System reads each row from CSV
- Extracts SKU with prefix: `RLC-22-N`
- Removes prefix to find original: `22-N`
- Searches database for product with SKU `22-N` from ritelite
- Marks matched products as "on_website"
- Identifies products in DB but not in CSV as "new"

**Results:**
- **Matched Products:** Products found in both DB and website
- **New Products Found:** Products in DB but not on website (these can be exported!)
- **Skipped Rows:** Rows that couldn't be matched

### 3. Select Products for Export

**URL:** `http://localhost:8000/scraper/sync/`

**Option A: Select Individual Products**
- Check the box next to each product you want to export

**Option B: Bulk Selection**
- Click "Bulk Select" dropdown
- Choose:
  - **Select All:** Select all products on current filter
  - **Select New Products:** Select only products not on website
  - **Deselect All:** Clear all selections

**Filters:**
- **Website:** Filter by vendor (e.g., ritelite)
- **Status:** 
  - **All:** Show all products
  - **New:** Only products not on website
  - **Synced:** Only products already on website
  - **Selected:** Only products selected for export
- **Search:** Search by name, SKU, or category

### 4. Export Selected Products

1. After selecting products, click "Export Selected"
2. System starts background task
3. Wait for completion notification
4. Click "Download" when prompted
5. File downloads as: `upload-products-to-website-YYYYMMDD_HHMMSS.csv`

**What the export CSV contains:**
```csv
SKU,Title,Categories,List Price,Length,Height,Width,Weight,Description,Short Desc,Product Type Id,Sell Out of stock,Track Inventory,Vendor id,Release Date,Media
RLC-22-N,Product Name,42,11.50,,,,,"Description",,3,TRUE,TRUE,5,,https://example.com/image.jpg
```

**Transformations Applied:**
- ✅ SKU prefix added: `22-N` → `RLC-22-N`
- ✅ Price markup applied: `$10.00` → `$11.50`
- ✅ Vendor ID added: `5`
- ✅ Category ID set: `42`
- ✅ Inventory settings applied

### 5. Upload to Website

1. Take the downloaded CSV file
2. Go to your website's product import page
3. Upload the CSV
4. Your website will bulk-create these products!

### 6. Monitor Import History

**URL:** `http://localhost:8000/scraper/sync/import-history/`

- View all past imports
- Check success rates
- Review error messages
- Monitor matched vs. new products

## 🔄 Regular Workflow

**Weekly Routine:**

1. **Monday:** Export products from website → Import into system
   - Updates sync status (what's on website vs. what's new)

2. **Tuesday-Thursday:** Scrape vendor websites
   - New products automatically added to database

3. **Friday:** 
   - Filter for "New Products"
   - Review and select products
   - Export to CSV
   - Upload to website

4. **Weekend:** Products are live on website!

## 🎯 Common Use Cases

### Use Case 1: Adding New Vendor Products Weekly

```
1. Scraper runs → 100 new products added to DB
2. Import website export → 500 products marked as "on website"
3. Filter by "New" status → Shows 100 new products
4. Bulk select "New Products"
5. Export → Generates CSV with all transformations
6. Upload to website → 100 new products go live!
```

### Use Case 2: Updating Prices

```
1. Edit vendor configuration
2. Change markup from 15% to 20%
3. Filter by vendor
4. Select products to update
5. Export with new prices
6. Upload to website (update mode)
```

### Use Case 3: Managing Multiple Vendors

```
Vendor A (ritelite):
  - SKU Prefix: RLC-
  - Vendor ID: 5
  - Markup: 15%
  - Category: 42

Vendor B (craftsandmore):
  - SKU Prefix: CAM-
  - Vendor ID: 8
  - Markup: 20%
  - Category: 56

System automatically applies correct settings per vendor!
```

## 📊 Understanding the Dashboard

### Statistics Cards

- **Total Products:** All products in database
- **On Website:** Products that have been exported/synced
- **New Products:** Products not yet on website (ready to export!)
- **Selected:** Products currently selected for export

### Product Table Columns

- **Select:** Checkbox to select for export
- **Product:** Product name (with image indicator)
- **SKU:** Original SKU from database
- **Price:** Original price (before markup)
- **Website:** Source vendor
- **Status:** 
  - 🟢 **On Website:** Already synced
  - 🟡 **New:** Not on website yet
  - ⚪ **Untracked:** No sync status yet
- **Last Sync:** Last time product was synced/exported

## 🔧 Admin Panel

Access Django admin: `http://localhost:8000/admin/`

### VendorConfiguration
- View/edit vendor settings
- Activate/deactivate vendors
- Bulk manage configurations

### ProductSyncStatus
- View sync status for all products
- Filter by on_website, selected_for_export
- Set custom overrides per product
- Useful for special cases

### WebsiteImportLog
- Detailed import logs
- Progress tracking
- Error messages
- Statistics per import

## ⚡ Quick Commands

```bash
# Create superuser (if not exists)
python manage.py createsuperuser

# Run migrations
python manage.py migrate

# Start Celery worker
celery -A core worker -l info

# Start Django server
python manage.py runserver

# Open shell for testing
python manage.py shell
```

## 🧪 Testing the System

### Test 1: Vendor Configuration

```python
python manage.py shell
```

```python
from scraper.models import Website, VendorConfiguration

# Get website
website = Website.objects.get(name='ritelite')

# Create/update config
config, created = VendorConfiguration.objects.update_or_create(
    website=website,
    defaults={
        'vendor_id': 5,
        'sku_prefix': 'RLC-',
        'markup_percentage': 15.00,
        'default_category_id': '42',
        'track_inventory': True,
        'sell_out_of_stock': True,
    }
)

print(f"Config {'created' if created else 'updated'}: {config}")
```

### Test 2: SKU Transformation

```python
from scraper.sync_utils import SKUMatcher

# Test prefix extraction
prefix, sku = SKUMatcher.extract_vendor_prefix('RLC-22-N')
print(f"Prefix: {prefix}, SKU: {sku}")  # Output: RLC-, 22-N

# Test product matching
product = SKUMatcher.match_product_by_sku('RLC-22-N')
print(f"Matched: {product}")
```

### Test 3: Price Markup

```python
from scraper.models import VendorConfiguration

config = VendorConfiguration.objects.get(website__name='ritelite')
marked_up = config.apply_price_markup('$10.00')
print(f"Original: $10.00, Marked up: {marked_up}")  # $11.50
```

## 🆘 Troubleshooting

### Issue: Products Not Matching During Import

**Symptoms:** Import shows 0 matched products, all skipped

**Solutions:**
1. Check vendor configuration exists and is active
2. Verify SKU prefix is correct (e.g., "RLC-" not "RLC")
3. Check SKU format in database matches (case-sensitive)
4. Review import log error messages in admin panel

**Debug:**
```python
from scraper.sync_utils import SKUMatcher

# Test with actual SKU from import
SKUMatcher.extract_vendor_prefix('RLC-22-N')
# Should return: ('RLC-', '22-N')

# Check if product exists
from scraper.models import Product
Product.objects.filter(sku='22-N', website__iexact='ritelite').exists()
```

### Issue: Export Generates Empty CSV

**Symptoms:** Export completes but CSV has no products

**Solutions:**
1. Verify products are selected (selected_for_export=True)
2. Check vendor configuration is active
3. Ensure product.website name matches vendor configuration

**Debug:**
```python
from scraper.models import ProductSyncStatus

# Check selected products
selected = ProductSyncStatus.objects.filter(selected_for_export=True)
print(f"Selected products: {selected.count()}")

for status in selected[:5]:
    print(f"{status.product.name} - {status.product.website}")
```

### Issue: Celery Tasks Not Running

**Symptoms:** Import/export hangs, never completes

**Solutions:**
1. Check Celery worker is running: `celery -A core worker -l info`
2. Check Redis is running: `redis-cli ping` (should return PONG)
3. Check Celery configuration in settings.py
4. Review Celery logs for errors

**Start Celery:**
```bash
# Kill any existing Celery processes
pkill -f celery

# Start fresh
celery -A core worker -l info
```

### Issue: Price Not Applying Markup

**Symptoms:** Exported prices same as database prices

**Solutions:**
1. Verify markup_percentage is set in vendor config
2. Check product.price format (should be "$10.00" not "10.00")
3. Ensure vendor config is active
4. Check for custom_price override in ProductSyncStatus

## 📱 API Endpoints Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/scraper/vendors/` | GET | List all vendors |
| `/scraper/vendors/<id>/edit/` | GET/POST | Edit vendor config |
| `/scraper/sync/` | GET | Product sync dashboard |
| `/scraper/sync/toggle-selection/` | POST | Toggle product selection |
| `/scraper/sync/bulk-select/` | POST | Bulk select/deselect |
| `/scraper/sync/import/` | POST | Upload import CSV |
| `/scraper/sync/import/<id>/status/` | GET | Check import status |
| `/scraper/sync/export/` | POST | Export selected products |
| `/scraper/sync/export/<task_id>/status/` | GET | Check export status |
| `/scraper/sync/download/<filename>/` | GET | Download CSV |
| `/scraper/sync/import-history/` | GET | View import history |

## 🎓 Best Practices

1. **Configure All Vendors First:** Set up vendor configs before first import
2. **Import Weekly:** Keep sync status accurate by importing website exports regularly
3. **Use Filters:** Filter by vendor and status to manage products efficiently
4. **Bulk Operations:** Use bulk select for efficiency with many products
5. **Monitor History:** Check import history to catch issues early
6. **Test Transformations:** Test SKU/price transformations before bulk export
7. **Backup Before Upload:** Keep a backup of website before bulk uploads
8. **Custom Overrides:** Use admin panel for special product-specific settings

## 📞 Support

For detailed documentation, see: `PRODUCT_SYNC_SYSTEM.md`

For issues:
1. Check Django logs: `python manage.py runserver` output
2. Check Celery logs: Celery worker terminal output
3. Check admin panel: `/admin/scraper/websiteimportlog/`
4. Review this guide's troubleshooting section

---

**Version:** 1.0  
**Last Updated:** 2026-03-13  
**Status:** Production Ready ✅
