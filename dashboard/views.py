from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from .forms import BootstrapAuthenticationForm
from scraper.models import Website, ScrapingSession, ScrapingState, ScrapingLog, Product, GoogleSheetLinks
from scraper.utils import (
    start_scraping_session,
    stop_scraping_session,
    resume_scraping_session,
    get_website_status,
    get_session_logs,
    initialize_websites,
    force_stop_all_scraping,
    recover_stuck_sessions,
)
import json
import csv
import xlsxwriter
from io import BytesIO
from django.utils import timezone
from django.conf import settings
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
from googleapiclient.http import MediaIoBaseUpload


@login_required(login_url='login')
def home(request):
    """Enhanced home view with scraping management"""
    
    # Initialize websites if they don't exist
    if not Website.objects.exists():
        initialize_websites()
    
    # Get all websites and their current status
    websites = Website.objects.filter(is_active=True)
    
    # Categorize websites into fast (Shopify) and slow (Custom HTML) scrapers
    # Shopify scrapers use products.json API (fast)
    # Custom scrapers parse HTML pages (slow)
    custom_scraper_types = [
        'meiros', 'ritelite', 'shaijudaica', 'jewisheducationaltoys',
        'legacyjudaica', 'simchonim', 'kaftorjudaica', 'mefoarjudaica',
        'ozvehadar', 'craftsandmore', 'zionjudaica', 'toys4u', 'feldheim'
    ]
    
    fast_websites = []  # Shopify websites
    slow_websites = []  # Custom HTML scrapers
    
    for website in websites:
        status = get_website_status(website.id)
        
        # Check if it's a custom scraper (slow) or Shopify (fast)
        scraper_function = website.scraper_function.lower()
        is_custom = any(scraper_type in scraper_function for scraper_type in custom_scraper_types)
        
        if is_custom:
            slow_websites.append(status)
        else:
            fast_websites.append(status)
    
    # Get recent sessions with improved grouping
    all_sessions = ScrapingSession.objects.select_related('website', 'started_by').order_by('-started_at')
    
    # Group sessions by "session chains" (original + resumes)
    session_groups = []
    processed_sessions = set()
    
    for session in all_sessions[:20]:  # Get more sessions to process
        if session.id in processed_sessions:
            continue
            
        # Check if this is a resumed session
        if session.resume_data.get('resumed_from_session'):
            continue  # Skip resumed sessions, they'll be grouped with original
        
        # This is an original session, find all its resumes
        session_group = {
            'original': session,
            'resumes': [],
            'latest_session': session,
            'latest_status': session.status,
            'total_scraped': session.products_scraped,
            'total_created': session.products_created,
            'total_updated': session.products_updated,
            'total_failed': session.products_failed,
            'is_active': session.status in ['running', 'pending']
        }
        
        # Find all resumes of this session
        resumes = ScrapingSession.objects.filter(
            resume_data__resumed_from_session=session.id
        ).order_by('started_at')
        
        for resume in resumes:
            session_group['resumes'].append(resume)
            processed_sessions.add(resume.id)
            
            # Update with latest session data
            if resume.started_at > session_group['latest_session'].started_at:
                session_group['latest_session'] = resume
                session_group['latest_status'] = resume.status
                session_group['total_scraped'] = resume.products_scraped
                session_group['total_created'] = resume.products_created
                session_group['total_updated'] = resume.products_updated
                session_group['total_failed'] = resume.products_failed
                session_group['is_active'] = resume.status in ['running', 'pending']
        
        session_groups.append(session_group)
        processed_sessions.add(session.id)
        
        # Limit to 10 session groups
        if len(session_groups) >= 10:
            break
    
    # Get Google Sheet export status
    current_export = GoogleSheetLinks.objects.filter(status__in=['pending', 'processing']).first()
    latest_export = GoogleSheetLinks.objects.filter(status='completed').first()
    
    context = {
        'websites': websites,
        'fast_websites': fast_websites,  # Shopify-based (fast scrapers)
        'slow_websites': slow_websites,  # Custom HTML (slow scrapers)
        'session_groups': session_groups,
        'current_export': current_export,
        'latest_export': latest_export,
    }
    
    return render(request, 'index.html', context)

@login_required(login_url='login')
def start_scraping(request, website_id):
    """Start scraping for a specific website"""
    if request.method == 'POST':
        result = start_scraping_session(website_id, user=request.user)
        
        if result['success']:
            messages.success(request, result['message'])
        else:
            messages.error(request, result['message'])
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(result)
        
        return redirect('home')
    
    return redirect('home')

@login_required(login_url='login')
def stop_scraping(request, website_id):
    """Stop scraping for a specific website"""
    if request.method == 'POST':
        result = stop_scraping_session(website_id)
        
        if result['success']:
            messages.success(request, result['message'])
        else:
            messages.error(request, result['message'])
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(result)
        
        return redirect('home')
    
    return redirect('home')

@login_required(login_url='login')
def resume_scraping(request, session_id):
    """Resume a paused or failed scraping session"""
    if request.method == 'POST':
        result = resume_scraping_session(session_id, user=request.user)
        
        if result['success']:
            messages.success(request, result['message'])
        else:
            messages.error(request, result['message'])
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(result)
        
        return redirect('home')
    
    return redirect('home')

@login_required(login_url='login')
def website_status(request, website_id):
    """Get real-time status of a website's scraping operation"""
    status = get_website_status(website_id)
    
    if status:
        return JsonResponse(status)
    else:
        return JsonResponse({'error': 'Website not found'}, status=404)

@login_required(login_url='login')
def session_details(request, session_id):
    """View details of a specific scraping session"""
    session = get_object_or_404(ScrapingSession, id=session_id)
    
    # Get logs for this session
    logs_data = get_session_logs(session_id, limit=200)
    
    context = {
        'session': session,
        'logs': logs_data.get('logs', []) if 'logs' in logs_data else [],
        'website_status': get_website_status(session.website.id)
    }
    
    return render(request, 'session_details.html', context)

@login_required(login_url='login')
def session_logs(request, session_id):
    """Get logs for a specific session (AJAX endpoint)"""
    limit = int(request.GET.get('limit', 100))
    logs_data = get_session_logs(session_id, limit)
    
    return JsonResponse(logs_data)

@login_required(login_url='login')
def session_data(request, session_id):
    """Get current session data for real-time updates (AJAX endpoint)"""
    try:
        session = ScrapingSession.objects.get(id=session_id)
        
        return JsonResponse({
            'id': session.id,
            'status': session.status,
            'total_products_found': session.total_products_found,
            'products_scraped': session.products_scraped,
            'products_created': session.products_created,
            'products_updated': session.products_updated,
            'products_failed': session.products_failed,
            'last_processed_index': session.last_processed_index,
            'started_at': session.started_at.isoformat(),
            'completed_at': session.completed_at.isoformat() if session.completed_at else None,
        })
    except ScrapingSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)

def user_login(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('home')
        
    if request.method == 'POST':
        form = BootstrapAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = BootstrapAuthenticationForm()

    return render(request, 'login.html', {'form': form})

@login_required(login_url='login')
def start_all_scraping(request):
    """Start scraping for all active websites"""
    if request.method == 'POST':
        websites = Website.objects.filter(is_active=True)
        results = []
        
        for website in websites:
            result = start_scraping_session(website.id, user=request.user)
            results.append(f"{website.name}: {result['message']}")
        
        if results:
            messages.success(request, f"Bulk operation completed: {'; '.join(results)}")
        else:
            messages.warning(request, "No active websites found to start scraping")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'results': results})
        
        return redirect('home')
    
    return redirect('home')

@login_required(login_url='login')
def stop_all_scraping(request):
    """
    Force-stop ALL running/pending scraping sessions across every website.

    Uses force_stop_all_scraping() which:
    - Iterates the DB directly (not just ScrapingState.is_running) to catch orphans
    - Revokes each Celery task (swallows revoke errors for already-dead tasks)
    - Bulk-resets all ScrapingState records to idle
    """
    if request.method == 'POST':
        result = force_stop_all_scraping()

        if result['total_stopped'] > 0:
            messages.success(
                request,
                f"Force-stopped {result['total_stopped']} scraping session(s): "
                + '; '.join(result['stopped'])
            )
        else:
            messages.warning(request, "No active scraping sessions found — all states reset to idle.")

        if result['errors']:
            messages.error(request, "Some errors occurred: " + '; '.join(result['errors']))

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, **result})

        return redirect('home')

    return redirect('home')


@login_required(login_url='login')
def recover_stuck_scrapers(request):
    """
    Manually trigger recovery of stuck scraping sessions.

    Scans all running/pending sessions, checks if their Celery tasks are
    actually alive, and marks dead/stale ones as failed. Also fixes
    orphaned ScrapingState records.

    Works for both GET (status-check JSON) and POST (trigger recovery).
    """
    if request.method == 'POST':
        try:
            count = recover_stuck_sessions()
            msg = (
                f"Recovery complete — {count} stuck session(s) recovered."
                if count > 0
                else "No stuck sessions found. Everything looks healthy."
            )
            messages.success(request, msg)

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'recovered': count, 'message': msg})

            return redirect('home')
        except Exception as e:
            error_msg = f"Recovery error: {str(e)}"
            messages.error(request, error_msg)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': error_msg}, status=500)
            return redirect('home')

    # GET: return current stuck-session info as JSON (useful for monitoring)
    from scraper.models import ScrapingSession
    from scraper.utils import is_celery_task_alive
    from django.utils import timezone as tz

    active = ScrapingSession.objects.filter(
        status__in=['running', 'pending']
    ).select_related('website').order_by('started_at')

    session_info = []
    for s in active:
        alive = is_celery_task_alive(s.celery_task_id)
        age_min = (tz.now() - s.started_at).total_seconds() / 60
        session_info.append({
            'id': s.id,
            'website': s.website.name,
            'status': s.status,
            'age_minutes': round(age_min, 1),
            'task_id': s.celery_task_id,
            'task_alive': alive,
            'likely_stuck': (
                alive is False
                or (alive is None and age_min > 15)
            ),
        })

    return JsonResponse({
        'active_sessions': session_info,
        'total_active': len(session_info),
        'likely_stuck': sum(1 for s in session_info if s['likely_stuck']),
    })

@login_required(login_url='login')
def start_all_fast_scraping(request):
    """Start scraping for all fast (Shopify) websites"""
    if request.method == 'POST':
        # Define custom scraper types (slow scrapers)
        custom_scraper_types = [
            'meiros', 'ritelite', 'shaijudaica', 'jewisheducationaltoys',
            'legacyjudaica', 'simchonim', 'kaftorjudaica', 'mefoarjudaica',
            'ozvehadar', 'craftsandmore', 'zionjudaica'
        ]
        
        # Get only fast websites (Shopify - not custom scrapers)
        websites = Website.objects.filter(is_active=True)
        fast_websites = [
            w for w in websites 
            if not any(scraper_type in w.scraper_function.lower() for scraper_type in custom_scraper_types)
        ]
        
        results = []
        for website in fast_websites:
            result = start_scraping_session(website.id, user=request.user)
            results.append(f"{website.name}: {result['message']}")
        
        if results:
            messages.success(request, f"Started {len(fast_websites)} fast Shopify scrapers: {'; '.join(results)}")
        else:
            messages.warning(request, "No fast scraping websites found")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'results': results, 'count': len(fast_websites)})
        
        return redirect('home')
    
    return redirect('home')

@login_required(login_url='login')
def stop_all_fast_scraping(request):
    """Stop scraping for all fast (Shopify) websites"""
    if request.method == 'POST':
        custom_scraper_types = [
            'meiros', 'ritelite', 'shaijudaica', 'jewisheducationaltoys',
            'legacyjudaica', 'simchonim', 'kaftorjudaica', 'mefoarjudaica',
            'ozvehadar', 'craftsandmore', 'zionjudaica'
        ]
        
        running_states = ScrapingState.objects.filter(is_running=True).select_related('website')
        fast_running = [
            state for state in running_states
            if not any(scraper_type in state.website.scraper_function.lower() for scraper_type in custom_scraper_types)
        ]
        
        results = []
        for state in fast_running:
            result = stop_scraping_session(state.website.id)
            results.append(f"{state.website.name}: {result['message']}")
        
        if results:
            messages.success(request, f"Stopped {len(fast_running)} fast scrapers: {'; '.join(results)}")
        else:
            messages.warning(request, "No running fast scraping sessions found")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'results': results})
        
        return redirect('home')
    
    return redirect('home')

@login_required(login_url='login')
def start_all_slow_scraping(request):
    """Start scraping for all slow (Custom HTML) websites"""
    if request.method == 'POST':
        # Define custom scraper types (slow scrapers)
        custom_scraper_types = [
            'meiros', 'ritelite', 'shaijudaica', 'jewisheducationaltoys',
            'legacyjudaica', 'simchonim', 'kaftorjudaica', 'mefoarjudaica',
            'ozvehadar', 'craftsandmore', 'zionjudaica'
        ]
        
        # Check if any fast scrapers are running
        running_states = ScrapingState.objects.filter(is_running=True).select_related('website')
        fast_running = [
            state for state in running_states
            if not any(scraper_type in state.website.scraper_function.lower() for scraper_type in custom_scraper_types)
        ]
        
        if fast_running:
            # Block slow scrapers from starting
            running_names = ', '.join([state.website.name for state in fast_running])
            messages.error(
                request, 
                f"Cannot start slow scrapers while fast scrapers are running. "
                f"Please wait for these to complete: {running_names}"
            )
            return redirect('home')
        
        # Get only slow websites (custom HTML scrapers)
        websites = Website.objects.filter(is_active=True)
        slow_websites = [
            w for w in websites 
            if any(scraper_type in w.scraper_function.lower() for scraper_type in custom_scraper_types)
        ]
        
        results = []
        for website in slow_websites:
            result = start_scraping_session(website.id, user=request.user)
            results.append(f"{website.name}: {result['message']}")
        
        if results:
            messages.success(request, f"Started {len(slow_websites)} slow HTML scrapers: {'; '.join(results)}")
        else:
            messages.warning(request, "No slow scraping websites found")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'results': results, 'count': len(slow_websites)})
        
        return redirect('home')
    
    return redirect('home')

@login_required(login_url='login')
def stop_all_slow_scraping(request):
    """Stop scraping for all slow (Custom HTML) websites"""
    if request.method == 'POST':
        custom_scraper_types = [
            'meiros', 'ritelite', 'shaijudaica', 'jewisheducationaltoys',
            'legacyjudaica', 'simchonim', 'kaftorjudaica', 'mefoarjudaica',
            'ozvehadar', 'craftsandmore', 'zionjudaica'
        ]
        
        running_states = ScrapingState.objects.filter(is_running=True).select_related('website')
        slow_running = [
            state for state in running_states
            if any(scraper_type in state.website.scraper_function.lower() for scraper_type in custom_scraper_types)
        ]
        
        results = []
        for state in slow_running:
            result = stop_scraping_session(state.website.id)
            results.append(f"{state.website.name}: {result['message']}")
        
        if results:
            messages.success(request, f"Stopped {len(slow_running)} slow scrapers: {'; '.join(results)}")
        else:
            messages.warning(request, "No running slow scraping sessions found")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'results': results})
        
        return redirect('home')
    
    return redirect('home')

@login_required(login_url='login')
def export_products(request):
    """Export products to CSV or Excel"""
    format_type = request.GET.get('format', 'csv')  # csv or excel
    website_id = request.GET.get('website_id', 'all')  # specific website or all
    
    # Get products based on filter
    if website_id == 'all':
        products = Product.objects.all().order_by('website', 'created_at')
        filename = f"all_products_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
    else:
        print(type(website_id))
        try:
            website = Website.objects.get(id=website_id)
            products = Product.objects.filter(website=website.name).order_by('created_at')
            filename = f"{website.name}_products_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        except Website.DoesNotExist:
            messages.error(request, "Website not found")
            return redirect('home')
    
    if not products.exists():
        messages.warning(request, "No products found to export")
        return redirect('home')
    
    if format_type == 'excel':
        return _export_excel(products, filename)
    elif format_type == 'google_sheet':
        return _export_google_sheet_background(request, website_id)
    else:
        return _export_csv(products, filename)

def _export_google_sheet_background(request, website_filter='all'):
    """Start Google Sheet export in background using Celery"""
    from scraper.tasks import export_products_to_google_sheet
    
    # Check if there's already an export running
    current_export = GoogleSheetLinks.objects.filter(status__in=['pending', 'processing']).first()
    
    if current_export:
        messages.warning(request, "An export is already in progress. Please wait for it to complete.")
        return redirect('home')
    
    # Create new export record
    export_record = GoogleSheetLinks.objects.create(
        status='pending',
        website_filter=website_filter if website_filter != 'all' else 'all'
    )
    
    # Start background task
    task = export_products_to_google_sheet.delay(export_record.id, website_filter)
    
    # Update with task ID
    export_record.celery_task_id = task.id
    export_record.save()
    
    messages.info(request, "Google Sheet export started in background. Check the status on the homepage.")
    return redirect('home')

def _export_csv(products, filename):
    """Export products to CSV format"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Website', 'Name', 'SKU', 'Price', 'Category','Vendor','InStock', 'Description', 'Image Link','Link', 'Created At', 'Updated At'])
    
    for product in products:
        writer.writerow([
            product.website,
            product.name,
            product.sku,
            product.price,
            product.category,
            product.vendor,
            "Yes" if product.in_stock else "No",
            product.description,
            product.image_link,
            product.link,
            product.created_at.strftime('%Y-%m-%d %H:%M:%S') if product.created_at else '',
            product.updated_at.strftime('%Y-%m-%d %H:%M:%S') if product.updated_at else ''
        ])
    
    return response

def _export_excel(products, filename):
    """Export products to Excel format"""
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('Products')
    
    # Add headers
    headers = ['Website', 'Name', 'SKU', 'Price', 'Category', 'Vendor', 'InStock','Description','Image Link', 'Link', 'Created At', 'Updated At']
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    
    # Add data
    for row, product in enumerate(products, start=1):
        worksheet.write(row, 0, product.website or '')
        worksheet.write(row, 1, product.name or '')
        worksheet.write(row, 2, product.sku or '')
        worksheet.write(row, 3, product.price or '')
        worksheet.write(row, 4, product.category or '')
        worksheet.write(row, 5, product.vendor or '')
        worksheet.write(row, 6, "Yes" if product.in_stock else "No")
        worksheet.write(row, 7, product.description or '')
        worksheet.write(row, 8, ", ".join(product.image_link.split(",")[:2]) or '')
        worksheet.write(row, 9, product.link or '')
        worksheet.write(row, 10, product.created_at.strftime('%Y-%m-%d %H:%M:%S') if product.created_at else '')
        worksheet.write(row, 11, product.updated_at.strftime('%Y-%m-%d %H:%M:%S') if product.updated_at else '')
    
    workbook.close()
    output.seek(0)
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
    
    return response

def _export_to_google_sheet(products, filename):
    SERVICE_ACCOUNT_FILE = os.path.join(settings.BASE_DIR, 'credentials', 'web-scraper-463601-05f99a6d168b.json')

    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

    # Step 1: Create Excel file in memory
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('Products')

    headers = ['Website', 'Name', 'SKU', 'Price', 'Category', 'Vendor', 'InStock', 'Description', 'Image Link', 'Link', 'Created At', 'Updated At']
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)

    for row, product in enumerate(products, start=1):
        worksheet.write(row, 0, product.website or '')
        worksheet.write(row, 1, product.name or '')
        worksheet.write(row, 2, product.sku or '')
        worksheet.write(row, 3, product.price or '')
        worksheet.write(row, 4, product.category or '')
        worksheet.write(row, 5, product.vendor or '')
        worksheet.write(row, 6, "Yes" if product.in_stock else "No")
        worksheet.write(row, 7, product.description or '')
        worksheet.write_string(row, 8, ", ".join(product.image_link.split(",")[:2]) or '')
        worksheet.write(row, 9, product.link or '')
        worksheet.write(row, 10, product.created_at.strftime('%Y-%m-%d %H:%M:%S') if product.created_at else '')
        worksheet.write(row, 11, product.updated_at.strftime('%Y-%m-%d %H:%M:%S') if product.updated_at else '')

    workbook.close()
    output.seek(0)

    # Step 2: Upload to Google Drive and convert
    drive_service = build('drive', 'v3', credentials=creds)
    media = MediaIoBaseUpload(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    file_metadata = {
        'name': filename,
        'mimeType': 'application/vnd.google-apps.spreadsheet'  # Convert to Google Sheet
    }

    uploaded_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    file_id = uploaded_file.get('id')

    # Step 3: Make it public
    drive_service.permissions().create(
        fileId=file_id,
        body={'type': 'anyone', 'role': 'reader'}
    ).execute()

    link = f"https://docs.google.com/spreadsheets/d/{file_id}"
    GoogleSheetLinks.objects.create(link=link)
    return link

@login_required(login_url='login')
def session_history(request, website_id):
    """Get session history for a specific website"""
    try:
        website = Website.objects.get(id=website_id)
        sessions = ScrapingSession.objects.filter(website=website).order_by('-started_at')
        
        # Group sessions by "session chain" (original + resumes)
        session_groups = []
        processed_sessions = set()
        
        for session in sessions:
            if session.id in processed_sessions:
                continue
                
            # Check if this is a resumed session
            if session.resume_data.get('resumed_from_session'):
                continue  # Skip resumed sessions, they'll be grouped with original
            
            # This is an original session, find all its resumes
            session_group = {
                'original': session,
                'resumes': [],
                'latest_status': session.status,
                'total_scraped': session.products_scraped,
                'total_created': session.products_created,
                'total_updated': session.products_updated,
                'total_failed': session.products_failed
            }
            
            # Find all resumes of this session
            resumes = ScrapingSession.objects.filter(
                website=website,
                resume_data__resumed_from_session=session.id
            ).order_by('started_at')
            
            for resume in resumes:
                session_group['resumes'].append(resume)
                processed_sessions.add(resume.id)
                
                # Update totals with latest data
                if resume.started_at > session.started_at:
                    session_group['latest_status'] = resume.status
                    session_group['total_scraped'] = resume.products_scraped
                    session_group['total_created'] = resume.products_created
                    session_group['total_updated'] = resume.products_updated
                    session_group['total_failed'] = resume.products_failed
            
            session_groups.append(session_group)
            processed_sessions.add(session.id)
        
        return JsonResponse({
            'website_name': website.name,
            'session_groups': [
                {
                    'original_id': group['original'].id,
                    'started_at': group['original'].started_at.isoformat(),
                    'latest_status': group['latest_status'],
                    'resume_count': len(group['resumes']),
                    'total_scraped': group['total_scraped'],
                    'total_created': group['total_created'],
                    'total_updated': group['total_updated'],
                    'total_failed': group['total_failed'],
                    'resumes': [
                        {
                            'id': resume.id,
                            'started_at': resume.started_at.isoformat(),
                            'status': resume.status,
                            'products_scraped': resume.products_scraped
                        } for resume in group['resumes']
                    ]
                } for group in session_groups
            ]
        })
        
    except Website.DoesNotExist:
        return JsonResponse({'error': 'Website not found'}, status=404)

@login_required(login_url='login')
def export_status(request, export_id):
    """Get export status (AJAX endpoint)"""
    try:
        export_record = GoogleSheetLinks.objects.get(id=export_id)
        
        return JsonResponse({
            'id': export_record.id,
            'status': export_record.status,
            'progress_percentage': export_record.progress_percentage,
            'total_products': export_record.total_products,
            'processed_products': export_record.processed_products,
            'filename': export_record.filename,
            'link': export_record.link,
            'error_message': export_record.error_message,
            'created_at': export_record.created_at.isoformat(),
            'completed_at': export_record.completed_at.isoformat() if export_record.completed_at else None,
        })
    except GoogleSheetLinks.DoesNotExist:
        return JsonResponse({'error': 'Export not found'}, status=404)

@login_required(login_url='login')
def cancel_export(request, export_id):
    """Cancel ongoing export (AJAX endpoint)"""
    if request.method == 'POST':
        try:
            export_record = GoogleSheetLinks.objects.get(id=export_id)
            
            if export_record.status in ['pending', 'processing']:
                # Try to revoke the Celery task
                if export_record.celery_task_id:
                    from celery import current_app
                    current_app.control.revoke(export_record.celery_task_id, terminate=True)
                
                # Update status
                export_record.status = 'failed'
                export_record.error_message = 'Export cancelled by user'
                export_record.save()
                
                return JsonResponse({'success': True, 'message': 'Export cancelled successfully'})
            else:
                return JsonResponse({'success': False, 'message': 'Export cannot be cancelled'})
                
        except GoogleSheetLinks.DoesNotExist:
            return JsonResponse({'error': 'Export not found'}, status=404)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

def user_logout(request):
    """User logout view"""
    logout(request)
    return redirect('login')
