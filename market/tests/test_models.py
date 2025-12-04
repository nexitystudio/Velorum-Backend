from django.test import TestCase
from market.models import Category, Product, Order, OrderDetail, Pay, Shipment, Cart, CartItem
from account_admin.models import User
from faker import Faker

fake = Faker()

class TestModels(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username=fake.user_name(),
            email=fake.email(),
            password='testpass123'
        )
        self.category = Category.objects.create(
            nombre=fake.word(),
            descripcion=fake.text()
        )
        self.product = Product.objects.create(
            nombre=fake.word(),
            descripcion=fake.text(),
            precio=fake.pydecimal(left_digits=4, right_digits=2, positive=True),
            stock=fake.random_int(min=1, max=100),
            categoria=self.category
        )
        self.order = Order.objects.create(
            usuario=self.user,
            estado='pendiente'
        )
        self.order_detail = OrderDetail.objects.create(
            pedido=self.order,
            producto=self.product,
            cantidad=2,
            subtotal=self.product.precio * 2
        )
        self.pay = Pay.objects.create(
            pedido=self.order,
            metodo='tarjeta',
            monto_pagado=self.product.precio * 2,
            estado='completado'
        )
        self.shipment = Shipment.objects.create(
            pedido=self.order,
            direccion_envio=fake.address(),
            empresa_envio=fake.company(),
            numero_guia=fake.uuid4(),
            fecha_entrega_estimada=fake.date_this_year().isoformat(),
            estado='pendiente'
        )
        self.cart = Cart.objects.create(usuario=self.user)
        self.cart_item = CartItem.objects.create(
            carrito=self.cart,
            producto=self.product,
            cantidad=3
        )

    def test_category_str(self):
        self.assertEqual(str(self.category), self.category.nombre)

    def test_product_str(self):
        self.assertEqual(str(self.product), self.product.nombre)

    def test_order_str(self):
        self.assertIn(str(self.order.id), str(self.order))
        self.assertIn(self.user.username, str(self.order))

    def test_order_detail_str(self):
        self.assertIn(self.product.nombre, str(self.order_detail))
        self.assertIn(str(self.order.id), str(self.order_detail))

    def test_pay_str(self):
        self.assertIn(str(self.pay.monto_pagado), str(self.pay))
        self.assertIn(self.pay.metodo, str(self.pay))

    def test_shipment_str(self):
        self.assertIn(str(self.order.id), str(self.shipment))
        self.assertIn(self.shipment.empresa_envio, str(self.shipment))

    def test_cart_str(self):
        self.assertIn(self.user.username, str(self.cart))

    def test_cart_item_str(self):
        self.assertIn(self.product.nombre, str(self.cart_item))

    def test_cart_total_and_cantidad_items(self):
        self.assertEqual(self.cart.total(), self.product.precio * self.cart_item.cantidad)
        self.assertEqual(self.cart.cantidad_items(), self.cart_item.cantidad)

    def test_cart_limpiar(self):
        self.cart.limpiar()
        self.assertEqual(self.cart.items.count(), 0)

    def test_order_total_update(self):
        self.order.total_update()
        self.order.refresh_from_db()
        self.assertEqual(self.order.total, self.order_detail.subtotal)

    def test_order_cancel_restock(self):
        # Simula cancelar el pedido y verifica que el stock se restituye
        stock_anterior = self.product.stock
        self.order.estado = 'cancelado'
        self.order.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, stock_anterior + self.order_detail.cantidad)

    def test_orderdetail_save_subtotal(self):
        self.order_detail.cantidad = 5
        self.order_detail.save()
        self.assertEqual(self.order_detail.subtotal, self.product.precio * 5)

    def test_cartitem_subtotal(self):
        self.assertEqual(self.cart_item.subtotal(), self.product.precio * self.cart_item.cantidad)