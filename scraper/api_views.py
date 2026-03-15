"""
API Views for Product Export
Provides REST API endpoints for third-party system integration
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination, CursorPagination
from django.db.models import Q
from .models import Product, Website
from .serializers import ProductExportSerializer, WebsiteListSerializer


class LargeResultsPagination(CursorPagination):
    """
    Cursor-based pagination for large datasets (100k+ records)
    More efficient than offset pagination for very large datasets
    """
    page_size = 1000  # Default: 1000 products per page
    page_size_query_param = 'page_size'
    max_page_size = 5000  # Maximum: 5000 products per page
    ordering = '-id'  # Order by ID descending (newest first)
    cursor_query_param = 'cursor'


class StandardResultsPagination(PageNumberPagination):
    """
    Standard page-based pagination (alternative option)
    Easier to use but less efficient for very large datasets
    """
    page_size = 1000
    page_size_query_param = 'page_size'
    max_page_size = 5000
    page_query_param = 'page'


class ProductExportViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API ViewSet for product export
    
    Provides:
    - GET /api/products/ - List all products with pagination
    - GET /api/products/{id}/ - Get single product details
    - GET /api/products/by_website/?website={name} - Filter by website
    - GET /api/products/summary/ - Get summary statistics
    
    Query Parameters:
    - page_size: Number of results per page (default: 1000, max: 5000)
    - cursor: Pagination cursor for next/previous page
    - website: Filter by website name
    - search: Search in name, sku, description
    - in_stock: Filter by stock status (true/false)
    - ordering: Order results (e.g., 'name', '-created_at')
    """
    serializer_class = ProductExportSerializer
    pagination_class = LargeResultsPagination
    
    def get_queryset(self):
        """
        Get queryset with optional filtering
        Optimized for large datasets with select_related and prefetch_related
        """
        queryset = Product.objects.all().order_by('-id')
        
        # Filter by website
        website = self.request.query_params.get('website', None)
        if website:
            queryset = queryset.filter(website__iexact=website)
        
        # Filter by stock status
        in_stock = self.request.query_params.get('in_stock', None)
        if in_stock is not None:
            if in_stock.lower() == 'true':
                queryset = queryset.filter(in_stock=True)
            elif in_stock.lower() == 'false':
                queryset = queryset.filter(in_stock=False)
        
        # Search functionality
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(sku__icontains=search) |
                Q(description__icontains=search) |
                Q(category__icontains=search) |
                Q(vendor__icontains=search)
            )
        
        # Custom ordering
        ordering = self.request.query_params.get('ordering', None)
        if ordering:
            # Validate ordering field to prevent SQL injection
            valid_orderings = ['id', '-id', 'name', '-name', 'created_at', '-created_at', 
                             'updated_at', '-updated_at', 'price', '-price', 'website', '-website']
            if ordering in valid_orderings:
                queryset = queryset.order_by(ordering)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def by_website(self, request):
        """
        Get products filtered by website name
        
        Example: /api/products/by_website/?website=waterdalecollection
        """
        website_name = request.query_params.get('website', None)
        
        if not website_name:
            return Response(
                {'error': 'Please provide website parameter'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if website exists
        try:
            website = Website.objects.get(name__iexact=website_name)
        except Website.DoesNotExist:
            return Response(
                {'error': f'Website "{website_name}" not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        queryset = Product.objects.filter(website__iexact=website_name).order_by('-id')
        
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get summary statistics about products
        
        Example: /api/products/summary/
        """
        total_products = Product.objects.count()
        in_stock_count = Product.objects.filter(in_stock=True).count()
        out_of_stock_count = Product.objects.filter(in_stock=False).count()
        
        # Products per website
        websites = Website.objects.all()
        website_stats = []
        for website in websites:
            count = Product.objects.filter(website=website.name).count()
            website_stats.append({
                'website': website.name,
                'product_count': count,
                'is_active': website.is_active
            })
        
        summary_data = {
            'total_products': total_products,
            'in_stock': in_stock_count,
            'out_of_stock': out_of_stock_count,
            'websites': website_stats,
            'api_info': {
                'default_page_size': 1000,
                'max_page_size': 5000,
                'pagination_type': 'cursor',
                'supported_filters': ['website', 'in_stock', 'search'],
                'supported_ordering': ['id', 'name', 'created_at', 'updated_at', 'price', 'website']
            }
        }
        
        return Response(summary_data)
    
    @action(detail=False, methods=['get'])
    def websites(self, request):
        """
        Get list of all available websites
        
        Example: /api/products/websites/
        """
        websites = Website.objects.all().order_by('name')
        serializer = WebsiteListSerializer(websites, many=True)
        return Response(serializer.data)


class ProductBulkExportViewSet(viewsets.ViewSet):
    """
    Optimized bulk export for very large datasets
    Uses streaming response for memory efficiency
    """
    
    @action(detail=False, methods=['get'])
    def stream(self, request):
        """
        Stream all products in JSON format
        Memory-efficient for very large datasets
        
        Example: /api/bulk-export/stream/?website=waterdalecollection
        """
        from django.http import StreamingHttpResponse
        import json
        
        # Get filters
        website = request.query_params.get('website', None)
        
        # Build queryset
        queryset = Product.objects.all().order_by('id')
        if website:
            queryset = queryset.filter(website__iexact=website)
        
        def stream_products():
            """Generator function to stream products"""
            yield '{"products": ['
            
            first = True
            batch_size = 1000
            
            # Process in batches to avoid loading all records into memory
            total = queryset.count()
            for offset in range(0, total, batch_size):
                batch = queryset[offset:offset + batch_size]
                
                for product in batch:
                    if not first:
                        yield ','
                    first = False
                    
                    # Serialize product data
                    data = {
                        'id': product.id,
                        'product_variant_id': product.product_variant_id,
                        'website': product.website,
                        'name': product.name,
                        'sku': product.sku,
                        'price': product.price,
                        'category': product.category,
                        'vendor': product.vendor,
                        'in_stock': product.in_stock,
                        'in_stock_display': "Yes" if product.in_stock else "No",
                        'description': product.description,
                        'image_link': product.image_link,
                        'link': product.link,
                        'created_at': product.created_at.isoformat() if product.created_at else None,
                        'updated_at': product.updated_at.isoformat() if product.updated_at else None,
                    }
                    yield json.dumps(data)
            
            yield '], "total": ' + str(total) + '}'
        
        response = StreamingHttpResponse(
            stream_products(),
            content_type='application/json'
        )
        response['Content-Disposition'] = 'attachment; filename="products_export.json"'
        return response
