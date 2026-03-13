# Product Sync System - User Guide

Welcome! This guide will help you understand how to use the Product Sync System to manage your vendor products and website listings.

---

## 📋 Table of Contents
1. [System Overview](#system-overview)
2. [Step 1: Configure Vendors](#step-1-configure-vendors)
3. [Step 2: Import Your Website Products](#step-3-import-your-website-products)
4. [Step 3: View Sync Status](#step-4-view-sync-status)
5. [Step 4: Export Products](#step-5-export-products)
6. [Understanding Scraping Speed](#understanding-scraping-speed)

---

## System Overview

This system helps you:
- ✅ Collect products from multiple vendor websites automatically
- ✅ Compare which products are already on your website
- ✅ Find new products that you can add to your website
- ✅ Export products in a format ready to upload

---

## Step 1: Configure Vendors

**Before you can sync products, you need to set up vendor configurations.**

### What is Vendor Configuration?
Vendor configuration tells the system how to match products from each vendor with products on your website.

### How to Configure:

1. **Go to Product Sync → Vendor Management**
   - You'll see a list of all vendor websites

2. **Click "Configure" or "Edit" for each vendor**
   - Fill in these details:

   **Vendor ID:** The ID number you use for this vendor in your website  
   *Example: If your vendor is assigned ID "123" in your system, enter 123*

   **SKU Prefix:** Text that gets added before the SKU  
   *Example: If you add "RLC-" prefix, SKU "12345" becomes "RLC-12345"*

   **Markup Percentage:** How much you increase the price  
   *Example: 15% markup on $10.00 = $11.50*

   **Default Category ID:** The category number for products from this vendor  
   *Example: 45 (your Judaica category)*

3. **Click "Save Configuration"**

4. **Repeat for all vendors you want to track**

> **💡 Tip:** Start with just 1-2 vendors to test the system before configuring all of them.

---

## Step 2: Import Your Website Products

**After Vendor Configuration, import your current website product list.**

### Why Import?
This step tells the system which products are already on your website so it can identify new products.

### How to Import:

1. **Export Products from Your Website**
   - Go to your website admin
   - Export all products as CSV file
   - Save the file on your computer

2. **Go to Product Sync → Import History**

3. **Click "Import New File"**

4. **Choose Your File and Select Vendor:**
   - Click "Choose File" and select your CSV
   - **Select Vendor** from the dropdown
     - Choose "All Vendors" to match products from all vendors
     - OR choose specific vendor to only match that vendor's products

5. **Click "Start Import"**
   - The system will process your file
   - It matches products based on SKU
   - Shows progress bar during import

6. **Wait for "Completed" Status**
   - You'll see:
     - Total rows processed
     - Products matched (already on website)
     - New products found (not on website)

> **💡 Tip:** Import your website products every time before checking sync status to get accurate results.

---

## Step 3: View Sync Status

**Now see which products are listed/not listed on your website.**

### How to View:

1. **Go to Product Sync → Product Sync Dashboard**

2. **Select Filters:**

   **Vendor Filter:**
   - Choose "All Vendors" to see products from all vendors
   - OR select specific vendor to see only their products

   **Status Filter (Most Important!):**
   - **New Products:** Products NOT on your website (ready to add!)
   - **Synced Products:** Products already on your website
   - **All Products:** Everything in the system

3. **Review the Results:**
   - Each row shows:
     - Product name and SKU
     - Vendor website
     - Original price
     - Your price (with markup applied)
     - Sync status
     - Checkbox to select

4. **Select Products You Want:**
   - Check the boxes next to products you want to export
   - OR click "Select All" to choose everything on the page

---

## Step 4: Export Products

**Export selected products to upload to your website.**

### How to Export:

1. **After Selecting Products:**
   - Click the **"Export Selected"** button
   - Enter a filename (e.g., "new-products-march-2026")
   - Click "Export"

2. **Download Your File:**
   - A CSV file will be generated
   - Click the download link
   - Save to your computer

3. **Upload to Your Website:**
   - Go to your website admin
   - Use the product import feature
   - Upload the CSV file
   - Your products will be added!

### What's in the Export File?

The CSV includes:
- Product title
- SKU (with prefix applied)
- Price (with markup applied)
- Vendor ID
- Category ID
- Description
- Image links
- All required fields for your website

---

## Understanding Scraping Speed

### ⚡ Fast Scraping Websites
- Complete in approximately **30 minutes**
- Can scrape multiple websites simultaneously
- Best to run during low-traffic hours

**Fast Websites Include:**
- waterdalecollection
- btshalom
- malchutjudaica
- feldart
- menuchapublishers
- And many more...

### 🐌 Slow Scraping Websites
- Can take **several hours to days** depending on:
  - Number of products
  - Website speed
  - Server response time
- Can only run when fast scrapers are NOT running
- Best to start before you leave for the day

**Slow Websites Include:**
- meiros
- legacyjudaica
- simchonim
- jewisheducationaltoys
- ritelite
- And several others...

---

## 📝 Quick Workflow Summary

Here's the complete process in simple steps:

1. **Configure Vendors** (one-time setup)
   - Set SKU prefix, markup %, vendor ID, category ID

2. **Scrape Vendor Products** (weekly/monthly)
   - Start fast scrapers (30 min)
   - Start slow scrapers (hours/days)

3. **Import Website Products** (before checking sync)
   - Export from your website
   - Import CSV file
   - Select vendor filter

4. **View Sync Status**
   - Go to Sync Dashboard
   - Filter by vendor
   - Filter by status (New/Synced/All)

5. **Export New Products**
   - Select products
   - Export to CSV
   - Upload to website

---

## ❓ Common Questions

**Q: Why do I need to configure vendors first?**  
A: Configuration tells the system how to format products for your website (SKU prefix, pricing, categories).

**Q: How often should I scrape?**  
A: Weekly is recommended, but you can scrape as often as needed.

**Q: What if scraping fails?**  
A: Simply click "Start Scraping" again. The system will resume from where it stopped.

**Q: Can I scrape while importing?**  
A: Yes! Scraping and importing are independent processes.

**Q: How do I know if products are matched correctly?**  
A: After importing, check the "Matched Products" count. It should match your current product count for that vendor.


