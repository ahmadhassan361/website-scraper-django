from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from .forms import BootstrapAuthenticationForm
from scraper.models import Website, ScrapingSession, ScrapingState, ScrapingLog, Product
from scraper.utils import (
    start_scraping_session, 
    stop_scraping_session, 
    resume_scraping_session, 
    get_website_status,
    get_session_logs,
    initialize_websites
)
import json
import csv
import xlsxwriter
from io import BytesIO
from django.utils import timezone

@login_required(login_url='login')
def home(request):
    """Enhanced home view with scraping management"""
    
    # Initialize websites if they don't exist
    if not Website.objects.exists():
        initialize_websites()
    
    # Get all websites and their current status
    websites = Website.objects.filter(is_active=True)
    website_statuses = []
    
    for website in websites:
        status = get_website_status(website.id)
        website_statuses.append(status)
    
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
    
    context = {
        'websites': websites,
        'website_statuses': website_statuses,
        'session_groups': session_groups,
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
    """Stop scraping for all running websites"""
    if request.method == 'POST':
        running_states = ScrapingState.objects.filter(is_running=True)
        results = []
        
        for state in running_states:
            result = stop_scraping_session(state.website.id)
            results.append(f"{state.website.name}: {result['message']}")
        
        if results:
            messages.success(request, f"Bulk stop completed: {'; '.join(results)}")
        else:
            messages.warning(request, "No running scraping sessions found")
        
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
    else:
        return _export_csv(products, filename)

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
        worksheet.write(row, 8, product.image_link or '')
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

def user_logout(request):
    """User logout view"""
    logout(request)
    return redirect('login')
