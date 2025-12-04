from django.urls import reverse, resolve
from rest_framework.test import APITestCase
from market import views
from faker import Faker

fake = Faker()

class TestMarketUrls(APITestCase):
    def test_categories_list_url(self):
        url = reverse('category-list')
        resolver = resolve(url)
        self.assertEqual(resolver.func.cls, views.CategoryViewSet)

    def test_categories_detail_url(self):
        pk = fake.random_int(min=1, max=999)
        url = reverse('category-detail', kwargs={'pk': pk})
        resolver = resolve(url)
        self.assertEqual(resolver.func.cls, views.CategoryViewSet)

    def test_products_list_url(self):
        url = reverse('product-list')
        resolver = resolve(url)
        self.assertEqual(resolver.func.cls, views.ProductViewSet)

    def test_products_detail_url(self):
        pk = fake.random_int(min=1, max=999)
        url = reverse('product-detail', kwargs={'pk': pk})
        resolver = resolve(url)
        self.assertEqual(resolver.func.cls, views.ProductViewSet)

    def test_orders_list_url(self):
        url = reverse('order-list')
        resolver = resolve(url)
        self.assertEqual(resolver.func.cls, views.OrderViewSet)

    def test_orders_detail_url(self):
        pk = fake.random_int(min=1, max=999)
        url = reverse('order-detail', kwargs={'pk': pk})
        resolver = resolve(url)
        self.assertEqual(resolver.func.cls, views.OrderViewSet)

    def test_pay_list_url(self):
        url = reverse('pay-list')
        resolver = resolve(url)
        self.assertEqual(resolver.func.cls, views.PayViewSet)

    def test_pay_detail_url(self):
        pk = fake.random_int(min=1, max=999)
        url = reverse('pay-detail', kwargs={'pk': pk})
        resolver = resolve(url)
        self.assertEqual(resolver.func.cls, views.PayViewSet)

    def test_shipment_list_url(self):
        url = reverse('shipment-list')
        resolver = resolve(url)
        self.assertEqual(resolver.func.cls, views.ShipmentViewSet)

    def test_shipment_detail_url(self):
        pk = fake.random_int(min=1, max=999)
        url = reverse('shipment-detail', kwargs={'pk': pk})
        resolver = resolve(url)
        self.assertEqual(resolver.func.cls, views.ShipmentViewSet)

    def test_cart_list_url(self):
        url = reverse('cart-list')
        resolver = resolve(url)
        self.assertEqual(resolver.func.cls, views.CartViewSet)

    def test_cart_detail_url(self):
        pk = fake.random_int(min=1, max=999)
        url = reverse('cart-detail', kwargs={'pk': pk})
        resolver = resolve(url)
        self.assertEqual(resolver.func.cls, views.CartViewSet)