from django.test import TestCase
from market.models import *
from market.serializer import *
from account_admin.models import User
from faker import Faker
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

fake = Faker()

class TestSerializers(TestCase):
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

    def test_category_serializer(self):
        serializer = CategorySerializer(instance=self.category)
        data = serializer.data
        self.assertEqual(data['nombre'], self.category.nombre)

    def test_product_serializer_to_representation(self):
        serializer = ProductSerializer(instance=self.product)
        data = serializer.data
        self.assertEqual(data['categoria']['id'], self.category.id)
        self.assertEqual(data['categoria']['nombre'], self.category.nombre)

    def test_order_serializer_to_representation_and_create(self):
        # Test to_representation
        serializer = OrderSerializer(instance=self.order, context={'request': None})
        data = serializer.data
        self.assertEqual(data['usuario_detalle']['username'], self.user.username)
        # Test create
        order_data = {
            'usuario': self.user.username,
            'detalles': [{'producto': self.product.id, 'cantidad': 1}]
        }
        serializer = OrderSerializer(data=order_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()
        self.assertEqual(order.usuario, self.user)

    def test_order_serializer_get_detalles(self):
        serializer = OrderSerializer(instance=self.order)
        detalles = serializer.get_detalles(self.order)
        self.assertIsInstance(detalles, list)

    def test_orderdetail_serializer(self):
        serializer = OrderDetailSerializer(instance=self.order_detail)
        data = serializer.data
        self.assertEqual(data['producto_detalle']['id'], self.product.id)

    def test_pay_serializer_get_pedido_detalle_and_create(self):
        serializer = PaySerializer(instance=self.pay)
        detalle = serializer.get_pedido_detalle(self.pay)
        self.assertEqual(detalle['id'], self.order.id)
        # Test create
        pay_data = {'pedido': self.order.id, 'metodo': 'tarjeta', 'estado': 'completado'}
        serializer = PaySerializer(data=pay_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        pay = serializer.save()
        self.assertEqual(pay.monto_pagado, self.order.total)

    def test_shipment_serializer_get_pedido_detalle_and_validate(self):
        serializer = ShipmentSerializer(instance=self.shipment)
        detalle = serializer.get_pedido_detalle(self.shipment)
        self.assertEqual(detalle['id'], self.order.id)

        # Test validate (estado inválido)
        self.order.estado = 'pagado'  # Estado inválido para Shipment
        self.order.save()
        data = {
            'pedido': self.order,
            'direccion_envio': fake.address(),
            'empresa_envio': fake.company(),
            'numero_guia': fake.uuid4(),
            'fecha_entrega_estimada': fake.date_this_year().isoformat(),
            'estado': 'pendiente'
        }
        with self.assertRaises(ValidationError):
            serializer.validate(data)

        # Test create (estado válido) con un nuevo pedido y sin Shipment asociado
        new_order = Order.objects.create(
            usuario=self.user,
            estado='pendiente'
        )
        serializer = ShipmentSerializer(data={
            'pedido': new_order.id,
            'direccion_envio': fake.address(),
            'empresa_envio': fake.company(),
            'numero_guia': fake.uuid4(),
            'fecha_entrega_estimada': fake.date_this_year().isoformat(),
            'estado': 'pendiente'
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        shipment = serializer.save()
        self.assertEqual(shipment.pedido.estado, 'procesando')

    def test_cartitem_serializer(self):
        serializer = CartItemSerializer(instance=self.cart_item)
        data = serializer.data
        self.assertEqual(data['producto_nombre'], self.product.nombre)
        self.assertEqual(float(data['subtotal']), float(self.product.precio * self.cart_item.cantidad))

    def test_cart_serializer_to_representation(self):
        serializer = CartSerializer(instance=self.cart)
        data = serializer.data
        self.assertEqual(float(data['total']), float(self.cart.total()))
        self.assertEqual(data['cantidad_items'], self.cart.cantidad_items())

    def test_order_serializer_get_detalles_no_attrs(self):
        class DummyObj:
            pass
        # Cubre líneas 70-73 (ni detalles ni orderdetail_set)
        serializer = OrderSerializer()
        dummy = DummyObj()
        detalles = serializer.get_detalles(dummy)
        self.assertEqual(detalles, [])

    def test_order_serializer_get_detalles_exception(self):
        # Cubre líneas 78-80 y 137-139 (excepción en el try)
        class BadObj:
            detalles = property(lambda self: 1/0)  # Provoca excepción
        serializer = OrderSerializer()
        detalles = serializer.get_detalles(BadObj())
        self.assertEqual(detalles, [])

    def test_order_serializer_to_representation_edit(self):
        # Cubre líneas 91-111 (rama de edición)
        factory = APIRequestFactory()
        request = factory.put('/fake-url/')
        serializer = OrderSerializer(instance=self.order, context={'request': Request(request)})
        data = serializer.data
        self.assertIn('usuario_detalle', data)
        self.assertIn('detalles', data)

    def test_order_serializer_create_without_detalles(self):
        # Cubre línea 126 (creación sin detalles)
        order_data = {
            'usuario': self.user.username
        }
        serializer = OrderSerializer(data=order_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()
        self.assertEqual(order.usuario, self.user)

    def test_order_serializer_get_detalles_orderdetail_set(self):
        class DummyObj:
            def __init__(self, detalles):
                self.orderdetail_set = detalles
        detalles_qs = OrderDetail.objects.none()  # Un queryset vacío, simula el all()
        dummy = DummyObj(detalles_qs)
        serializer = OrderSerializer()
        detalles = serializer.get_detalles(dummy)
        self.assertEqual(detalles, [])

    def test_order_serializer_create_with_missing_producto(self):
        order_data = {
            'usuario': self.user.username,
            'detalles': [
                {'cantidad': 2},  # Falta 'producto', debería activar el continue
                {'producto': self.product.id, 'cantidad': 1}
            ]
        }
        serializer = OrderSerializer(data=order_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()
        # Solo debe haberse creado un detalle (el que sí tiene producto)
        self.assertEqual(order.detalles.count(), 1)

    def test_order_serializer_create_with_nonexistent_producto(self):
        order_data = {
            'usuario': self.user.username,
            'detalles': [
                {'producto': 999999, 'cantidad': 1},  # ID que no existe
                {'producto': self.product.id, 'cantidad': 2}
            ]
        }
        serializer = OrderSerializer(data=order_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()
        # Solo debe haberse creado el detalle con producto existente
        self.assertEqual(order.detalles.count(), 1)