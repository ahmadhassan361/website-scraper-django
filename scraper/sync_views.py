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
    WebsiteImportLog, ProductExportLog
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
    Import products from website export CSV.
    Only one import is allowed at a time.
    """
    # ------------------------------------------------------------------
    # One-at-a-time enforcement
    # ------------------------------------------------------------------
    active_import = WebsiteImportLog.objects.filter(
        status__in=['pending', 'processing']
    ).order_by('-created_at').first()

    if active_import:
        return JsonResponse({
            'success': False,
            'already_running': True,
            'import_log_id': active_import.id,
            'vendor': active_import.vendor_website,
            'progress': active_import.progress_percentage,
            'status': active_import.status,
            'error': (
                f'An import is already running for "{active_import.vendor_website}" '
                f'({active_import.progress_percentage}% complete). '
                f'Please wait for it to finish before starting a new one.'
            )
        }, status=409)

    if 'csv_file' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'No file uploaded'}, status=400)

    csv_file = request.FILES['csv_file']
    vendor_website = request.POST.get('website', '')

    if not vendor_website:
        return JsonResponse({'success': False, 'error': 'Please select a vendor/website'}, status=400)

    if not csv_file.name.endswith('.csv'):
        return JsonResponse({'success': False, 'error': 'File must be a CSV'}, status=400)

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
        vendor_website=vendor_website,
        status='pending'
    )

    # Start background task
    task = import_website_products_task.delay(import_log.id, tmp_file_path, vendor_website)
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
    Export selected products to website upload CSV.
    Only one export is allowed at a time (enforced via ProductExportLog).
    """
    # ------------------------------------------------------------------
    # One-at-a-time enforcement
    # ------------------------------------------------------------------
    active_export = ProductExportLog.objects.filter(
        status__in=['pending', 'processing']
    ).order_by('-created_at').first()

    if active_export:
        return JsonResponse({
            'success': False,
            'already_running': True,
            'export_log_id': active_export.id,
            'progress': active_export.progress_percentage,
            'status': active_export.status,
            'error': (
                f'An export is already running ({active_export.progress_percentage}% complete). '
                f'Please wait for it to finish before starting a new one.'
            )
        }, status=409)

    # ------------------------------------------------------------------
    # Check for a recently-completed export that hasn't been downloaded yet
    # (completed within the last 24 hours and file still exists)
    # ------------------------------------------------------------------
    recent_completed = ProductExportLog.objects.filter(
        status='completed'
    ).order_by('-completed_at').first()

    if recent_completed and recent_completed.file_path:
        if os.path.exists(recent_completed.file_path):
            from datetime import timedelta
            age = timezone.now() - recent_completed.completed_at
            if age < timedelta(hours=24):
                return JsonResponse({
                    'success': False,
                    'pending_download': True,
                    'export_log_id': recent_completed.id,
                    'filename': recent_completed.filename,
                    'products_exported': recent_completed.products_exported,
                    'error': (
                        f'A completed export is waiting to be downloaded '
                        f'({recent_completed.products_exported} products). '
                        f'Please download it first.'
                    )
                }, status=409)

    # ------------------------------------------------------------------
    # Get selected products
    # ------------------------------------------------------------------
    selected_statuses = ProductSyncStatus.objects.filter(selected_for_export=True)
    selected_product_ids = list(selected_statuses.values_list('product_id', flat=True))

    if not selected_product_ids:
        total_sync_status = ProductSyncStatus.objects.count()
        return JsonResponse({
            'success': False,
            'error': f'No products selected for export. Total sync status records: {total_sync_status}'
        }, status=400)

    # Generate filename
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f'upload-products-to-website-{timestamp}.csv'

    # Create persistent export log record
    export_log = ProductExportLog.objects.create(
        filename=filename,
        total_products=len(selected_product_ids),
        status='pending',
        created_by=request.user,
    )

    # Start background task, passing the export_log_id
    task = export_products_to_website_task.delay(
        list(selected_product_ids),
        filename,
        export_log_id=export_log.id,
    )

    export_log.celery_task_id = task.id
    export_log.save()

    return JsonResponse({
        'success': True,
        'export_log_id': export_log.id,
        'filename': filename,
        'message': f'Exporting {len(selected_product_ids)} products...'
    })


@login_required
def export_log_status(request, export_log_id):
    """
    Get status of an export operation via ProductExportLog ID (persistent).
    """
    try:
        export_log = ProductExportLog.objects.get(id=export_log_id)
        return JsonResponse({
            'status': export_log.status,
            'progress': export_log.progress_percentage,
            'total_products': export_log.total_products,
            'products_exported': export_log.products_exported,
            'filename': export_log.filename,
            'error_message': export_log.error_message,
            'file_exists': bool(export_log.file_path and os.path.exists(export_log.file_path)),
        })
    except ProductExportLog.DoesNotExist:
        return JsonResponse({'error': 'Export log not found'}, status=404)


@login_required
def download_export_by_log(request, export_log_id):
    """
    Download the CSV file for a completed export using the ProductExportLog ID.
    """
    try:
        export_log = ProductExportLog.objects.get(id=export_log_id)
    except ProductExportLog.DoesNotExist:
        return HttpResponse('Export not found', status=404)

    if export_log.status != 'completed':
        return HttpResponse('Export not yet completed', status=400)

    file_path = export_log.file_path
    if not file_path or not os.path.exists(file_path):
        return HttpResponse('Export file not found on server', status=404)

    response = FileResponse(open(file_path, 'rb'), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{export_log.filename}"'
    return response


@login_required
def active_jobs_status(request):
    """
    Returns active import and export job information so the frontend can
    show persistent status banners after a page refresh.
    """
    # Active import
    active_import = WebsiteImportLog.objects.filter(
        status__in=['pending', 'processing']
    ).order_by('-created_at').first()

    # Most recent export: active OR recently-completed (last 24 hours with file present)
    active_export = ProductExportLog.objects.filter(
        status__in=['pending', 'processing']
    ).order_by('-created_at').first()

    recent_export = None
    if not active_export:
        from datetime import timedelta
        candidate = ProductExportLog.objects.filter(
            status='completed'
        ).order_by('-completed_at').first()
        if candidate and candidate.file_path and os.path.exists(candidate.file_path):
            age = timezone.now() - candidate.completed_at
            if age < timedelta(hours=24):
                recent_export = candidate

    import_data = None
    if active_import:
        import_data = {
            'id': active_import.id,
            'status': active_import.status,
            'progress': active_import.progress_percentage,
            'vendor': active_import.vendor_website,
            'filename': active_import.filename,
            'total_rows': active_import.total_rows,
            'processed_rows': active_import.processed_rows,
        }

    export_data = None
    export_obj = active_export or recent_export
    if export_obj:
        export_data = {
            'id': export_obj.id,
            'status': export_obj.status,
            'progress': export_obj.progress_percentage,
            'filename': export_obj.filename,
            'total_products': export_obj.total_products,
            'products_exported': export_obj.products_exported,
            'file_exists': bool(export_obj.file_path and os.path.exists(export_obj.file_path)),
        }

    return JsonResponse({
        'active_import': import_data,
        'active_export': export_data,
    })


@login_required
def export_status(request, task_id):
    """
    Legacy: Get status of export operation by Celery task ID.
    Kept for backward compatibility.
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
                'error': str(result.get('message', 'Unknown error')) if isinstance(result, dict) else 'Unknown error'
            })
    else:
        return JsonResponse({'status': 'processing', 'progress': 50})


@login_required
def download_export(request, filename):
    """
    Download exported CSV file by filename (legacy / direct).
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
