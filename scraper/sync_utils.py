"""
Utility functions for Product Sync System
Handles SKU matching, CSV parsing, and product transformations
"""

import csv
import re
from typing import Dict, List, Tuple, Optional
from django.db.models import Q
from .models import Product, VendorConfiguration, ProductSyncStatus, Website


class SKUMatcher:
    """Smart SKU matching between database and website products"""
    
    @staticmethod
    def extract_vendor_prefix(sku: str) -> Tuple[str, str]:
        """
        Extract vendor prefix from SKU
        Returns: (prefix, original_sku)
        
        Examples:
            "RLC-22-N" -> ("RLC-", "22-N")
            "IBSLA123" -> ("IBSLA", "123")
            "C751" -> ("", "C751")
        """
        if not sku:
            return '', ''
        
        # Common patterns for vendor prefixes
        patterns = [
            r'^([A-Z]{2,6}-)(.+)$',  # RLC-, IBSLA-, etc. with dash
            r'^([A-Z]{2,6})(.+)$',   # IBSLA, IBSC, etc. without dash
        ]
        
        for pattern in patterns:
            match = re.match(pattern, sku)
            if match:
                return match.group(1), match.group(2)
        
        return '', sku
    
    @staticmethod
    def find_vendor_by_prefix(prefix: str) -> Optional[VendorConfiguration]:
        """Find vendor configuration by SKU prefix"""
        if not prefix:
            return None
        
        try:
            # Try exact match first
            return VendorConfiguration.objects.get(sku_prefix=prefix, is_active=True)
        except VendorConfiguration.DoesNotExist:
            # Try case-insensitive match
            return VendorConfiguration.objects.filter(
                sku_prefix__iexact=prefix,
                is_active=True
            ).first()
    
    @staticmethod
    def match_product_by_sku(website_sku: str, website_product_id: str = '', vendor_website: str = None) -> Optional[Product]:
        """
        Match a product from website export to database product (vendor-specific)
        
        Args:
            website_sku: SKU as it appears on website (may have prefix)
            website_product_id: Product ID from website
            vendor_website: Limit matching to this vendor only
            
        Returns:
            Matched Product object or None
        """
        if not website_sku:
            return None
        
        # Step 1: Extract prefix and original SKU
        prefix, original_sku = SKUMatcher.extract_vendor_prefix(website_sku)
        
        # Step 2: If vendor_website is specified, only match products from that vendor
        if vendor_website:
            # Try exact match with vendor filter
            product = Product.objects.filter(
                website__iexact=vendor_website,
                sku__iexact=original_sku
            ).first()
            
            if product:
                return product
            
            # Try with original website SKU (no prefix removal)
            product = Product.objects.filter(
                website__iexact=vendor_website,
                sku__iexact=website_sku
            ).first()
            
            return product
        
        # Step 3: Original logic (when no vendor specified) - Find vendor configuration
        vendor_config = SKUMatcher.find_vendor_by_prefix(prefix)
        
        if vendor_config:
            # Match by website name and original SKU
            website_name = vendor_config.website.name
            
            # Try exact match
            product = Product.objects.filter(
                website__iexact=website_name,
                sku__iexact=original_sku
            ).first()
            
            if product:
                return product
        
        # Step 4: Fallback - try direct SKU match (no prefix removal)
        product = Product.objects.filter(
            Q(sku__iexact=website_sku) |
            Q(sku__iexact=original_sku)
        ).first()
        
        return product
    
    @staticmethod
    def fuzzy_match_by_name(product_name: str, website_name: str = None) -> Optional[Product]:
        """
        Fuzzy match product by name (fallback method)
        
        Args:
            product_name: Product name from website
            website_name: Limit search to specific website
            
        Returns:
            Best matched Product or None
        """
        if not product_name:
            return None
        
        # Clean name for matching
        clean_name = product_name.strip().lower()
        
        query = Product.objects.filter(name__iexact=clean_name)
        
        if website_name:
            query = query.filter(website__iexact=website_name)
        
        return query.first()


class CSVParser:
    """Parse CSV files for import/export"""
    
    @staticmethod
    def parse_website_export(file_path: str) -> List[Dict]:
        """
        Parse export-from-website.csv
        
        Returns list of dicts with keys: ID, Name, Sku, Barcode, ISBN
        """
        products = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    products.append({
                        'id': row.get('ID', '').strip(),
                        'name': row.get('Name', '').strip(),
                        'sku': row.get('Sku', '').strip(),
                        'barcode': row.get('Barcode', '').strip(),
                        'isbn': row.get('ISBN', '').strip(),
                    })
        except Exception as e:
            raise Exception(f"Error parsing CSV: {str(e)}")
        
        return products
    
    @staticmethod
    def generate_upload_csv(products: List[Product], output_path: str) -> int:
        """
        Generate upload-products-to-website.csv
        
        Args:
            products: List of Product objects to export
            output_path: Path to save CSV file
            
        Returns:
            Number of products written
        """
        headers = [
            'SKU', 'Title', 'Categories', 'List Price', 'Length', 'Height', 
            'Width', 'Weight', 'Description', 'Short Desc', 'Product Type Id',
            'Sell Out of stock', 'Track Inventory', 'Vendor id', 'Release Date', 'Media'
        ]
        
        count = 0
        
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                
                for product in products:
                    row_data = ProductTransformer.transform_for_upload(product)
                    if row_data:
                        writer.writerow(row_data)
                        count += 1
        except Exception as e:
            raise Exception(f"Error generating CSV: {str(e)}")
        
        return count


class ProductTransformer:
    """Transform products for website upload"""
    
    @staticmethod
    def transform_for_upload(product: Product) -> Optional[Dict]:
        """
        Transform a Product into upload CSV format
        
        Applies vendor configuration (SKU prefix, pricing, defaults)
        """
        try:
            # Get vendor configuration
            website = Website.objects.filter(name__iexact=product.website).first()
            if not website:
                return None
            
            try:
                vendor_config = VendorConfiguration.objects.get(website=website, is_active=True)
            except VendorConfiguration.DoesNotExist:
                # No vendor config - skip or use defaults
                return None
            
            # Get sync status for custom overrides
            sync_status = None
            try:
                sync_status = ProductSyncStatus.objects.get(product=product)
            except ProductSyncStatus.DoesNotExist:
                pass
            
            # Transform SKU
            transformed_sku = vendor_config.apply_sku_transform(product.sku or '')
            
            # Transform price
            price = sync_status.custom_price if (sync_status and sync_status.custom_price) else product.price
            transformed_price = vendor_config.apply_price_markup(price or '$0.00')
            # Remove $ sign for CSV
            transformed_price = transformed_price.replace('$', '').strip()
            
            # Get category
            category_id = ''
            if sync_status and sync_status.custom_category_id:
                category_id = sync_status.custom_category_id
            elif vendor_config.default_category_id:
                category_id = vendor_config.default_category_id
            
            # Get inventory settings
            if sync_status and sync_status.custom_track_inventory is not None:
                track_inventory = sync_status.custom_track_inventory
            else:
                track_inventory = vendor_config.track_inventory
            
            if sync_status and sync_status.custom_sell_out_of_stock is not None:
                sell_out_of_stock = sync_status.custom_sell_out_of_stock
            else:
                sell_out_of_stock = vendor_config.sell_out_of_stock
            
            # Build row
            row = {
                'SKU': transformed_sku,
                'Title': product.name or '',
                'Categories': category_id,
                'List Price': transformed_price,
                'Length': '',  # Not available in scraped data
                'Height': '',
                'Width': '',
                'Weight': '',
                'Description': product.description or '',
                'Short Desc': '',  # Could extract from description if needed
                'Product Type Id': vendor_config.default_product_type_id,
                'Sell Out of stock': 'TRUE' if sell_out_of_stock else 'FALSE',
                'Track Inventory': 'TRUE' if track_inventory else 'FALSE',
                'Vendor id': str(vendor_config.vendor_id),
                'Release Date': '',  # Not available
                'Media': product.image_link or '',
            }
            
            return row
            
        except Exception as e:
            print(f"Error transforming product {product.id}: {e}")
            return None
    
    @staticmethod
    def get_price_numeric(price_str: str) -> float:
        """Extract numeric price from string"""
        try:
            # Remove currency symbols and commas
            clean_price = re.sub(r'[^0-9.]', '', price_str)
            return float(clean_price) if clean_price else 0.0
        except:
            return 0.0


class SyncStatistics:
    """Calculate sync statistics"""
    
    @staticmethod
    def get_sync_stats() -> Dict:
        """Get overall sync statistics"""
        total_products = Product.objects.count()
        
        # Products with sync status
        synced_count = ProductSyncStatus.objects.filter(on_website=True).count()
        new_count = ProductSyncStatus.objects.filter(status='new').count()
        
        # Products without sync status (never checked)
        untracked_count = total_products - ProductSyncStatus.objects.count()
        
        # Selected for export
        selected_count = ProductSyncStatus.objects.filter(selected_for_export=True).count()
        
        return {
            'total_products': total_products,
            'on_website': synced_count,
            'new_products': new_count + untracked_count,  # Include untracked as new
            'selected_for_export': selected_count,
            'untracked': untracked_count,
        }
    
    @staticmethod
    def get_vendor_stats() -> List[Dict]:
        """Get statistics per vendor"""
        vendors = []
        
        for website in Website.objects.filter(is_active=True):
            total = Product.objects.filter(website__iexact=website.name).count()
            
            # Get products with sync status
            product_ids = Product.objects.filter(website__iexact=website.name).values_list('id', flat=True)
            on_website = ProductSyncStatus.objects.filter(
                product_id__in=product_ids,
                on_website=True
            ).count()
            
            new = total - on_website
            
            try:
                vendor_config = VendorConfiguration.objects.get(website=website)
                has_config = True
            except VendorConfiguration.DoesNotExist:
                vendor_config = None
                has_config = False
            
            vendors.append({
                'website': website,
                'vendor_config': vendor_config,
                'has_config': has_config,
                'total_products': total,
                'on_website': on_website,
                'new_products': new,
            })
        
        return vendors
