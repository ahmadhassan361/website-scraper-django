"""
Serializers for Product API
"""
from rest_framework import serializers
from .models import Product, Website


class ProductExportSerializer(serializers.ModelSerializer):
    """
    Serializer for product export API
    Matches the format used in Google Sheets export
    """
    in_stock_display = serializers.SerializerMethodField()
    created_at_formatted = serializers.SerializerMethodField()
    updated_at_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id',
            'product_variant_id',
            'website',
            'name',
            'sku',
            'price',
            'category',
            'vendor',
            'in_stock',
            'in_stock_display',
            'description',
            'image_link',
            'link',
            'created_at',
            'created_at_formatted',
            'updated_at',
            'updated_at_formatted',
        ]
    
    def get_in_stock_display(self, obj):
        """Return 'Yes' or 'No' for in_stock field"""
        return "Yes" if obj.in_stock else "No"
    
    def get_created_at_formatted(self, obj):
        """Return formatted created_at datetime"""
        return obj.created_at.strftime('%Y-%m-%d %H:%M:%S') if obj.created_at else ''
    
    def get_updated_at_formatted(self, obj):
        """Return formatted updated_at datetime"""
        return obj.updated_at.strftime('%Y-%m-%d %H:%M:%S') if obj.updated_at else ''


class WebsiteListSerializer(serializers.ModelSerializer):
    """Serializer for listing available websites"""
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Website
        fields = ['id', 'name', 'url', 'is_active', 'product_count']
    
    def get_product_count(self, obj):
        """Return count of products for this website"""
        return Product.objects.filter(website=obj.name).count()
