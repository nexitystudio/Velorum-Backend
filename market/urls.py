from django.urls import path, include 
from rest_framework import routers
from market import views

router = routers.DefaultRouter()
router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'products', views.ProductViewSet, basename='product')
router.register(r'orders', views.OrderViewSet, basename='order')
router.register(r'pay', views.PayViewSet, basename='pay')
router.register(r'shipment', views.ShipmentViewSet, basename='shipment')
router.register(r'cart', views.CartViewSet, basename='cart')
router.register(r'cart-items', views.CartItemViewSet, basename='cartitem')  # ⭐ NUEVA LÍNEA
router.register(r'favorites', views.FavoriteViewSet, basename='favorites')
router.register(r'codigos-descuento', views.CodigoDescuentoViewSet, basename='codigo-descuento')

urlpatterns = [
    path('market/model/', include(router.urls)),
    
    # Endpoints de sincronización de productos
    path('market/sync-external/', views.manual_sync_products, name='manual-sync-products'),
    path('market/products/<int:pk>/update-price/', views.update_product_price, name='update-product-price'),
    path('market/products/<int:pk>/reset-stock/', views.reset_stock_vendido, name='reset-stock-vendido'),
    path('market/products/bulk-markup/', views.bulk_update_markup, name='bulk-update-markup'),
    
    # Endpoints de Mercado Pago
    path('market/mp/create-preference/', views.create_mp_preference, name='mp-create-preference'),
    path('market/mp/webhook/', views.mercadopago_webhook, name='mp-webhook'),
    
    # Endpoint de códigos de descuento
    path('market/validar-codigo-descuento/', views.validar_codigo_descuento, name='validar-codigo-descuento'),
    
    # Endpoint de validación de checkout
    path('market/validate-checkout/', views.validate_checkout_access, name='validate-checkout'),
]