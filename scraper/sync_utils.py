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
    def normalize_sku(sku: str) -> str:
        """
        Normalize SKU for comparison
        - Convert to uppercase
        - Remove/standardize special characters
        - Trim whitespace
        
        Examples:
            "kwpp-7" -> "KWPP7"
            "RLC/22-N" -> "RLC22N"
            " CBGL-2 " -> "CBGL2"
        """
        if not sku:
            return ''
        
        # Convert to uppercase and strip
        normalized = sku.upper().strip()
        
        # Remove common special characters but keep alphanumeric
        # This makes "RLC-22-N" and "RLC22N" match
        normalized = re.sub(r'[-_/\s]+', '', normalized)
        
        return normalized
    
    @staticmethod
    def extract_vendor_prefix(sku: str) -> List[Tuple[str, str]]:
        """
        Extract possible vendor prefixes from SKU
        Returns list of (prefix, base_sku) tuples for multiple attempts
        
        Examples:
            "RLKWPP-7" -> [("RL", "KWPP7"), ("RLC", "WPP7"), ("RLKW", "PP7"), ...]
            "NMNM30113" -> [("NM", "NM30113"), ("NMNM", "30113"), ...]
        """
        if not sku:
            return [('', '')]
        
        normalized = SKUMatcher.normalize_sku(sku)
        results = []
        
        # Try different prefix lengths (2 to 6 characters)
        for prefix_len in [2, 3, 4, 5, 6]:
            if len(normalized) > prefix_len:
                prefix = normalized[:prefix_len]
                base = normalized[prefix_len:]
                if base:  # Only add if base is not empty
                    results.append((prefix, base))
        
        # Also add the full SKU with no prefix
        results.append(('', normalized))
        
        return results
    
    @staticmethod
    def find_vendor_configs_by_sku(sku: str) -> List[VendorConfiguration]:
        """
        Find all possible vendor configurations that might match this SKU
        """
        if not sku:
            return []
        
        possible_prefixes = SKUMatcher.extract_vendor_prefix(sku)
        vendor_configs = []
        
        for prefix, _ in possible_prefixes:
            if prefix:
                # Normalize the prefix for comparison
                normalized_prefix = prefix
                
                # Try to find vendor configs with this prefix
                configs = VendorConfiguration.objects.filter(
                    is_active=True
                ).filter(
                    Q(sku_prefix__iexact=prefix) |
                    Q(sku_prefix__iexact=prefix + '-') |
                    Q(sku_prefix__iexact=prefix + '_')
                )
                
                vendor_configs.extend(configs)
        
        # Remove duplicates
        seen = set()
        unique_configs = []
        for config in vendor_configs:
            if config.id not in seen:
                seen.add(config.id)
                unique_configs.append(config)
        
        return unique_configs
    
    @staticmethod
    def match_product_by_sku(website_sku: str, website_product_id: str = '', vendor_website: str = None) -> Optional[Product]:
        """
        Match a product from website export to database product (returns first match only).
        
        Prefer match_all_products_by_sku() to handle duplicate-SKU scenarios correctly.
        """
        matches = SKUMatcher.match_all_products_by_sku(website_sku, website_product_id, vendor_website)
        return matches[0] if matches else None

    @staticmethod
    def match_all_products_by_sku(website_sku: str, website_product_id: str = '', vendor_website: str = None) -> List[Product]:
        """
        Match ALL database products that correspond to a website SKU.

        This is the correct method to use during import because the same SKU can
        legitimately exist on multiple DB rows (e.g. a Shopify store reused a SKU
        when it replaced a product, leaving the old row in our DB).  Marking every
        matching product as "On Website" keeps the sync state consistent and avoids
        phantom "New" products that confuse operators.

        Args:
            website_sku: SKU as it appears on the website (may include vendor prefix)
            website_product_id: Product ID from website export (not used for matching)
            vendor_website: Vendor/website name — strongly recommended

        Returns:
            List of matched Product objects (may be empty, may have > 1 entry)
        """
        if not website_sku:
            return []

        normalized_website_sku = SKUMatcher.normalize_sku(website_sku)
        matched: List[Product] = []
        seen_ids: set = set()

        if vendor_website:
            # ---------- vendor-scoped matching ----------
            try:
                website_obj = Website.objects.get(name__iexact=vendor_website, is_active=True)
                vendor_config = VendorConfiguration.objects.get(website=website_obj, is_active=True)
            except (Website.DoesNotExist, VendorConfiguration.DoesNotExist):
                vendor_config = None

            # Level 1 – exact case-insensitive match
            for p in Product.objects.filter(website__iexact=vendor_website, sku__iexact=website_sku):
                if p.id not in seen_ids:
                    matched.append(p)
                    seen_ids.add(p.id)

            # Level 2 – strip vendor prefix then exact match
            if vendor_config and vendor_config.sku_prefix:
                if website_sku.upper().startswith(vendor_config.sku_prefix.upper()):
                    base_sku = website_sku[len(vendor_config.sku_prefix):]
                    for p in Product.objects.filter(website__iexact=vendor_website, sku__iexact=base_sku):
                        if p.id not in seen_ids:
                            matched.append(p)
                            seen_ids.add(p.id)

            # Level 3 – normalised match (handles punctuation/spacing differences)
            for p in Product.objects.filter(website__iexact=vendor_website):
                if p.id in seen_ids:
                    continue
                p_norm = SKUMatcher.normalize_sku(p.sku or '')
                if p_norm == normalized_website_sku:
                    matched.append(p)
                    seen_ids.add(p.id)
                    continue
                if vendor_config and vendor_config.sku_prefix:
                    prefix_norm = SKUMatcher.normalize_sku(vendor_config.sku_prefix)
                    if normalized_website_sku.startswith(prefix_norm):
                        base_norm = normalized_website_sku[len(prefix_norm):]
                        if p_norm == base_norm:
                            matched.append(p)
                            seen_ids.add(p.id)

            return matched

        # ---------- fallback: no vendor filter ----------
        for p in Product.objects.filter(sku__iexact=website_sku):
            if p.id not in seen_ids:
                matched.append(p)
                seen_ids.add(p.id)

        if not matched:
            for p in Product.objects.all():
                if p.id in seen_ids:
                    continue
                if SKUMatcher.normalize_sku(p.sku or '') == normalized_website_sku:
                    matched.append(p)
                    seen_ids.add(p.id)

        return matched
    
    @staticmethod
    def _match_with_vendor_filter(website_sku: str, normalized_sku: str, vendor_website: str) -> Optional[Product]:
        """
        Match within a specific vendor's products
        
        Strategy:
        1. Try exact match with original SKU (case-insensitive)
        2. If vendor has prefix, remove it and try matching
        3. As fallback, try normalized matching (for edge cases)
        """
        
        # Get vendor configuration
        try:
            website_obj = Website.objects.get(name__iexact=vendor_website, is_active=True)
            vendor_config = VendorConfiguration.objects.get(website=website_obj, is_active=True)
        except (Website.DoesNotExist, VendorConfiguration.DoesNotExist):
            vendor_config = None
        
        # LEVEL 1: Try exact match with original SKU (case-insensitive, keeps special chars)
        product = Product.objects.filter(
            website__iexact=vendor_website,
            sku__iexact=website_sku
        ).first()
        
        if product:
            return product
        
        # LEVEL 2: If vendor has prefix, try removing it (preserve special chars)
        if vendor_config and vendor_config.sku_prefix:
            # Remove prefix (case-insensitive)
            if website_sku.upper().startswith(vendor_config.sku_prefix.upper()):
                # Remove prefix keeping original case and special chars
                base_sku = website_sku[len(vendor_config.sku_prefix):]
                
                # Try matching base SKU
                product = Product.objects.filter(
                    website__iexact=vendor_website,
                    sku__iexact=base_sku
                ).first()
                
                if product:
                    return product
        
        # LEVEL 3: Fallback - normalized matching (for edge cases with inconsistent formatting)
        # This handles cases where special chars might differ
        for product in Product.objects.filter(website__iexact=vendor_website):
            product_sku_normalized = SKUMatcher.normalize_sku(product.sku or '')
            
            # Try with full website SKU normalized
            if product_sku_normalized == normalized_sku:
                return product
            
            # Try with prefix removed and normalized
            if vendor_config and vendor_config.sku_prefix:
                prefix_normalized = SKUMatcher.normalize_sku(vendor_config.sku_prefix)
                if normalized_sku.startswith(prefix_normalized):
                    base_normalized = normalized_sku[len(prefix_normalized):]
                    if product_sku_normalized == base_normalized:
                        return product
        
        return None
    
    @staticmethod
    def _match_with_vendor_prefix(website_sku: str, normalized_sku: str) -> Optional[Product]:
        """Match by detecting vendor prefix"""
        
        # Get possible vendor configurations
        vendor_configs = SKUMatcher.find_vendor_configs_by_sku(website_sku)
        
        for vendor_config in vendor_configs:
            website_name = vendor_config.website.name
            prefix_normalized = SKUMatcher.normalize_sku(vendor_config.sku_prefix)
            
            # Try to extract base SKU
            if normalized_sku.startswith(prefix_normalized):
                base_sku = normalized_sku[len(prefix_normalized):]
                
                # Try matching with base SKU
                products = Product.objects.filter(
                    website__iexact=website_name
                )
                
                for product in products:
                    product_sku_normalized = SKUMatcher.normalize_sku(product.sku or '')
                    if product_sku_normalized == base_sku:
                        return product
                    # Also try if product SKU matches the full SKU
                    if product_sku_normalized == normalized_sku:
                        return product
        
        return None
    
    @staticmethod
    def _match_direct_sku(website_sku: str, normalized_sku: str) -> Optional[Product]:
        """Direct SKU matching without prefix logic"""
        
        # Try exact match (case-insensitive)
        product = Product.objects.filter(sku__iexact=website_sku).first()
        if product:
            return product
        
        # Try normalized match
        for product in Product.objects.all():
            if SKUMatcher.normalize_sku(product.sku or '') == normalized_sku:
                return product
        
        return None
    
    @staticmethod
    def _match_partial_sku(website_sku: str, normalized_sku: str) -> Optional[Product]:
        """Partial/fuzzy matching as last resort"""
        
        # Try contains match (be careful with this - only use for longer SKUs)
        if len(normalized_sku) >= 6:
            products = Product.objects.filter(
                Q(sku__icontains=website_sku) |
                Q(sku__icontains=normalized_sku)
            )
            
            # Return the closest match
            for product in products:
                product_normalized = SKUMatcher.normalize_sku(product.sku or '')
                # Check if it's a close match (at least 80% similar)
                if product_normalized == normalized_sku:
                    return product
                if normalized_sku in product_normalized or product_normalized in normalized_sku:
                    return product
        
        return None
    
    @staticmethod
    def find_all_matching_products(website_sku: str) -> List[Product]:
        """
        Find ALL products that match a SKU (to detect duplicates)
        Returns list of all matching products
        """
        if not website_sku:
            return []
        
        normalized_sku = SKUMatcher.normalize_sku(website_sku)
        matches = []
        seen_ids = set()
        
        # Get all possible matches
        for product in Product.objects.all():
            product_normalized = SKUMatcher.normalize_sku(product.sku or '')
            
            if product_normalized == normalized_sku:
                if product.id not in seen_ids:
                    matches.append(product)
                    seen_ids.add(product.id)
            elif product.sku and product.sku.upper() == website_sku.upper():
                if product.id not in seen_ids:
                    matches.append(product)
                    seen_ids.add(product.id)
        
        return matches
    
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
            'Sell Out of stock', 'Track Inventory', 'Vendor id', 'Release Date', 'Media', 'Visibility'
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
                'Visibility': 'TRUE'
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
