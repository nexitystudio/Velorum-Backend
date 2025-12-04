from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from market.models import *
from account_admin.models import User
from faker import Faker
from unittest.mock import put

fake = Faker()

class TestViews(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username=fake.unique.user_name(),
            name=fake.unique.name(),
            email=fake.unique.email(),
            password='testpass123',
            role='admin'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.category = Category.objects.create(
            nombre=fake.word(),
            descripcion=fake.text()
        )
        self.product = Product.objects.create(
            nombre=fake.word(),
            descripcion=fake.text(),
            precio=fake.pydecimal(left_digits=4, right_digits=2, positive=True),
            stock=10,
            categoria=self.category
        )
        self.cart = Cart.objects.create(usuario=self.user)
        self.order = Order.objects.create(usuario=self.user, estado='pendiente')
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
            estado='pendiente'
        )
        self.shipment = Shipment.objects.create(
            pedido=self.order,
            direccion_envio=fake.address(),
            empresa_envio=fake.company(),
            numero_guia=fake.uuid4(),
            fecha_entrega_estimada=fake.date_this_year().isoformat(),
            estado='pendiente'
        )

    def test_category_list(self):
        url = reverse('category-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_category_filter(self):
        url = reverse('category-list') + f'?nombre={self.category.nombre}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)

    def test_product_list(self):
        url = reverse('product-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_product_filter(self):
        url = reverse('product-list') + f'?nombre={self.product.nombre}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_product_add_to_cart(self):
        url = reverse('product-add-to-cart', kwargs={'pk': self.product.id})
        response = self.client.post(url, {'cantidad': 1})
        self.assertEqual(response.status_code, 200)
        self.assertIn('mensaje', response.data)

    def test_product_add_to_cart_invalid_quantity(self):
        url = reverse('product-add-to-cart', kwargs={'pk': self.product.id})
        response = self.client.post(url, {'cantidad': 0})
        self.assertEqual(response.status_code, 400)

    def test_product_add_to_cart_insufficient_stock(self):
        url = reverse('product-add-to-cart', kwargs={'pk': self.product.id})
        response = self.client.post(url, {'cantidad': 1000})
        self.assertEqual(response.status_code, 400)

    def test_order_list(self):
        url = reverse('order-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_order_create(self):
        url = reverse('order-list')
        response = self.client.post(url, {'usuario': self.user.username})
        self.assertEqual(response.status_code, 201)

    def test_order_cancel(self):
        url = reverse('order-cancel', kwargs={'pk': self.order.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.estado, 'cancelado')

    def test_cart_list(self):
        url = reverse('cart-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_cart_clear(self):
        url = reverse('cart-clear')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)

    def test_cart_checkout_empty(self):
        # Vacía el carrito antes de hacer checkout
        self.cart.limpiar()
        url = reverse('cart-checkout')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 400)

    def test_pay_list(self):
        url = reverse('pay-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_shipment_list(self):
        url = reverse('shipment-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_shipment_tracking(self):
        url = reverse('shipment-tracking', kwargs={'pk': self.shipment.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_product_filter_by_categoria(self):
        url = reverse('product-list') + f'?categoria={self.category.id}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Todos los productos devueltos deben ser de esa categoría
        for prod in response.data:
            self.assertEqual(prod['categoria']['id'], self.category.id)
    
    def test_product_filter_by_precio_min(self):
        # Crea un producto más barato
        cheap_product = Product.objects.create(
            nombre=fake.word(),
            descripcion=fake.text(),
            precio=1,
            stock=5,
            categoria=self.category
        )
        url = reverse('product-list') + f'?precio_min={self.product.precio}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Todos los productos devueltos deben tener precio >= self.product.precio
        for prod in response.data:
            self.assertGreaterEqual(float(prod['precio']), float(self.product.precio))
    
    def test_product_filter_by_precio_max(self):
        # Crea un producto más caro
        expensive_product = Product.objects.create(
            nombre=fake.word(),
            descripcion=fake.text(),
            precio=9999,
            stock=5,
            categoria=self.category
        )
        url = reverse('product-list') + f'?precio_max={self.product.precio}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Todos los productos devueltos deben tener precio <= self.product.precio
        for prod in response.data:
            self.assertLessEqual(float(prod['precio']), float(self.product.precio))
    
    def test_product_filter_by_categoria_and_precio(self):
        # Crea un producto en otra categoría
        other_category = Category.objects.create(
            nombre=fake.word(),
            descripcion=fake.text()
        )
        Product.objects.create(
            nombre=fake.word(),
            descripcion=fake.text(),
            precio=5,
            stock=5,
            categoria=other_category
        )
        url = reverse('product-list') + f'?categoria={self.category.id}&precio_min=1&precio_max={self.product.precio}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        for prod in response.data:
            self.assertEqual(prod['categoria']['id'], self.category.id)
            self.assertGreaterEqual(float(prod['precio']), 1)
            self.assertLessEqual(float(prod['precio']), float(self.product.precio))

    def test_product_add_to_cart_exceeding_stock_with_existing_item(self):
        # Primero agrega una cantidad válida al carrito
        url = reverse('product-add-to-cart', kwargs={'pk': self.product.id})
        response = self.client.post(url, {'cantidad': 5})
        self.assertEqual(response.status_code, 200)
    
        # Ahora intenta agregar otra cantidad que, sumada, excede el stock
        response = self.client.post(url, {'cantidad': 6})  # 5 + 6 = 11 > stock (10)
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)

    def test_product_add_to_cart_updates_existing_item(self):
        # Agrega primero una cantidad al carrito
        url = reverse('product-add-to-cart', kwargs={'pk': self.product.id})
        response = self.client.post(url, {'cantidad': 3})
        self.assertEqual(response.status_code, 200)
    
        # Agrega otra cantidad que sumada NO excede el stock
        response = self.client.post(url, {'cantidad': 2})  # 3 + 2 = 5 <= stock (10)
        self.assertEqual(response.status_code, 200)
        self.assertIn('mensaje', response.data)
        self.assertEqual(response.data['mensaje'], 'Producto actualizado en el carrito')
    
        # Verifica que la cantidad en el carrito se haya actualizado
        carrito = Cart.objects.get(usuario=self.user)
        item = CartItem.objects.get(carrito=carrito, producto=self.product)
        self.assertEqual(item.cantidad, 5)

    def test_order_list_only_own_orders_for_client(self):
        # Crea un usuario cliente y una orden de otro usuario
        client_user = User.objects.create_user(
            username=fake.unique.user_name(),
            name=fake.unique.name(),
            email=fake.email(),
            password='testpass123',
            role='client'
        )
        other_user = User.objects.create_user(
            username=fake.unique.user_name(),
            name=fake.name(),
            email=fake.email(),
            password='testpass123',
            role='client'
        )
        # Orden de otro usuario
        Order.objects.create(usuario=other_user, estado='pendiente')
    
        # Autentica como el cliente
        self.client.force_authenticate(user=client_user)
        # Crea una orden propia
        own_order = Order.objects.create(usuario=client_user, estado='pendiente')
    
        url = reverse('order-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Solo debe ver su propia orden
        self.assertTrue(all(order['usuario_detalle']['id'] == client_user.id for order in response.data))
        self.assertIn(own_order.id, [order['id'] for order in response.data])

    def test_order_update_forbidden_states(self):
        # Crea una orden en estado 'entregado'
        order = Order.objects.create(
            usuario=self.user,
            estado='entregado'
        )
        url = reverse('order-detail', kwargs={'pk': order.id})
        data = {'estado': 'pendiente', 'usuario': self.user.username}
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("No se puede modificar un pedido en estado", str(response.data))
    
        # Crea una orden en estado 'cancelado'
        order2 = Order.objects.create(
            usuario=self.user,
            estado='cancelado'
        )
        url2 = reverse('order-detail', kwargs={'pk': order2.id})
        response2 = self.client.put(url2, data, format='json')
        self.assertEqual(response2.status_code, 400)
        self.assertIn("No se puede modificar un pedido en estado", str(response2.data))
    
    def test_order_update_allowed_state(self):
        # Crea una orden en estado 'pendiente'
        order = Order.objects.create(
            usuario=self.user,
            estado='pendiente'
        )
        url = reverse('order-detail', kwargs={'pk': order.id})
        data = {'estado': 'procesando', 'usuario': self.user.username}
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.estado, 'procesando')

    def test_order_update_with_detalles(self):
        # Crea un producto nuevo para agregar como detalle
        new_product = Product.objects.create(
            nombre=fake.word(),
            descripcion=fake.text(),
            precio=50,
            stock=10,
            categoria=self.category
        )
        order = Order.objects.create(usuario=self.user, estado='pendiente')
        url = reverse('order-detail', kwargs={'pk': order.id})
    
        detalles = [
            {
                "producto": new_product.id,
                "cantidad": 2
            }
        ]
        data = {
            "estado": "pendiente",
            "usuario": self.user.username,
            "detalles": detalles
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, 200)
        # Verifica que el detalle fue creado
        self.assertTrue(OrderDetail.objects.filter(pedido=order, producto=new_product, cantidad=2).exists())

    def test_order_update_with_detalle_missing_producto(self):
        order = Order.objects.create(usuario=self.user, estado='pendiente')
        url = reverse('order-detail', kwargs={'pk': order.id})
    
        detalles = [
            {
                # Falta el campo 'producto'
                "cantidad": 2
            },
            {
                "producto": None,
                "cantidad": 3
            }
        ]
        data = {
            "estado": "pendiente",
            "usuario": self.user.username,
            "detalles": detalles
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, 200)
        # No debe haberse creado ningún detalle para este pedido
        self.assertFalse(OrderDetail.objects.filter(pedido=order).exists())

    def test_order_update_detail_quantity_and_stock(self):
        # Crea un producto con stock suficiente
        product = Product.objects.create(
            nombre=fake.word(),
            descripcion=fake.text(),
            precio=10,
            stock=10,
            categoria=self.category
        )
        order = Order.objects.create(usuario=self.user, estado='pendiente')
        detail = OrderDetail.objects.create(
            pedido=order,
            producto=product,
            cantidad=2,
            subtotal=20
        )
        url = reverse('order-detail', kwargs={'pk': order.id})
        detalles = [
            {
                "id": detail.id,
                "producto": product.id,
                "cantidad": 5  # Cambia la cantidad
            }
        ]
        data = {
            "estado": "pendiente",
            "usuario": self.user.username,
            "detalles": detalles
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, 200)
        detail.refresh_from_db()
        product.refresh_from_db()
        self.assertEqual(detail.cantidad, 5)
        # Stock original 10 + 2 (devuelto) - 5 (nuevo) = 7
        self.assertEqual(product.stock, 7)
    
    def test_order_update_detail_quantity_stock_insufficient(self):
        # Crea un producto con poco stock
        product = Product.objects.create(
            nombre=fake.word(),
            descripcion=fake.text(),
            precio=10,
            stock=2,
            categoria=self.category
        )
        order = Order.objects.create(usuario=self.user, estado='pendiente')
        detail = OrderDetail.objects.create(
            pedido=order,
            producto=product,
            cantidad=2,
            subtotal=20
        )
        url = reverse('order-detail', kwargs={'pk': order.id})
        detalles = [
            {
                "id": detail.id,
                "producto": product.id,
                "cantidad": 10  # Excede el stock disponible
            }
        ]
        data = {
            "estado": "pendiente",
            "usuario": self.user.username,
            "detalles": detalles
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Stock insuficiente", str(response.data))
    
    def test_order_update_detail_not_belongs(self):
        # Intenta actualizar un detalle que no pertenece a la orden
        product = Product.objects.create(
            nombre=fake.word(),
            descripcion=fake.text(),
            precio=10,
            stock=10,
            categoria=self.category
        )
        order = Order.objects.create(usuario=self.user, estado='pendiente')
        other_order = Order.objects.create(usuario=self.user, estado='pendiente')
        detail = OrderDetail.objects.create(
            pedido=other_order,
            producto=product,
            cantidad=2,
            subtotal=20
        )
        url = reverse('order-detail', kwargs={'pk': order.id})
        detalles = [
            {
                "id": detail.id,
                "producto": product.id,
                "cantidad": 3
            }
        ]
        data = {
            "estado": "pendiente",
            "usuario": self.user.username,
            "detalles": detalles
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("no pertenece a esta orden", str(response.data))
    
    def test_order_update_create_detail_stock_insufficient(self):
        # Crea un producto con poco stock
        product = Product.objects.create(
            nombre=fake.word(),
            descripcion=fake.text(),
            precio=10,
            stock=1,
            categoria=self.category
        )
        order = Order.objects.create(usuario=self.user, estado='pendiente')
        url = reverse('order-detail', kwargs={'pk': order.id})
        detalles = [
            {
                "producto": product.id,
                "cantidad": 5  # Excede el stock disponible
            }
        ]
        data = {
            "estado": "pendiente",
            "usuario": self.user.username,
            "detalles": detalles
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Stock insuficiente", str(response.data))

    def test_order_update_create_detail_product_does_not_exist(self):
        order = Order.objects.create(usuario=self.user, estado='pendiente')
        url = reverse('order-detail', kwargs={'pk': order.id})
        detalles = [
            {
                "producto": 999999,  # ID de producto inexistente
                "cantidad": 2
            }
        ]
        data = {
            "estado": "pendiente",
            "usuario": self.user.username,
            "detalles": detalles
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, 200)
        # No debe haberse creado ningún detalle para este pedido
        self.assertFalse(OrderDetail.objects.filter(pedido=order).exists())

    def test_remove_detail_success(self):
        # Crea una orden y un detalle asociado
        order = Order.objects.create(usuario=self.user, estado='pendiente')
        product = Product.objects.create(
            nombre=fake.word(),
            descripcion=fake.text(),
            precio=10,
            stock=5,
            categoria=self.category
        )
        detail = OrderDetail.objects.create(
            pedido=order,
            producto=product,
            cantidad=2,
            subtotal=20
        )
        # Reduce el stock para simular la compra
        product.stock -= 2
        product.save()
    
        url = reverse('order-remove-detail', kwargs={'pk': order.id, 'detail_id': detail.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Detalle eliminado', str(response.data))
        # El detalle ya no debe existir
        self.assertFalse(OrderDetail.objects.filter(id=detail.id).exists())
        # El stock debe haberse devuelto
        product.refresh_from_db()
        self.assertEqual(product.stock, 5)
    
    def test_remove_detail_not_found(self):
        order = Order.objects.create(usuario=self.user, estado='pendiente')
        # Usa un ID de detalle inexistente
        url = reverse('order-remove-detail', kwargs={'pk': order.id, 'detail_id': 999999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
        self.assertIn('no existe o no pertenece a esta orden', str(response.data))

    def test_remove_detail_entregado_o_cancelado(self):
        # 1) No se puede modificar un pedido en estado entregado/cancelado
        for estado in ['entregado', 'cancelado']:
            order = Order.objects.create(usuario=self.user, estado=estado)
            product = Product.objects.create(
                nombre=fake.word(), descripcion=fake.text(), precio=10, stock=5, categoria=self.category
            )
            detail = OrderDetail.objects.create(pedido=order, producto=product, cantidad=1, subtotal=10)
            url = reverse('order-remove-detail', kwargs={'pk': order.id, 'detail_id': detail.id})
            response = self.client.post(url)
            self.assertEqual(response.status_code, 400)
            self.assertIn('No se puede modificar un pedido en estado', str(response.data))
    
    def test_order_cancel_already_cancelled(self):
        # 2) La orden ya está cancelada
        order = Order.objects.create(usuario=self.user, estado='cancelado')
        url = reverse('order-cancel', kwargs={'pk': order.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 400)
        self.assertIn('La orden ya está cancelada', str(response.data))
    
    def test_order_cancel_invalid_state(self):
        # 3) No se puede cancelar una orden en estado distinto a pendiente/procesando
        for estado in ['entregado', 'pagado']:
            order = Order.objects.create(usuario=self.user, estado=estado)
            url = reverse('order-cancel', kwargs={'pk': order.id})
            response = self.client.post(url)
            self.assertEqual(response.status_code, 400)
            self.assertIn('No se puede cancelar una orden en estado', str(response.data))
    
    def test_order_update_total(self):
        # 4) Endpoint para actualizar el total del pedido
        order = Order.objects.create(usuario=self.user, estado='pendiente', total=0)
        # Crea un detalle para que el total cambie
        product = Product.objects.create(
            nombre=fake.word(), descripcion=fake.text(), precio=20, stock=5, categoria=self.category
        )
        OrderDetail.objects.create(pedido=order, producto=product, cantidad=2, subtotal=40)
        url = reverse('order-update-total', kwargs={'pk': order.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('total actualizado', str(response.data))
        self.assertEqual(float(response.data['total']), 40.0)
    
    def test_cart_retrieve_only_current_user(self):
        # Crea un carrito de otro usuario
        other_user = User.objects.create_user(
            username=fake.unique.user_name(),
            name=fake.unique.name(),
            email=fake.unique.email(),
            password='testpass123',
            role='client'
        )
        other_cart = Cart.objects.create(usuario=other_user)

        # El usuario autenticado intenta acceder a su propio carrito (debe funcionar)
        url = reverse('cart-detail', kwargs={'pk': self.cart.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['usuario'], self.user.id)

        # El usuario autenticado intenta acceder al carrito de otro usuario (debe dar 404)
        url = reverse('cart-detail', kwargs={'pk': other_cart.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_cart_checkout_insufficient_stock_first_check(self):
        # Agrega un producto al carrito con cantidad mayor al stock
        self.product.stock = 2
        self.product.save()
        CartItem.objects.create(carrito=self.cart, producto=self.product, cantidad=5)
        url = reverse('cart-checkout')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 400)
        self.assertIn('Stock insuficiente', str(response.data))
    
    def test_cart_checkout_insufficient_stock_second_check(self):
        # Crea dos productos con stock suficiente
        product1 = Product.objects.create(
            nombre=fake.word(),
            descripcion=fake.text(),
            precio=10,
            stock=5,
            categoria=self.category
        )
        product2 = Product.objects.create(
            nombre=fake.word(),
            descripcion=fake.text(),
            precio=10,
            stock=5,
            categoria=self.category
        )
        CartItem.objects.create(carrito=self.cart, producto=product1, cantidad=5)
        CartItem.objects.create(carrito=self.cart, producto=product2, cantidad=5)

        # Mock del método refresh_from_db para simular la concurrencia
        original_refresh = Product.refresh_from_db
        refresh_call_count = 0
        
        def mock_refresh(self):
            nonlocal refresh_call_count
            refresh_call_count += 1
            original_refresh(self)
            # En la segunda llamada (product2), simular que otro proceso redujo el stock
            if refresh_call_count == 2 and self.id == product2.id:
                Product.objects.filter(id=product2.id).update(stock=2)
                # Refrescar nuevamente para obtener el valor actualizado
                original_refresh(self)
        
        # Aplicar el mock
        Product.refresh_from_db = mock_refresh
        
        try:
            url = reverse('cart-checkout')
            response = self.client.post(url)
            self.assertEqual(response.status_code, 400)
            self.assertIn('Stock insuficiente', str(response.data))
        finally:
            # Restaurar el método original
            Product.refresh_from_db = original_refresh
    
    def test_cart_checkout_success(self):
        # Agrega un producto al carrito con cantidad igual al stock
        self.product.stock = 5
        self.product.save()
        CartItem.objects.create(carrito=self.cart, producto=self.product, cantidad=5)
        url = reverse('cart-checkout')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 201)
        self.assertIn('Pedido creado correctamente', str(response.data))
        # El carrito debe estar vacío
        self.assertEqual(self.cart.items.count(), 0)
        # El stock debe haberse descontado
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)

    def test_pay_filter_by_estado(self):
        """Test para filtrar pagos por estado"""

        Pay.objects.all().delete()  # Limpiar pagos existentes

        # Crear dos pagos con diferentes estados
        order1 = Order.objects.create(usuario=self.user, estado='pendiente', total=100)
        order2 = Order.objects.create(usuario=self.user, estado='pendiente', total=200)
        
        pay1 = Pay.objects.create(
            pedido=order1,
            monto_pagado=100,
            estado='pendiente'
        )
        pay2 = Pay.objects.create(
            pedido=order2,
            monto_pagado=200,
            estado='completado'
        )
        
        # Test filtrar por estado 'pendiente'
        url = reverse('pay-list') + '?estado=pendiente'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['estado'], 'pendiente')
        
        # Test filtrar por estado 'completado'
        url = reverse('pay-list') + '?estado=completado'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['estado'], 'completado')
    
    def test_pay_list_filtered_by_user_for_clients(self):
        """Test para verificar que los clientes solo vean pagos de sus propias órdenes"""
        
        # Cambiar el usuario actual a un cliente (no admin)
        client_user = User.objects.create_user(
            username=fake.unique.user_name(),
            name=fake.unique.name(),
            email=fake.unique.email(),
            password='testpass123',
            role='client'
        )
        self.client.force_authenticate(user=client_user)
        
        # Crear otro usuario cliente
        other_user = User.objects.create_user(
            username=fake.unique.user_name(),
            name=fake.unique.name(),
            email=fake.unique.email(),
            password='testpass123',
            role='client'
        )
        
        # Crear órdenes para ambos usuarios
        user_order = Order.objects.create(usuario=client_user, estado='pendiente', total=100)
        other_user_order = Order.objects.create(usuario=other_user, estado='pendiente', total=200)
        
        # Crear pagos para ambas órdenes
        user_pay = Pay.objects.create(
            pedido=user_order,
            monto_pagado=100,
            estado='pendiente'
        )
        other_pay = Pay.objects.create(
            pedido=other_user_order,
            monto_pagado=200,
            estado='pendiente'
        )
        
        # El cliente actual debe ver solo su pago (no los del admin ni del otro usuario)
        url = reverse('pay-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], user_pay.id)
        
        # Verificar que no ve el pago del otro usuario ni del admin
        payment_ids = [pay['id'] for pay in response.data]
        self.assertNotIn(other_pay.id, payment_ids)
        self.assertNotIn(self.pay.id, payment_ids)  # Tampoco ve el del admin
    
    def test_pay_create_client_cannot_pay_other_user_order(self):
        """Test que verifica que un cliente no puede crear pagos para órdenes de otros usuarios"""
        # Crear un usuario cliente
        client_user = User.objects.create_user(
            username=fake.unique.user_name(),
            name=fake.unique.name(),
            email=fake.unique.email(),
            password='testpass123',
            role='client'
        )
        self.client.force_authenticate(user=client_user)
        
        # Crear una orden de otro usuario (admin)
        admin_order = Order.objects.create(usuario=self.user, estado='pendiente', total=100)
        
        # Intentar crear un pago para la orden del admin
        url = reverse('pay-list')
        data = {
            'pedido': admin_order.id,
            'metodo': 'tarjeta',
            'estado': 'pendiente'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 400)
        self.assertIn('No puedes crear pagos para pedidos que no te pertenecen', str(response.data))
    
    def test_pay_create_invalid_order_state(self):
        """Test que verifica que no se puede pagar una orden en estado inválido"""
        # Crear órdenes en estados no válidos para pago
        invalid_states = ['entregado', 'cancelado', 'enviado']
        
        for estado in invalid_states:
            order = Order.objects.create(usuario=self.user, estado=estado, total=100)
            url = reverse('pay-list')
            data = {
                'pedido': order.id,
                'metodo': 'tarjeta',
                'estado': 'pendiente'
            }
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 400)
            self.assertIn(f'No se puede pagar un pedido en estado \'{estado}\'', str(response.data))
    
    def test_pay_create_order_not_found(self):
        """Test que verifica el manejo cuando la orden no existe"""
        url = reverse('pay-list')
        data = {
            'pedido': 999999,  # ID inexistente
            'metodo': 'tarjeta',
            'estado': 'pendiente'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 400)
        # El error viene del serializer, no del perform_create
        self.assertIn('does not exist', str(response.data))
    
    def test_pay_create_success_with_default_estado(self):
        """Test para verificar creación exitosa con estado por defecto"""
        order = Order.objects.create(usuario=self.user, estado='pendiente', total=150)
        url = reverse('pay-list')
        data = {
            'pedido': order.id,
            'metodo': 'tarjeta'
            # No se especifica estado, debe usar 'pendiente' por defecto
            # No se especifica monto_pagado, se calcula automáticamente
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 201)
        
        # Verificar que se creó correctamente
        pay = Pay.objects.get(id=response.data['id'])
        self.assertEqual(pay.estado, 'pendiente')
        self.assertEqual(pay.monto_pagado, 150)  # Debe usar el total de la orden
        self.assertEqual(pay.pedido, order)
    
    def test_pay_create_success_with_custom_estado(self):
        """Test para verificar creación exitosa con estado personalizado"""
        order = Order.objects.create(usuario=self.user, estado='procesando', total=200)
        url = reverse('pay-list')
        data = {
            'pedido': order.id,
            'metodo': 'transferencia',
            'estado': 'completado'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 201)
        
        # Verificar que se creó correctamente
        pay = Pay.objects.get(id=response.data['id'])
        self.assertEqual(pay.estado, 'completado')
        self.assertEqual(pay.monto_pagado, 200)  # Debe usar el total de la orden
        self.assertEqual(pay.pedido, order)
    
    def test_pay_create_admin_can_pay_any_order(self):
        """Test que verifica que admin/operator pueden crear pagos para cualquier orden"""
        # Crear otro usuario
        other_user = User.objects.create_user(
            username=fake.unique.user_name(),
            name=fake.unique.name(),
            email=fake.unique.email(),
            password='testpass123',
            role='client'
        )
        
        # Crear orden del otro usuario
        other_order = Order.objects.create(usuario=other_user, estado='pendiente', total=300)
        
        # El admin puede crear pagos para cualquier orden
        url = reverse('pay-list')
        data = {
            'pedido': other_order.id,
            'metodo': 'tarjeta',
            'estado': 'pendiente'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 201)
        
        # Verificar que se creó correctamente
        pay = Pay.objects.get(id=response.data['id'])
        self.assertEqual(pay.pedido, other_order)
        self.assertEqual(pay.monto_pagado, 300)
    
    def test_pay_create_order_deleted_during_creation(self):
        """Test que verifica el manejo cuando la orden se elimina durante la creación del pago"""
        order = Order.objects.create(usuario=self.user, estado='pendiente', total=100)
        
        # Mock del queryset select_for_update
        with put('market.views.Order.objects.select_for_update') as mock_select:
            mock_manager = mock_select.return_value
            mock_manager.get.side_effect = Order.DoesNotExist("Pedido no encontrado")
            
            url = reverse('pay-list')
            data = {
                'pedido': order.id,
                'metodo': 'tarjeta',
                'estado': 'pendiente'
            }
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 400)
            self.assertIn('Pedido no encontrado', str(response.data))

    def test_pay_complete_payment_success(self):
        """Test para completar un pago exitosamente"""
        # Crear orden y pago pendiente
        order = Order.objects.create(usuario=self.user, estado='pendiente', total=100)
        payment = Pay.objects.create(
            pedido=order,
            metodo='tarjeta',
            monto_pagado=100,
            estado='pendiente'
        )
        
        url = reverse('pay-complete-payment', kwargs={'pk': payment.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'pago completado')
        self.assertEqual(response.data['pedido_actualizado'], True)
        self.assertEqual(response.data['nuevo_estado_pedido'], 'pagado')
        
        # Verificar que el pago se actualizó
        payment.refresh_from_db()
        self.assertEqual(payment.estado, 'completado')
        
        # Verificar que el pedido se actualizó
        order.refresh_from_db()
        self.assertEqual(order.estado, 'pagado')
    
    def test_pay_complete_payment_forbidden_for_client(self):
        """Test que verifica que los clientes no pueden completar pagos manualmente"""
        # Crear usuario cliente
        client_user = User.objects.create_user(
            username=fake.unique.user_name(),
            name=fake.unique.name(),
            email=fake.unique.email(),
            password='testpass123',
            role='client'
        )
        self.client.force_authenticate(user=client_user)
        
        # Crear orden y pago del cliente
        order = Order.objects.create(usuario=client_user, estado='pendiente', total=100)
        payment = Pay.objects.create(
            pedido=order,
            metodo='tarjeta',
            monto_pagado=100,
            estado='pendiente'
        )
        
        url = reverse('pay-complete-payment', kwargs={'pk': payment.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 403)
        self.assertIn('Solo administradores y operadores pueden completar pagos manualmente', str(response.data))
    
    def test_pay_complete_payment_invalid_state(self):
        """Test que verifica que no se puede completar un pago que no está pendiente"""
        # Crear orden y pago ya completado
        order = Order.objects.create(usuario=self.user, estado='pendiente', total=100)
        payment = Pay.objects.create(
            pedido=order,
            metodo='tarjeta',
            monto_pagado=100,
            estado='completado'  # Ya está completado
        )
        
        url = reverse('pay-complete-payment', kwargs={'pk': payment.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('No se puede completar un pago en estado completado', str(response.data))
    
    def test_pay_complete_payment_cancelled_state(self):
        """Test que verifica que no se puede completar un pago cancelado"""
        # Crear orden y pago cancelado
        order = Order.objects.create(usuario=self.user, estado='pendiente', total=100)
        payment = Pay.objects.create(
            pedido=order,
            metodo='tarjeta',
            monto_pagado=100,
            estado='cancelado'
        )
        
        url = reverse('pay-complete-payment', kwargs={'pk': payment.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('No se puede completar un pago en estado cancelado', str(response.data))
    
    def test_pay_complete_payment_operator_can_complete(self):
        """Test que verifica que los operadores también pueden completar pagos"""
        # Crear usuario operador
        operator_user = User.objects.create_user(
            username=fake.unique.user_name(),
            name=fake.unique.name(),
            email=fake.unique.email(),
            password='testpass123',
            role='operator'
        )
        self.client.force_authenticate(user=operator_user)
        
        # Crear orden y pago pendiente
        order = Order.objects.create(usuario=self.user, estado='pendiente', total=100)
        payment = Pay.objects.create(
            pedido=order,
            metodo='tarjeta',
            monto_pagado=100,
            estado='pendiente'
        )
        
        url = reverse('pay-complete-payment', kwargs={'pk': payment.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'pago completado')
        
        # Verificar cambios
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.estado, 'completado')
        self.assertEqual(order.estado, 'pagado')

    def test_pay_cancelar_success(self):
        """Test para cancelar un pago pendiente exitosamente"""
        # Crear orden y pago pendiente
        order = Order.objects.create(usuario=self.user, estado='pendiente', total=100)
        payment = Pay.objects.create(
            pedido=order,
            metodo='tarjeta',
            monto_pagado=100,
            estado='pendiente'
        )
        
        url = reverse('pay-cancelar', kwargs={'pk': payment.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['mensaje'], 'Pago cancelado correctamente')
        
        # Verificar que el pago se actualizó
        payment.refresh_from_db()
        self.assertEqual(payment.estado, 'cancelado')
    
    def test_pay_cancelar_already_completed(self):
        """Test que verifica que no se puede cancelar un pago completado"""
        # Crear orden y pago completado
        order = Order.objects.create(usuario=self.user, estado='pendiente', total=100)
        payment = Pay.objects.create(
            pedido=order,
            metodo='tarjeta',
            monto_pagado=100,
            estado='completado'
        )
        
        url = reverse('pay-cancelar', kwargs={'pk': payment.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('No se puede cancelar un pago en estado \'completado\'', str(response.data))
        
        # Verificar que el pago NO se cambió
        payment.refresh_from_db()
        self.assertEqual(payment.estado, 'completado')
    
    def test_pay_cancelar_already_cancelled(self):
        """Test que verifica que no se puede cancelar un pago ya cancelado"""
        # Crear orden y pago ya cancelado
        order = Order.objects.create(usuario=self.user, estado='pendiente', total=100)
        payment = Pay.objects.create(
            pedido=order,
            metodo='tarjeta',
            monto_pagado=100,
            estado='cancelado'
        )
        
        url = reverse('pay-cancelar', kwargs={'pk': payment.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('No se puede cancelar un pago en estado \'cancelado\'', str(response.data))
        
        # Verificar que el estado se mantiene
        payment.refresh_from_db()
        self.assertEqual(payment.estado, 'cancelado')
    
    def test_pay_cancelar_client_can_cancel_own_payment(self):
        """Test que verifica que los clientes pueden cancelar sus propios pagos"""
        # Crear usuario cliente
        client_user = User.objects.create_user(
            username=fake.unique.user_name(),
            name=fake.unique.name(),
            email=fake.unique.email(),
            password='testpass123',
            role='client'
        )
        self.client.force_authenticate(user=client_user)
        
        # Crear orden y pago del cliente
        order = Order.objects.create(usuario=client_user, estado='pendiente', total=100)
        payment = Pay.objects.create(
            pedido=order,
            metodo='tarjeta',
            monto_pagado=100,
            estado='pendiente'
        )
        
        url = reverse('pay-cancelar', kwargs={'pk': payment.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['mensaje'], 'Pago cancelado correctamente')
        
        # Verificar que el pago se canceló
        payment.refresh_from_db()
        self.assertEqual(payment.estado, 'cancelado')
    
    def test_pay_cancelar_operator_can_cancel(self):
        """Test que verifica que los operadores pueden cancelar pagos"""
        # Crear usuario operador
        operator_user = User.objects.create_user(
            username=fake.unique.user_name(),
            name=fake.unique.name(),
            email=fake.unique.email(),
            password='testpass123',
            role='operator'
        )
        self.client.force_authenticate(user=operator_user)
        
        # Crear orden y pago pendiente
        order = Order.objects.create(usuario=self.user, estado='pendiente', total=100)
        payment = Pay.objects.create(
            pedido=order,
            metodo='tarjeta',
            monto_pagado=100,
            estado='pendiente'
        )
        
        url = reverse('pay-cancelar', kwargs={'pk': payment.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['mensaje'], 'Pago cancelado correctamente')
        
        # Verificar que el pago se canceló
        payment.refresh_from_db()
        self.assertEqual(payment.estado, 'cancelado')
    
    def test_shipment_list_client_sees_only_own(self):
        """Test que verifica que los clientes solo ven envíos de sus propias órdenes"""
        # Crear usuario cliente
        client_user = User.objects.create_user(
            username=fake.unique.user_name(),
            name=fake.unique.name(),
            email=fake.unique.email(),
            password='testpass123',
            role='client'
        )
        self.client.force_authenticate(user=client_user)
        
        # Crear orden y envío del cliente
        client_order = Order.objects.create(usuario=client_user, estado='pendiente', total=100)
        client_shipment = Shipment.objects.create(
            pedido=client_order,
            direccion_envio=fake.address(),
            empresa_envio=fake.company(),
            numero_guia=fake.uuid4(),
            fecha_entrega_estimada=fake.date_this_year().isoformat(),
            estado='pendiente'
        )
        
        # El cliente debe ver solo su envío
        url = reverse('shipment-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], client_shipment.id)

    def test_shipment_update_status_success(self):
        """Test para actualizar el estado de un envío exitosamente"""
        # Crear orden y envío
        order = Order.objects.create(usuario=self.user, estado='pendiente', total=100)
        shipment = Shipment.objects.create(
            pedido=order,
            direccion_envio=fake.address(),
            empresa_envio=fake.company(),
            numero_guia=fake.uuid4(),
            fecha_entrega_estimada=fake.date_this_year().isoformat(),
            estado='pendiente'
        )
        
        url = reverse('shipment-update-status', kwargs={'pk': shipment.id})
        data = {'estado': 'preparando'}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'Estado de envío actualizado')
        
        # Verificar que el envío se actualizó
        shipment.refresh_from_db()
        self.assertEqual(shipment.estado, 'preparando')
    
    def test_shipment_update_status_forbidden_for_client(self):
        """Test que verifica que los clientes no pueden actualizar el estado de envíos"""
        # Crear usuario cliente
        client_user = User.objects.create_user(
            username=fake.unique.user_name(),
            name=fake.unique.name(),
            email=fake.unique.email(),
            password='testpass123',
            role='client'
        )
        self.client.force_authenticate(user=client_user)
        
        # Crear orden y envío
        order = Order.objects.create(usuario=client_user, estado='pendiente', total=100)
        shipment = Shipment.objects.create(
            pedido=order,
            direccion_envio=fake.address(),
            empresa_envio=fake.company(),
            numero_guia=fake.uuid4(),
            fecha_entrega_estimada=fake.date_this_year().isoformat(),
            estado='pendiente'
        )
        
        url = reverse('shipment-update-status', kwargs={'pk': shipment.id})
        data = {'estado': 'preparando'}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 403)
        self.assertIn('No autorizado', str(response.data))
    
    def test_shipment_update_status_invalid_state(self):
        """Test que verifica que no se puede actualizar a un estado inválido"""
        # Crear orden y envío
        order = Order.objects.create(usuario=self.user, estado='pendiente', total=100)
        shipment = Shipment.objects.create(
            pedido=order,
            direccion_envio=fake.address(),
            empresa_envio=fake.company(),
            numero_guia=fake.uuid4(),
            fecha_entrega_estimada=fake.date_this_year().isoformat(),
            estado='pendiente'
        )
        
        url = reverse('shipment-update-status', kwargs={'pk': shipment.id})
        data = {'estado': 'estado_inexistente'}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('Estado inválido', str(response.data))
    
    def test_shipment_update_status_en_camino_updates_order(self):
        """Test que verifica que al marcar como 'en camino' se actualiza el pedido a 'enviado'"""
        # Crear orden y envío
        order = Order.objects.create(usuario=self.user, estado='procesando', total=100)
        shipment = Shipment.objects.create(
            pedido=order,
            direccion_envio=fake.address(),
            empresa_envio=fake.company(),
            numero_guia=fake.uuid4(),
            fecha_entrega_estimada=fake.date_this_year().isoformat(),
            estado='preparando'
        )
        
        url = reverse('shipment-update-status', kwargs={'pk': shipment.id})
        data = {'estado': 'en camino'}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 200)
        
        # Verificar que el envío se actualizó
        shipment.refresh_from_db()
        self.assertEqual(shipment.estado, 'en camino')
        
        # Verificar que el pedido se actualizó a 'enviado'
        order.refresh_from_db()
        self.assertEqual(order.estado, 'enviado')
    
    def test_shipment_update_status_en_camino_order_already_enviado(self):
        """Test que verifica que no se actualiza el pedido si ya está en 'enviado'"""
        # Crear orden ya en estado 'enviado' y envío
        order = Order.objects.create(usuario=self.user, estado='enviado', total=100)
        shipment = Shipment.objects.create(
            pedido=order,
            direccion_envio=fake.address(),
            empresa_envio=fake.company(),
            numero_guia=fake.uuid4(),
            fecha_entrega_estimada=fake.date_this_year().isoformat(),
            estado='preparando'
        )
        
        url = reverse('shipment-update-status', kwargs={'pk': shipment.id})
        data = {'estado': 'en camino'}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 200)
        
        # Verificar que el envío se actualizó
        shipment.refresh_from_db()
        self.assertEqual(shipment.estado, 'en camino')
        
        # Verificar que el pedido sigue en 'enviado' (no cambió)
        order.refresh_from_db()
        self.assertEqual(order.estado, 'enviado')
    
    def test_shipment_update_status_entregado_updates_order(self):
        """Test que verifica que al marcar como 'entregado' se actualiza el pedido a 'entregado'"""
        # Crear orden y envío
        order = Order.objects.create(usuario=self.user, estado='enviado', total=100)
        shipment = Shipment.objects.create(
            pedido=order,
            direccion_envio=fake.address(),
            empresa_envio=fake.company(),
            numero_guia=fake.uuid4(),
            fecha_entrega_estimada=fake.date_this_year().isoformat(),
            estado='en camino'
        )
        
        url = reverse('shipment-update-status', kwargs={'pk': shipment.id})
        data = {'estado': 'entregado'}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 200)
        
        # Verificar que el envío se actualizó
        shipment.refresh_from_db()
        self.assertEqual(shipment.estado, 'entregado')
        
        # Verificar que el pedido se actualizó a 'entregado'
        order.refresh_from_db()
        self.assertEqual(order.estado, 'entregado')
    
    def test_shipment_update_status_entregado_order_already_entregado(self):
        """Test que verifica que no se actualiza el pedido si ya está en 'entregado'"""
        # Crear orden ya en estado 'entregado' y envío
        order = Order.objects.create(usuario=self.user, estado='entregado', total=100)
        shipment = Shipment.objects.create(
            pedido=order,
            direccion_envio=fake.address(),
            empresa_envio=fake.company(),
            numero_guia=fake.uuid4(),
            fecha_entrega_estimada=fake.date_this_year().isoformat(),
            estado='en camino'
        )
        
        url = reverse('shipment-update-status', kwargs={'pk': shipment.id})
        data = {'estado': 'entregado'}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 200)
        
        # Verificar que el envío se actualizó
        shipment.refresh_from_db()
        self.assertEqual(shipment.estado, 'entregado')
        
        # Verificar que el pedido sigue en 'entregado' (no cambió)
        order.refresh_from_db()
        self.assertEqual(order.estado, 'entregado')
    
    def test_shipment_update_status_operator_can_update(self):
        """Test que verifica que los operadores pueden actualizar el estado de envíos"""
        # Crear usuario operador
        operator_user = User.objects.create_user(
            username=fake.unique.user_name(),
            name=fake.unique.name(),
            email=fake.unique.email(),
            password='testpass123',
            role='operator'
        )
        self.client.force_authenticate(user=operator_user)
        
        # Crear orden y envío
        order = Order.objects.create(usuario=self.user, estado='pendiente', total=100)
        shipment = Shipment.objects.create(
            pedido=order,
            direccion_envio=fake.address(),
            empresa_envio=fake.company(),
            numero_guia=fake.uuid4(),
            fecha_entrega_estimada=fake.date_this_year().isoformat(),
            estado='pendiente'
        )
        
        url = reverse('shipment-update-status', kwargs={'pk': shipment.id})
        data = {'estado': 'preparando'}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'Estado de envío actualizado')
        
        # Verificar que el envío se actualizó
        shipment.refresh_from_db()
        self.assertEqual(shipment.estado, 'preparando')