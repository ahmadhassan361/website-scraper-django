"""
Views for Product Sync System
Handles vendor management, product sync dashboard, import/export operations
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.utils import timezone
from django.conf import settings
import os
import csv

from .models import (
    Website, Product, VendorConfiguration, ProductSyncStatus, 
    WebsiteImportLog
)
from .sync_utils import SyncStatistics, SKUMatcher, CSVParser
from .tasks import import_website_products_task, export_products_to_website_task


@login_required
def vendor_management(request):
    """
    Vendor management dashboard
    Shows all websites and their vendor configurations
    """
    websites = Website.objects.filter(is_active=True).order_by('name')
    
    vendors_data = []
    for website in websites:
        try:
            vendor_config = VendorConfiguration.objects.get(website=website)
            has_config = True
        except VendorConfiguration.DoesNotExist:
            vendor_config = None
            has_config = False
        
        # Get product count
        product_count = Product.objects.filter(website__iexact=website.name).count()
        
        vendors_data.append({
            'website': website,
            'vendor_config': vendor_config,
            'has_config': has_config,
            'product_count': product_count,
        })
    
    context = {
        'vendors': vendors_data,
        'page_title': 'Vendor Management',
    }
    
    return render(request, 'scraper/vendor_management.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def vendor_config_edit(request, website_id):
    """
    Edit or create vendor configuration
    """
    website = get_object_or_404(Website, id=website_id)
    
    try:
        vendor_config = VendorConfiguration.objects.get(website=website)
    except VendorConfiguration.DoesNotExist:
        vendor_config = None
    
    if request.method == 'POST':
        # Create or update vendor configuration
        vendor_id = request.POST.get('vendor_id')
        sku_prefix = request.POST.get('sku_prefix', '')
        markup_percentage = request.POST.get('markup_percentage', '0.00')
        default_category_id = request.POST.get('default_category_id', '')
        default_product_type_id = request.POST.get('default_product_type_id', '3')
        track_inventory = request.POST.get('track_inventory') == 'on'
        sell_out_of_stock = request.POST.get('sell_out_of_stock') == 'on'
        
        if vendor_config:
            # Update existing
            vendor_config.vendor_id = vendor_id
            vendor_config.sku_prefix = sku_prefix
            vendor_config.markup_percentage = markup_percentage
            vendor_config.default_category_id = default_category_id
            vendor_config.default_product_type_id = default_product_type_id
            vendor_config.track_inventory = track_inventory
            vendor_config.sell_out_of_stock = sell_out_of_stock
            vendor_config.save()
        else:
            # Create new
            vendor_config = VendorConfiguration.objects.create(
                website=website,
                vendor_id=vendor_id,
                sku_prefix=sku_prefix,
                markup_percentage=markup_percentage,
                default_category_id=default_category_id,
                default_product_type_id=default_product_type_id,
                track_inventory=track_inventory,
                sell_out_of_stock=sell_out_of_stock,
            )
        
        return JsonResponse({
            'success': True,
            'message': 'Vendor configuration saved successfully'
        })
    
    context = {
        'website': website,
        'vendor_config': vendor_config,
    }
    
    return render(request, 'scraper/vendor_config_edit.html', context)


@login_required
def product_sync_dashboard(request):
    """
    Main product sync dashboard
    Shows overall statistics and product sync status
    """
    # Get overall statistics
    stats = SyncStatistics.get_sync_stats()
    vendor_stats = SyncStatistics.get_vendor_stats()
    
    # Get filter parameters
    website_filter = request.GET.get('website', 'all')
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('q', '')
    
    # Build query
    products_query = Product.objects.all()
    
    if website_filter != 'all':
        products_query = products_query.filter(website__iexact=website_filter)
    
    # Join with sync status
    products = products_query.select_related().order_by('-updated_at')
    
    # Apply status filter
    if status_filter == 'new':
        # Products not on website (excluding disabled)
        synced_product_ids = ProductSyncStatus.objects.filter(
            on_website=True
        ).values_list('product_id', flat=True)
        disabled_product_ids = ProductSyncStatus.objects.filter(
            is_disabled=True
        ).values_list('product_id', flat=True)
        products = products.exclude(id__in=synced_product_ids).exclude(id__in=disabled_product_ids)
    elif status_filter == 'synced':
        # Products on website (excluding disabled)
        synced_product_ids = ProductSyncStatus.objects.filter(
            on_website=True,
            is_disabled=False
        ).values_list('product_id', flat=True)
        products = products.filter(id__in=synced_product_ids)
    elif status_filter == 'selected':
        # Products selected for export (excluding disabled)
        selected_product_ids = ProductSyncStatus.objects.filter(
            selected_for_export=True,
            is_disabled=False
        ).values_list('product_id', flat=True)
        products = products.filter(id__in=selected_product_ids)
    elif status_filter == 'disabled':
        # Disabled products only
        disabled_product_ids = ProductSyncStatus.objects.filter(
            is_disabled=True
        ).values_list('product_id', flat=True)
        products = products.filter(id__in=disabled_product_ids)
    else:
        # 'all' - exclude disabled products from normal view
        disabled_product_ids = ProductSyncStatus.objects.filter(
            is_disabled=True
        ).values_list('product_id', flat=True)
        products = products.exclude(id__in=disabled_product_ids)
    
    # Apply search
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(sku__icontains=search_query) |
            Q(category__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(products, 50)  # 50 products per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Attach sync status to each product
    products_with_status = []
    for product in page_obj:
        try:
            sync_status = ProductSyncStatus.objects.get(product=product)
        except ProductSyncStatus.DoesNotExist:
            sync_status = None
        
        products_with_status.append({
            'product': product,
            'sync_status': sync_status,
        })
    
    context = {
        'stats': stats,
        'vendor_stats': vendor_stats,
        'products': products_with_status,
        'page_obj': page_obj,
        'website_filter': website_filter,
        'status_filter': status_filter,
        'search_query': search_query,
        'websites': Website.objects.filter(is_active=True).order_by('name'),
        'page_title': 'Product Sync Dashboard',
    }
    
    return render(request, 'scraper/product_sync_dashboard.html', context)


@login_required
@require_http_methods(["POST"])
def toggle_product_selection(request):
    """
    Toggle product selection for export
    """
    product_id = request.POST.get('product_id')
    
    try:
        product = Product.objects.get(id=product_id)
        
        # Get or create sync status
        sync_status, created = ProductSyncStatus.objects.get_or_create(
            product=product,
            defaults={'status': 'new'}
        )
        
        # Toggle selection
        sync_status.selected_for_export = not sync_status.selected_for_export
        sync_status.save()
        
        return JsonResponse({
            'success': True,
            'selected': sync_status.selected_for_export
        })
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found'
        }, status=404)


@login_required
@require_http_methods(["POST"])
def bulk_select_products(request):
    """
    Bulk select/deselect products for export
    """
    action = request.POST.get('action')  # 'select_all', 'deselect_all', 'select_new'
    website_filter = request.POST.get('website', 'all')
    
    products_query = Product.objects.all()
    
    if website_filter != 'all':
        products_query = products_query.filter(website__iexact=website_filter)
    
    if action == 'select_new':
        # Select only new products (not on website)
        synced_product_ids = ProductSyncStatus.objects.filter(
            on_website=True
        ).values_list('product_id', flat=True)
        products_query = products_query.exclude(id__in=synced_product_ids)
    
    count = 0
    for product in products_query:
        sync_status, created = ProductSyncStatus.objects.get_or_create(
            product=product,
            defaults={'status': 'new'}
        )
        
        if action in ['select_all', 'select_new']:
            sync_status.selected_for_export = True
        else:  # deselect_all
            sync_status.selected_for_export = False
        
        sync_status.save()
        count += 1
    
    return JsonResponse({
        'success': True,
        'count': count,
        'message': f'{count} products updated'
    })


@login_required
@require_http_methods(["POST"])
def import_website_products(request):
    """
    Import products from website export CSV
    Upload CSV file and start background task
    """
    if 'csv_file' not in request.FILES:
        return JsonResponse({
            'success': False,
            'error': 'No file uploaded'
        }, status=400)
    
    csv_file = request.FILES['csv_file']
    vendor_website = request.POST.get('website', '')
    
    # Validate vendor selection
    if not vendor_website:
        return JsonResponse({
            'success': False,
            'error': 'Please select a vendor/website'
        }, status=400)
    
    # Validate file
    if not csv_file.name.endswith('.csv'):
        return JsonResponse({
            'success': False,
            'error': 'File must be a CSV'
        }, status=400)
    
    # Save file temporarily
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='wb') as tmp_file:
        for chunk in csv_file.chunks():
            tmp_file.write(chunk)
        tmp_file_path = tmp_file.name
    
    # Create import log
    import_log = WebsiteImportLog.objects.create(
        filename=csv_file.name,
        uploaded_by=request.user,
        vendor_website=vendor_website,  # Store vendor
        status='pending'
    )
    
    # Start background task with vendor filter
    task = import_website_products_task.delay(import_log.id, tmp_file_path, vendor_website)
    
    # Update task ID
    import_log.celery_task_id = task.id
    import_log.save()
    
    return JsonResponse({
        'success': True,
        'import_log_id': import_log.id,
        'vendor': vendor_website,
        'message': f'Import started for {vendor_website}'
    })


@login_required
def import_status(request, import_log_id):
    """
    Get status of import operation
    """
    try:
        import_log = WebsiteImportLog.objects.get(id=import_log_id)
        
        return JsonResponse({
            'status': import_log.status,
            'progress': import_log.progress_percentage,
            'total_rows': import_log.total_rows,
            'processed_rows': import_log.processed_rows,
            'matched_products': import_log.matched_products,
            'new_products_found': import_log.new_products_found,
            'skipped_rows': import_log.skipped_rows,
            'error_message': import_log.error_message,
            'unmatched_products': import_log.unmatched_products if hasattr(import_log, 'unmatched_products') else [],
        })
    except WebsiteImportLog.DoesNotExist:
        return JsonResponse({
            'error': 'Import log not found'
        }, status=404)


@login_required
@require_http_methods(["POST"])
def export_selected_products(request):
    """
    Export selected products to website upload CSV
    """
    # Get selected products
    selected_statuses = ProductSyncStatus.objects.filter(selected_for_export=True)
    selected_product_ids = list(selected_statuses.values_list('product_id', flat=True))
    
    # Debug logging
    print(f"DEBUG: Total ProductSyncStatus records: {ProductSyncStatus.objects.count()}")
    print(f"DEBUG: Selected for export: {selected_statuses.count()}")
    print(f"DEBUG: Selected product IDs: {selected_product_ids}")
    
    if not selected_product_ids:
        # Return detailed error
        total_sync_status = ProductSyncStatus.objects.count()
        return JsonResponse({
            'success': False,
            'error': f'No products selected for export. Total sync status records: {total_sync_status}'
        }, status=400)
    
    # Generate filename
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f'upload-products-to-website-{timestamp}.csv'
    
    # Start background task
    task = export_products_to_website_task.delay(
        list(selected_product_ids),
        filename
    )
    
    return JsonResponse({
        'success': True,
        'task_id': task.id,
        'filename': filename,
        'message': f'Exporting {len(selected_product_ids)} products...'
    })


@login_required
def export_status(request, task_id):
    """
    Get status of export operation
    """
    from celery.result import AsyncResult
    
    task_result = AsyncResult(task_id)
    
    if task_result.ready():
        result = task_result.result
        if isinstance(result, dict) and result.get('status') == 'completed':
            return JsonResponse({
                'status': 'completed',
                'filename': result.get('filename'),
                'file_path': result.get('file_path'),
                'products_exported': result.get('products_exported'),
            })
        else:
            return JsonResponse({
                'status': 'failed',
                'error': result.get('message', 'Unknown error')
            })
    else:
        return JsonResponse({
            'status': 'processing',
            'progress': 50,
        })


@login_required
def download_export(request, filename):
    """
    Download exported CSV file
    """
    file_path = os.path.join(settings.BASE_DIR, filename)
    
    if not os.path.exists(file_path):
        return HttpResponse('File not found', status=404)
    
    response = FileResponse(open(file_path, 'rb'), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


@login_required
@require_http_methods(["POST"])
def disable_product(request, product_id):
    """
    Disable a product (exclude from matching/export/normal display)
    """
    try:
        product = Product.objects.get(id=product_id)
        
        # Get or create sync status
        sync_status, created = ProductSyncStatus.objects.get_or_create(
            product=product,
            defaults={'status': 'new'}
        )
        
        # Disable the product
        sync_status.is_disabled = True
        sync_status.disabled_at = timezone.now()
        sync_status.disabled_reason = request.POST.get('reason', '')
        sync_status.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Product disabled successfully'
        })
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found'
        }, status=404)


@login_required
@require_http_methods(["POST"])
def enable_product(request, product_id):
    """
    Re-enable a disabled product
    """
    try:
        product = Product.objects.get(id=product_id)
        
        try:
            sync_status = ProductSyncStatus.objects.get(product=product)
            sync_status.is_disabled = False
            sync_status.disabled_at = None
            sync_status.disabled_reason = ''
            sync_status.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Product enabled successfully'
            })
        except ProductSyncStatus.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Product sync status not found'
            }, status=404)
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found'
        }, status=404)


@login_required
def import_history(request):
    """
    Show import history
    """
    imports = WebsiteImportLog.objects.all().order_by('-created_at')[:50]
    
    context = {
        'imports': imports,
        'page_title': 'Import History',
    }
    
    return render(request, 'scraper/import_history.html', context)
