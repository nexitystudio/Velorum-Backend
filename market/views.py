from django.shortcuts import render, get_object_or_404
from rest_framework import viewsets, status
from .serializer import *
from .models import *
from Velorum.permissions import *
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django.core.cache import cache
from django.utils import timezone

# Create your views here.

class CategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar las categorías de productos.
    - Administradores y operadores: acceso completo (CRUD)
    - Clientes: solo lectura (GET)
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer 
    permission_classes = [CategoryPermission]
    
    def get_queryset(self):
        """Filtrado para categorías"""
        queryset = Category.objects.all()
        
        # Filtrado por nombre
        nombre = self.request.query_params.get('nombre', None)
        if nombre:
            queryset = queryset.filter(nombre__icontains=nombre)
            
        return queryset

class ProductViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar productos.
    - Administradores y operadores: acceso completo (CRUD) 
    - Clientes: solo lectura (GET)
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [ProductPermission]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    
    def get_queryset(self):
        """Permite filtrar productos por nombre, categoría o precio"""
        queryset = Product.objects.all()
        
        # Si el usuario no es admin/operator, ocultar productos desactivados
        user = self.request.user
        if not (hasattr(user, 'role') and user.role in ['admin', 'operator']):
            queryset = queryset.filter(desactivado=False)
        
        nombre = self.request.query_params.get('nombre', None)
        categoria = self.request.query_params.get('categoria', None)
        precio_min = self.request.query_params.get('precio_min', None)
        precio_max = self.request.query_params.get('precio_max', None)
        
        if nombre:
            queryset = queryset.filter(nombre__icontains=nombre)
        if categoria:
            queryset = queryset.filter(categoria__id=categoria)
        if precio_min:
            queryset = queryset.filter(precio__gte=precio_min)
        if precio_max:
            queryset = queryset.filter(precio__lte=precio_max)
            
        return queryset
        
    @action(detail=True, methods=['post'], permission_classes=[AddToCartPermission])
    def add_to_cart(self, request, pk=None):
        """Endpoint personalizado para agregar producto al carrito"""
        # 1. Obtener el producto
        producto = self.get_object()
        
        # 2. Obtener la cantidad solicitada (default: 1)
        cantidad = int(request.data.get('cantidad', 1))
        
        # 3. Validar que la cantidad sea positiva
        if cantidad <= 0:
            return Response(
                {'error': 'La cantidad debe ser mayor a cero'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 4. Validar que haya suficiente stock
        if cantidad > producto.stock_disponible:
            return Response(
                {'error': f'Stock insuficiente. Solo hay {producto.stock_disponible} unidades disponibles'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 5. Obtener o crear el carrito del usuario
        carrito, created = Cart.objects.get_or_create(usuario=request.user)
        
        # 6. Buscar si el producto ya está en el carrito
        try:
            item = CartItem.objects.get(carrito=carrito, producto=producto)
            # 6.1 Si existe, actualizar cantidad (verificando stock)
            nueva_cantidad = item.cantidad + cantidad
            if nueva_cantidad > producto.stock_disponible:
                return Response(
                    {'error': f'Stock insuficiente. Solo hay {producto.stock_disponible} unidades disponibles'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            item.cantidad = nueva_cantidad
            item.save()
            mensaje = 'Producto actualizado en el carrito'
        except CartItem.DoesNotExist:
            # 6.2 Si no existe, crear nuevo item
            CartItem.objects.create(
                carrito=carrito,
                producto=producto,
                cantidad=cantidad
            )
            mensaje = 'Producto agregado al carrito'
        
        # 7. Preparar respuesta con los datos del carrito actualizado
        datos_carrito = {
            'mensaje': mensaje,
            'total_items': carrito.cantidad_items(),
            'total': float(carrito.total()),
            'producto_agregado': {
                'id': producto.id,
                'nombre': producto.nombre,
                'precio': float(producto.precio),
                'cantidad': cantidad,
            }
        }
        
        return Response(datos_carrito, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdminOrOperator])
    def reset_all_prices(self, request):
        """Resetea todos los precios de productos a precio_proveedor * 2"""
        try:
            productos = Product.objects.all()
            actualizados = 0
            
            for producto in productos:
                if producto.precio_proveedor:
                    nuevo_precio = producto.precio_proveedor * 2
                    producto.precio = nuevo_precio
                    producto.precio_manual = False
                    producto.save()
                    actualizados += 1
            
            return Response({
                'mensaje': f'Precios reseteados exitosamente',
                'actualizados': actualizados,
                'total': productos.count()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Error al resetear precios: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrOperator])
    def reset_price(self, request, pk=None):
        """Resetea el precio de un producto específico a precio_proveedor * 2"""
        try:
            producto = self.get_object()
            
            if not producto.precio_proveedor:
                return Response({
                    'error': 'Este producto no tiene precio de proveedor definido'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            nuevo_precio = producto.precio_proveedor * 2
            producto.precio = nuevo_precio
            producto.precio_manual = False
            producto.save()
            
            return Response({
                'mensaje': 'Precio reseteado exitosamente',
                'producto_id': producto.id,
                'precio_proveedor': float(producto.precio_proveedor),
                'precio_nuevo': float(nuevo_precio)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Error al resetear precio: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrOperator])
    def toggle_visibility(self, request, pk=None):
        """Activa o desactiva la visibilidad de un producto"""
        try:
            producto = self.get_object()
            producto.desactivado = not producto.desactivado
            producto.save()
            
            estado = 'oculto' if producto.desactivado else 'visible'
            
            return Response({
                'mensaje': f'Producto {estado} exitosamente',
                'producto_id': producto.id,
                'desactivado': producto.desactivado
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': f'Error al cambiar visibilidad: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CodigoDescuentoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar códigos de descuento.
    Solo administradores pueden crear, editar y eliminar códigos.
    """
    queryset = CodigoDescuento.objects.all()
    serializer_class = CodigoDescuentoSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        """Ordena por fecha de creación descendente"""
        return CodigoDescuento.objects.all().order_by('-fecha_creacion')

class OrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar órdenes/pedidos.
    - Administradores y operadores: acceso completo a todas las órdenes
    - Clientes: pueden crear órdenes y ver/editar solo las suyas
    """
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [OrderPermission]
    
    def get_queryset(self):
        """
        Filtra para que clientes vean solo sus órdenes.
        Los administradores y operadores ven todas las órdenes.
        Este método se usa para las rutas principales (GET /orders/, GET /orders/{id}/).
        """
        user = self.request.user
        if hasattr(user, 'role') and user.role in ['admin', 'operator']:
            return Order.objects.all()
        return Order.objects.filter(usuario=user)
    
    @action(detail=False, methods=['get'], url_path='my-orders', permission_classes=[IsAuthenticated])
    def my_orders(self, request):
        """
        Endpoint dedicado para que CUALQUIER usuario (incluido admin)
        vea solo sus propios pedidos.
        """
        user = request.user
        orders = Order.objects.filter(usuario=user).order_by('-fecha')
        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        """
        Crea una nueva orden asociada al usuario actual.
        Procesa los detalles de la orden si se proporcionan.
        """
        user = self.request.user
        # Usar dirección del body si existe, sino usar la del usuario
        direccion = serializer.validated_data.get('direccion_envio') or user.address
        # Asignar el usuario actual como dueño de la orden
        orden = serializer.save(usuario=user, direccion_envio=direccion)
        # Recalcular el total de la orden en base a los detalles
        orden.total_update()
        
        return orden
        
    def perform_update(self, serializer):
        """Maneja la actualización de una orden y sus detalles"""
        instance = self.get_object()
        
        # Verificar si se pueden hacer cambios según el estado
        if instance.estado in ['entregado', 'cancelado']:
            raise serializers.ValidationError(
                f"No se puede modificar un pedido en estado '{instance.estado}'"
            )
        
        # Actualizar los campos básicos de la orden
        updated_instance = serializer.save()
        
        # Procesar detalles si se proporcionan
        detalles_data = self.request.data.get('detalles', [])
        if detalles_data:
            # Manejar cada detalle de la orden
            self._process_order_details(updated_instance, detalles_data)
            
        # Recalcular total
        if hasattr(updated_instance, 'total_update'):
            updated_instance.total_update()
    
    def _process_order_details(self, order, detalles_data):
        """Procesa los detalles de una orden durante la actualización"""
        for detalle_data in detalles_data:
            producto_id = detalle_data.get('producto')
            cantidad = detalle_data.get('cantidad', 1)
            detalle_id = detalle_data.get('id', None)
            
            if not producto_id:
                continue
                
            try:
                producto = Product.objects.get(id=producto_id)
                
                if detalle_id:
                    # Actualizar detalle existente
                    try:
                        detalle = OrderDetail.objects.get(id=detalle_id, pedido=order)
                        
                        # Si la cantidad cambia, ajustar el stock
                        if detalle.cantidad != cantidad:
                            # Devolver el stock anterior
                            producto.stock += detalle.cantidad
                            # Restar el nuevo stock
                            if producto.stock < cantidad:
                                raise serializers.ValidationError(
                                    f"Stock insuficiente para {producto.nombre}"
                                )
                            producto.stock -= cantidad
                            producto.save()
                        
                        detalle.cantidad = cantidad
                        detalle.save()
                    except OrderDetail.DoesNotExist:
                        raise serializers.ValidationError(
                            f"Detalle con id {detalle_id} no pertenece a esta orden"
                        )
                else:
                    # Crear nuevo detalle
                    if producto.stock < cantidad:
                        raise serializers.ValidationError(
                            f"Stock insuficiente para {producto.nombre}"
                        )
                        
                    OrderDetail.objects.create(
                        pedido=order,
                        producto=producto,
                        cantidad=cantidad
                    )
            except Product.DoesNotExist:
                # Ignorar productos que no existen
                pass
    
    @action(detail=True, methods=['post'], url_path='remove-detail/(?P<detail_id>[^/.]+)')
    def remove_detail(self, request, pk=None, detail_id=None):
        """Elimina un detalle específico de la orden"""
        order = self.get_object()
        
        # Verificar estado del pedido
        if order.estado in ['entregado', 'cancelado']:
            return Response(
                {'error': f'No se puede modificar un pedido en estado {order.estado}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            detail = OrderDetail.objects.get(id=detail_id, pedido=order)
            
            # Devolver el stock
            producto = detail.producto
            producto.stock += detail.cantidad
            producto.save()
            
            # Eliminar el detalle
            detail.delete()
            
            # Actualizar el total
            order.total_update()
            
            return Response(
                {'status': 'Detalle eliminado', 'total_actualizado': float(order.total)}, 
                status=status.HTTP_200_OK
            )
        except OrderDetail.DoesNotExist:
            return Response(
                {'error': 'El detalle no existe o no pertenece a esta orden'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'], permission_classes=[CancelOrderPermission])
    def cancel(self, request, pk=None):
        """Endpoint para cancelar una orden"""
        order = self.get_object()
        
        # Verificación de estado
        if order.estado == 'cancelado':
            return Response(
                {"error": "La orden ya está cancelada"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if order.estado not in ['pendiente', 'procesando']:
            return Response(
                {"error": f"No se puede cancelar una orden en estado '{order.estado}'"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Cambiar estado
        order.estado = 'cancelado'
        order.save()
        
        return Response({"message": "Orden cancelada correctamente"})
    
    @action(detail=True, methods=['post'])
    def update_total(self, request, pk=None):
        """Endpoint para actualizar el total del pedido"""
        order = self.get_object()
        order.total_update()  # Usa el método personalizado del modelo
        return Response({'status': 'total actualizado', 'total': order.total}, 
                        status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def force_delete(self, request, pk=None):
        """
        Elimina forzadamente un pedido (solo admin/operator),
        restaurando stock y cerrando pagos abiertos previamente.
        """
        if getattr(request.user, 'role', None) not in ['admin', 'operator']:
            return Response({'error': 'No autorizado'}, status=status.HTTP_403_FORBIDDEN)
        order = self.get_object()
        # 1) Cerrar pagos abiertos (pendiente/en_revision) como fallido
        abiertos = Pay.objects.filter(pedido=order, estado__in=['pendiente', 'en_revision'])
        for p in abiertos:
            p.fail()
        # 2) Restaurar stock si el pedido no estaba cancelado aún
        if order.estado != 'cancelado':
            for det in order.detalles.all():
                prod = det.producto
                prod.stock += det.cantidad
                prod.save()
        # 3) Eliminar pagos y pedido
        Pay.objects.filter(pedido=order).delete()
        order.delete()
        return Response({'status': 'pedido eliminado'}, status=status.HTTP_200_OK)
    
class CartViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar el carrito de compras.
    - Cada usuario solo puede ver y modificar su propio carrito
    """
    serializer_class = CartSerializer  # Necesitarás crear este serializer
    permission_classes = [IsAuthenticated]  # Solo usuarios autenticados
    
    def get_queryset(self):
        """Retorna solo el carrito del usuario actual"""
        return Cart.objects.filter(usuario=self.request.user)
    
    def list(self, request):
        """Obtener detalles del carrito actual del usuario"""
        carrito, created = Cart.objects.get_or_create(usuario=request.user)
        serializer = self.get_serializer(carrito)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def clear(self, request):
        """Vaciar el carrito"""
        carrito, created = Cart.objects.get_or_create(usuario=request.user)
        carrito.limpiar()
        return Response({'mensaje': 'Carrito vaciado correctamente'}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def checkout(self, request):
        """Convertir carrito en pedido"""
        carrito, created = Cart.objects.get_or_create(usuario=request.user)
        
        # Verificar que el carrito no esté vacío
        if carrito.items.count() == 0:
            return Response(
                {'error': 'El carrito está vacío'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar stock disponible para todos los productos (primer chequeo)
        for item in carrito.items.all():
            if item.cantidad > item.producto.stock_disponible:
                return Response(
                    {'error': f'Stock insuficiente para {item.producto.nombre}. Solo hay {item.producto.stock_disponible} unidades disponibles'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        direccion_cliente = getattr(request.user, 'address', 'Dirección no proporcionada por el cliente')
        
        # Crear nuevo pedido
        pedido = Order.objects.create(
            usuario=request.user,
            estado='pendiente',
            total=carrito.total(),
            direccion_envio=direccion_cliente
        )
        
        # Transferir items del carrito al pedido (segundo chequeo y reducción de stock)
        for item in carrito.items.all():
            # Refrescar el producto desde la base de datos para obtener stock actualizado
            item.producto.refresh_from_db()
            
            # Verificar stock nuevamente (segundo chequeo)
            if item.cantidad > item.producto.stock_disponible:
                # Si falla, eliminar el pedido creado y retornar error
                pedido.delete()
                return Response(
                    {'error': f'Stock insuficiente para {item.producto.nombre}. Solo hay {item.producto.stock_disponible} unidades disponibles'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Crear el detalle del pedido
            OrderDetail.objects.create(
                pedido=pedido,
                producto=item.producto,
                cantidad=item.cantidad,
                subtotal=item.cantidad * item.producto.precio
            )
            
            # Incrementar stock vendido
            item.producto.stock_vendido += item.cantidad
            item.producto.save()
        
        # Vaciar el carrito
        carrito.limpiar()
        
        return Response({
            'mensaje': 'Pedido creado correctamente',
            'pedido_id': pedido.id,
            'total': float(pedido.total)
        }, status=status.HTTP_201_CREATED)

class PayViewSet(viewsets.ModelViewSet):
    """Pagos y acciones de simulación (completar / fallar)."""
    queryset = Pay.objects.select_related('pedido', 'pedido__usuario')
    serializer_class = PaySerializer
    permission_classes = [PaymentPermission]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        estado = self.request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        if getattr(user, 'role', None) not in ['admin', 'operator'] and self.action == 'list':
            qs = qs.filter(pedido__usuario=user)
        pedido_id = self.request.query_params.get('pedido')
        if pedido_id:
            qs = qs.filter(pedido_id=pedido_id)
        return qs

    def perform_create(self, serializer):
        pedido = serializer.validated_data.get('pedido')
        user = self.request.user
        if getattr(user, 'role', None) not in ['admin', 'operator'] and pedido.usuario != user:
            raise serializers.ValidationError('No puedes crear pagos para pedidos ajenos')
        if pedido.estado not in ['pendiente']:
            raise serializers.ValidationError(f"No se puede pagar un pedido en estado '{pedido.estado}'")
        serializer.save()

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        pago = self.get_object()
        if pago.estado not in ['pendiente','en_revision']:
            return Response({'error': 'Solo se puede completar un pago pendiente o en revisión'}, status=status.HTTP_400_BAD_REQUEST)
        # Solo admin/operator pueden completar (aprobar) directamente
        if getattr(request.user, 'role', None) not in ['admin', 'operator']:
            return Response({'error': 'No autorizado'}, status=status.HTTP_403_FORBIDDEN)
        pago.complete()
        ser = self.get_serializer(pago)
        return Response(ser.data)

    @action(detail=True, methods=['post'])
    def fail(self, request, pk=None):
        pago = self.get_object()
        if pago.estado not in ['pendiente','en_revision']:
            return Response({'error': 'Solo se puede fallar un pago pendiente o en revisión'}, status=status.HTTP_400_BAD_REQUEST)
        # Permitir al dueño o staff
        if getattr(request.user, 'role', None) not in ['admin', 'operator'] and pago.pedido.usuario != request.user:
            return Response({'error': 'No autorizado'}, status=status.HTTP_403_FORBIDDEN)
        pago.fail()
        ser = self.get_serializer(pago)
        return Response(ser.data)

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        """Marcar un pago como 'en revisión' (admin/operator)."""
        pago = self.get_object()
        if getattr(request.user, 'role', None) not in ['admin', 'operator']:
            return Response({'error': 'No autorizado'}, status=status.HTTP_403_FORBIDDEN)
        if pago.estado not in ['pendiente']:
            return Response({'error': 'Solo se puede pasar a revisión un pago pendiente'}, status=status.HTTP_400_BAD_REQUEST)
        pago.estado = 'en_revision'
        pago.save()
        # Mantener consistencia: si el pedido estaba 'pendiente', también pasarlo a 'en_revision'
        pedido = pago.pedido
        if pedido and pedido.estado == 'pendiente':
            pedido.estado = 'en_revision'
            pedido.save()
        return Response(self.get_serializer(pago).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Aprobar un pago en revisión (admin/operator)."""
        pago = self.get_object()
        if getattr(request.user, 'role', None) not in ['admin', 'operator']:
            return Response({'error': 'No autorizado'}, status=status.HTTP_403_FORBIDDEN)
        if pago.estado != 'en_revision':
            return Response({'error': 'Solo se puede aprobar un pago en revisión'}, status=status.HTTP_400_BAD_REQUEST)
        pago.complete()
        return Response(self.get_serializer(pago).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Rechazar un pago en revisión (admin/operator)."""
        pago = self.get_object()
        if getattr(request.user, 'role', None) not in ['admin', 'operator']:
            return Response({'error': 'No autorizado'}, status=status.HTTP_403_FORBIDDEN)
        if pago.estado != 'en_revision':
            return Response({'error': 'Solo se puede rechazar un pago en revisión'}, status=status.HTTP_400_BAD_REQUEST)
        pago.fail()
        # Devolver el pedido a 'pendiente' si estaba en revisión
        pedido = pago.pedido
        if pedido and pedido.estado == 'en_revision':
            pedido.estado = 'pendiente'
            pedido.save()
        return Response(self.get_serializer(pago).data)

    @action(detail=True, methods=['post'], parser_classes=[JSONParser, MultiPartParser, FormParser])
    def proof(self, request, pk=None):
        """Cliente o admin sube/declara comprobante; pasa el pago a 'en_revision'."""
        pago = self.get_object()
        # Dueño o staff
        if getattr(request.user, 'role', None) not in ['admin', 'operator'] and pago.pedido.usuario != request.user:
            return Response({'error': 'No autorizado'}, status=status.HTTP_403_FORBIDDEN)
        if pago.estado not in ['pendiente']:
            return Response({'error': 'Solo se puede adjuntar comprobante a pagos pendientes'}, status=status.HTTP_400_BAD_REQUEST)
        file = request.data.get('comprobante_archivo')
        url = request.data.get('comprobante_url')
        if not file and not url:
            return Response({'error': 'Debe enviar comprobante_archivo o comprobante_url'}, status=status.HTTP_400_BAD_REQUEST)
        if file:
            pago.comprobante_archivo = file
        if url:
            pago.comprobante_url = url
        pago.estado = 'en_revision'
        pago.save()
        # Marcar también el pedido como en revisión
        if pago.pedido.estado == 'pendiente':
            pedido = pago.pedido
            pedido.estado = 'en_revision'
            pedido.save()
        return Response(self.get_serializer(pago).data)

class ShipmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet para envíos.
    - Admin y operadores: acceso completo a todos los envíos
    - Clientes: solo pueden ver información de sus propios envíos
    """
    queryset = Shipment.objects.all()
    serializer_class = ShipmentSerializer
    permission_classes = [ShipmentPermission]
    
    def get_queryset(self):
        """Filtra para que clientes vean solo envíos de sus órdenes"""
        user = self.request.user
        if user.role in ['admin', 'operator']:
            return Shipment.objects.all()
        return Shipment.objects.filter(pedido__usuario=user)
    
    @action(detail=True, methods=['get'], permission_classes=[TrackingPermission])
    def tracking(self, request, pk=None):
        """Endpoint para consultar el estado del envío"""
        shipment = self.get_object()
        tracking_data = {
            'numero_guia': shipment.numero_guia,
            'estado': shipment.estado,
            'empresa_envio': shipment.empresa_envio,
            'fecha_entrega_estimada': shipment.fecha_entrega_estimada,
            'direccion_envio': shipment.direccion_envio
        }
        return Response(tracking_data)
    
    @action(detail=True, methods=['post'], permission_classes=[])  # Sin permisos
    def update_status(self, request, pk=None):
        """Endpoint para actualizar el estado del envío (solo admin/operator)"""
        if not request.user.role in ['admin', 'operator']:
            return Response({'error': 'No autorizado'}, status=status.HTTP_403_FORBIDDEN)
            
        shipment = self.get_object()
        nuevo_estado = request.data.get('estado')
        
        # Valida que el estado sea válido
        estados_validos = ['pendiente', 'preparando', 'en camino', 'entregado']
        if nuevo_estado not in estados_validos:
            return Response({'error': 'Estado inválido'}, status=status.HTTP_400_BAD_REQUEST)
            
        shipment.estado = nuevo_estado
        
        # Si se marca como enviado, actualizar también el pedido
        if nuevo_estado == 'en camino' and shipment.pedido.estado != 'enviado':
            shipment.pedido.estado = 'enviado'
            shipment.pedido.save()
            
        # Si se marca como entregado, actualizar también el pedido
        if nuevo_estado == 'entregado' and shipment.pedido.estado != 'entregado':
            shipment.pedido.estado = 'entregado'
            shipment.pedido.save()
            
        shipment.save()
        return Response({'status': 'Estado de envío actualizado'}, status=status.HTTP_200_OK)

class CartItemViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar items individuales del carrito.
    Permite actualizar cantidades y eliminar items específicos.
    """
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Retorna solo los items del carrito del usuario actual"""
        return CartItem.objects.filter(carrito__usuario=self.request.user)
    
    def list(self, request, *args, **kwargs):
        """Lista todos los items del carrito del usuario"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'items': serializer.data,
            'total_items': queryset.count()
        })
    
    def retrieve(self, request, *args, **kwargs):
        """Obtiene un item específico del carrito"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def update(self, request, *args, **kwargs):
        """Actualizar cantidad de un item del carrito (PUT)"""
        return self.partial_update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        """Actualizar cantidad de un item del carrito (PATCH)"""
        instance = self.get_object()
        cantidad = request.data.get('cantidad', instance.cantidad)
        
        # Validar que la cantidad sea un número válido
        try:
            cantidad = int(cantidad)
        except (ValueError, TypeError):
            return Response(
                {'error': 'La cantidad debe ser un número válido'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Si la cantidad es 0 o negativa, eliminar el item
        if cantidad <= 0:
            instance.delete()
            return Response({
                'mensaje': 'Item eliminado del carrito',
                'item_eliminado': True
            }, status=status.HTTP_200_OK)
        
        # Validar stock disponible
        if cantidad > instance.producto.stock_disponible:
            return Response({
                'error': f'Stock insuficiente. Solo hay {instance.producto.stock_disponible} unidades disponibles'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Actualizar cantidad
        instance.cantidad = cantidad
        instance.save()
        
        # Serializar la respuesta
        serializer = self.get_serializer(instance)
        
        return Response({
            'mensaje': 'Cantidad actualizada exitosamente',
            'item': serializer.data,
            'nueva_cantidad': instance.cantidad,
            'subtotal': float(instance.subtotal())
        }, status=status.HTTP_200_OK)
    
    def destroy(self, request, *args, **kwargs):
        """Eliminar un item del carrito"""
        instance = self.get_object()
        producto_nombre = instance.producto.nombre
        
        # Eliminar el item
        instance.delete()
        
        return Response({
            'mensaje': f'"{producto_nombre}" eliminado del carrito',
            'item_eliminado': True
        }, status=status.HTTP_200_OK)

class FavoriteViewSet(viewsets.ModelViewSet):
    """
    Favoritos del usuario.
    - Clientes: solo sus favoritos.
    - Admin/Operador: pueden ver todos; opcionalmente filtrar por ?user=<id>.
    """
    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]

    def get_queryset(self):
        user = self.request.user
        qs = Favorite.objects.select_related('product')
        if getattr(user, 'role', None) in ['admin', 'operator']:
            uid = self.request.query_params.get('user')
            return qs.filter(user_id=uid) if uid else qs
        return qs.filter(user=user)

    def create(self, request, *args, **kwargs):
        product_id = request.data.get('product_id')
        if not product_id:
            return Response({'detail': 'product_id es requerido'}, status=status.HTTP_400_BAD_REQUEST)
        inst, created = Favorite.objects.get_or_create(user=request.user, product_id=product_id)
        ser = self.get_serializer(inst)
        return Response(ser.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        # Permitir DELETE por ?product_id=123 además de /favorites/<id>/
        product_id = request.query_params.get('product_id')
        if product_id:
            fav = get_object_or_404(Favorite, user=request.user, product_id=product_id)
            fav.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['post'])
    def bulk(self, request):
        """
        Fusión de favoritos de invitado al iniciar sesión.
        Body: { "product_ids": [1,2,3] }
        """
        ids = request.data.get('product_ids') or []
        if not isinstance(ids, list):
            return Response({'detail': 'product_ids debe ser una lista'}, status=status.HTTP_400_BAD_REQUEST)
        created = 0
        for pid in ids:
            _, ok = Favorite.objects.get_or_create(user=request.user, product_id=pid)
            if ok:
                created += 1
        return Response({'merged': created}, status=status.HTTP_200_OK)


# ============================================================
# ENDPOINTS PARA SINCRONIZACIÓN DE PRODUCTOS EXTERNOS
# ============================================================

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from market.scraper import sync_external_products
import logging

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def manual_sync_products(request):
    """
    Endpoint para sincronización manual de productos externos.
    Solo accesible por administradores.
    
    POST /api/products/sync-external/
    
    Returns:
        {
            "success": true,
            "productos_nuevos": 10,
            "productos_actualizados": 517,
            "total": 527,
            "desactivados": 0,
            "errores": []
        }
    """
    try:
        logger.info("Sincronización manual iniciada por usuario: " + request.user.username)
        resultado = sync_external_products()
        
        return Response(resultado, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error en sincronización manual: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_product_price(request, pk):
    """
    Actualiza el precio de un producto manualmente.
    Marca el precio como manual para que el scraper no lo sobrescriba.
    
    PATCH /api/products/<id>/update-price/
    Body: {"precio": 15000}
    
    Returns:
        {
            "success": true,
            "producto": {...}
        }
    """
    try:
        producto = Product.objects.get(pk=pk)
        nuevo_precio = request.data.get('precio')
        
        if not nuevo_precio:
            return Response({
                'success': False,
                'error': 'El campo precio es requerido'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        producto.precio = float(nuevo_precio)
        producto.precio_manual = True
        producto.save()
        
        serializer = ProductSerializer(producto)
        
        return Response({
            'success': True,
            'producto': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Product.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Producto no encontrado'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def reset_stock_vendido(request, pk):
    """
    Resetea el stock vendido cuando recibís los productos del proveedor.
    
    POST /api/products/<id>/reset-stock/
    
    Returns:
        {
            "success": true,
            "stock_disponible": 19
        }
    """
    try:
        producto = Product.objects.get(pk=pk)
        producto.stock_vendido = 0
        producto.save()
        
        return Response({
            'success': True,
            'stock_disponible': producto.stock_disponible
        }, status=status.HTTP_200_OK)
        
    except Product.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Producto no encontrado'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def bulk_update_markup(request):
    """
    Recalcula los precios de todos los productos con un nuevo markup.
    Solo afecta productos que NO tienen precio manual.
    
    POST /api/products/bulk-markup/
    Body: {"markup_percentage": 100}  // 100% = precio x2
    
    Returns:
        {
            "success": true,
            "productos_actualizados": 527
        }
    """
    try:
        markup_percentage = float(request.data.get('markup_percentage', 100))
        markup_multiplier = 1 + (markup_percentage / 100)
        
        # Solo actualizar productos sin precio manual y con precio_proveedor
        productos = Product.objects.filter(
            precio_manual=False,
            precio_proveedor__isnull=False
        )
        
        count = 0
        for producto in productos:
            producto.precio = float(producto.precio_proveedor) * markup_multiplier
            producto.save()
            count += 1
        
        return Response({
            'success': True,
            'productos_actualizados': count,
            'markup_aplicado': markup_percentage
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# ENDPOINTS PARA MERCADO PAGO
# ============================================================

from .mercadopago_service import create_preference, process_payment_notification


@api_view(['POST'])
def create_mp_preference(request):
    """
    Crea un pedido y genera una preferencia de pago en Mercado Pago.
    Permite compras tanto de usuarios autenticados como invitados.
    
    POST /market/mp/create-preference/
    """
    try:
        print("📦 Datos recibidos:", request.data)
        
        customer_data = request.data.get('customer_data', {})
        shipping_data = request.data.get('shipping_data', {})
        cart_items = request.data.get('cart_items', [])
        total = float(request.data.get('total', 0))
        costo_envio = float(request.data.get('costo_envio', 0))
        
        if not cart_items:
            return Response({'success': False, 'error': 'Carrito vacío'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Construir dirección
        direccion_completa = f"{shipping_data.get('calle', '')} {shipping_data.get('numero', '')}"
        if shipping_data.get('piso'):
            direccion_completa += f", Piso {shipping_data['piso']}"
        if shipping_data.get('departamento'):
            direccion_completa += f", Depto {shipping_data['departamento']}"
        direccion_completa += f", {shipping_data.get('ciudad', '')}, {shipping_data.get('provincia', '')} - CP: {shipping_data.get('codigo_postal', '')}"
        
        # Crear orden con todos los datos de envío y pago
        order_data = {
            'usuario': request.user if request.user.is_authenticated else None,
            'direccion_envio': direccion_completa,
            'estado': 'pendiente',
            'costo_envio': costo_envio,
            'codigo_postal': shipping_data.get('codigo_postal', ''),
            'zona_envio': shipping_data.get('zona', ''),
            'metodo_pago': 'Mercado Pago',
            # Datos del invitado
            'email_invitado': customer_data.get('email') if not request.user.is_authenticated else None,
            'nombre_invitado': customer_data.get('nombre') if not request.user.is_authenticated else None,
            'apellido_invitado': customer_data.get('apellido') if not request.user.is_authenticated else None,
            'telefono_invitado': customer_data.get('telefono_contacto') if not request.user.is_authenticated else None,
            'detalles_input': [{
                'watch_id': item.get('watch_id') or item.get('id_backend') or item.get('id'),
                'cantidad': item.get('quantity', 1),
                'precio_unitario': item.get('price', 0)
            } for item in cart_items]
        }
        
        print("📋 Order data preparada:", order_data)
        
        from .serializer import OrderSerializer
        serializer = OrderSerializer(data=order_data, context={'request': request})
        
        if not serializer.is_valid():
            print(f"❌ Error de validación del serializer: {serializer.errors}")
            return Response({'success': False, 'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        order = serializer.save()
        print(f"✅ Orden creada: #{order.id}")
        
        # Preparar items para MP
        mp_items = [{'name': item.get('name', 'Producto'), 'quantity': item.get('quantity', 1), 'price': item.get('price', 0)} for item in cart_items]
        if costo_envio > 0:
            mp_items.append({'name': 'Envío', 'quantity': 1, 'price': costo_envio})
        
        mp_data = {
            'order_id': order.id,
            'items': mp_items,
            'payer_email': customer_data.get('email', ''),
            'payer_name': f"{customer_data.get('nombre', '')} {customer_data.get('apellido', '')}".strip(),
            'payer_phone': customer_data.get('telefono_contacto', ''),
            'payer_address': {
                'street_name': shipping_data.get('calle', ''),
                'street_number': shipping_data.get('numero', ''),
                'zip_code': shipping_data.get('codigo_postal', '')
            },
            'total': total + costo_envio
        }
        
        preference = create_preference(mp_data)
        
        return Response({
            'success': True,
            'order_id': order.id,
            'preference_id': preference['preference_id'],
            'init_point': preference['init_point']
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"❌ Error creando preferencia de MP: {str(e)}")
        import traceback
        traceback.print_exc()
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def mercadopago_webhook(request):
    """
    Webhook para recibir notificaciones de Mercado Pago.
    POST /market/mp/webhook/
    """
    try:
        topic = request.query_params.get('topic') or request.data.get('type')
        resource_id = request.query_params.get('id') or request.data.get('data', {}).get('id')
        
        logger.info(f"Webhook MP - Topic: {topic}, ID: {resource_id}")
        
        if topic == 'payment' and resource_id:
            payment_info = process_payment_notification(resource_id)
            order_id = payment_info.get('order_id')
            
            if order_id:
                try:
                    order = Order.objects.get(id=order_id)
                    
                    if payment_info['status'] == 'approved':
                        order.estado_pago = 'completado'
                        order.estado = 'pagado'
                        pay_estado = 'completado'
                    elif payment_info['status'] == 'pending':
                        order.estado_pago = 'pendiente'
                        pay_estado = 'pendiente'
                    elif payment_info['status'] in ['rejected', 'cancelled']:
                        order.estado_pago = 'fallido'
                        pay_estado = 'fallido'
                    else:
                        pay_estado = 'en_revision'
                    
                    order.save()
                    
                    # Crear o actualizar registro de pago
                    pay, created = Pay.objects.get_or_create(
                        pedido=order,
                        external_id=str(payment_info['payment_id']),
                        defaults={
                            'metodo': 'tarjeta',
                            'monto_pagado': payment_info['transaction_amount'],
                            'estado': pay_estado,
                            'metadata': {
                                'payment_method_id': payment_info['payment_method_id'],
                                'status_detail': payment_info['status_detail'],
                                'mp_payment_id': payment_info['payment_id']
                            }
                        }
                    )
                    if not created:
                        # Actualizar si ya existe
                        pay.estado = pay_estado
                        pay.monto_pagado = payment_info['transaction_amount']
                        pay.metadata.update({
                            'payment_method_id': payment_info['payment_method_id'],
                            'status_detail': payment_info['status_detail'],
                            'mp_payment_id': payment_info['payment_id']
                        })
                        pay.save()
                    
                    logger.info(f"Orden {order_id} actualizada: {payment_info['status']}, Pay {'creado' if created else 'actualizado'}")
                    
                except Order.DoesNotExist:
                    logger.error(f"Orden {order_id} no encontrada")
        
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error en webhook MP: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_200_OK)


@api_view(['POST'])
def validar_codigo_descuento(request):
    """
    Valida un código de descuento.
    POST /market/validar-codigo-descuento/
    Body: { "codigo": "MANOLITO", "monto_compra": 50000 }
    """
    try:
        codigo_str = request.data.get('codigo', '').strip().upper()
        monto_compra = float(request.data.get('monto_compra', 0))
        
        if not codigo_str:
            return Response({
                'valido': False,
                'mensaje': 'Debes ingresar un código'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            codigo = CodigoDescuento.objects.get(codigo=codigo_str)
        except CodigoDescuento.DoesNotExist:
            return Response({
                'valido': False,
                'mensaje': 'Código de descuento no válido'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Verificar si el código es válido
        usuario = request.user if request.user.is_authenticated else None
        puede_usar, mensaje = codigo.puede_usar(usuario, monto_compra)
        
        if not puede_usar:
            return Response({
                'valido': False,
                'mensaje': mensaje
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Código válido
        return Response({
            'valido': True,
            'codigo': codigo.codigo,
            'porcentaje': float(codigo.porcentaje_descuento),
            'descripcion': codigo.descripcion or f'{codigo.porcentaje_descuento}% de descuento'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error validando código de descuento: {str(e)}")
        return Response({
            'valido': False,
            'mensaje': 'Error al validar el código'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def validate_checkout_access(request):
    """
    Valida que el acceso provenga de Mercado Pago usando sus parámetros automáticos
    """
    # Parámetros que MP agrega automáticamente
    payment_id = request.GET.get('payment_id') or request.GET.get('collection_id')
    external_reference = request.GET.get('external_reference')
    preference_id = request.GET.get('preference_id')
    
    # Si no hay parámetros de MP, es acceso directo no autorizado
    if not payment_id and not preference_id:
        return Response({
            'valid': False,
            'error': 'Acceso no autorizado - debe venir desde Mercado Pago'
        }, status=403)
    
    # Obtener order_id del external_reference
    order_id = external_reference
    
    if not order_id:
        return Response({
            'valid': False,
            'error': 'No se pudo identificar el pedido'
        }, status=400)
    
    try:
        # Verificar que el pago sea real consultando a MP
        if payment_id:
            payment_info = process_payment_notification(payment_id)
            
            # Verificar que el payment_id corresponda a esta orden
            if str(payment_info.get('order_id')) != str(order_id):
                return Response({
                    'valid': False,
                    'error': 'El pago no corresponde a esta orden'
                }, status=403)
        
        # Obtener la orden
        order = Order.objects.select_related('usuario').prefetch_related('detalles__producto').get(id=order_id)
        
        return Response({
            'valid': True,
            'order': {
                'id': order.id,
                'total': order.total,
                'estado': order.estado,
                'usuario': order.usuario.username if order.usuario else 'Invitado',
                'email': order.usuario.email if order.usuario else order.email_invitado,
                'email_invitado': order.email_invitado,
                'nombre_invitado': order.nombre_invitado,
                'apellido_invitado': order.apellido_invitado,
                'telefono_invitado': order.telefono_invitado,
                'productos': list(order.detalles.values(
                    'producto__nombre',
                    'cantidad',
                    'subtotal'
                ))
            }
        })
        
    except Order.DoesNotExist:
        return Response({
            'valid': False,
            'error': 'Orden no encontrada'
        }, status=404)
    except Exception as e:
        logger.error(f"Error validando acceso: {str(e)}")
        return Response({
            'valid': False,
            'error': 'Error al validar el acceso'
        }, status=500)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_product_price(request, pk):
    """Actualiza el precio de un producto individualmente"""
    try:
        producto = Product.objects.get(pk=pk)
        nuevo_precio = request.data.get('precio')
        
        if nuevo_precio is None:
            return Response({
                'error': 'Debes proporcionar un precio'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        producto.precio = float(nuevo_precio)
        producto.precio_manual = True  # Marcar como precio editado manualmente
        producto.save()
        
        return Response({
            'mensaje': 'Precio actualizado correctamente',
            'producto_id': producto.id,
            'precio_nuevo': float(producto.precio)
        }, status=status.HTTP_200_OK)
        
    except Product.DoesNotExist:
        return Response({
            'error': 'Producto no encontrado'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': f'Error al actualizar precio: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def reset_stock_vendido(request, pk):
    """Resetea el stock vendido de un producto a 0"""
    try:
        producto = Product.objects.get(pk=pk)
        producto.stock_vendido = 0
        producto.save()
        
        return Response({
            'mensaje': 'Stock vendido reseteado correctamente',
            'producto_id': producto.id,
            'stock_vendido': producto.stock_vendido
        }, status=status.HTTP_200_OK)
        
    except Product.DoesNotExist:
        return Response({
            'error': 'Producto no encontrado'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': f'Error al resetear stock: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def bulk_update_markup(request):
    """Actualiza el markup (margen) de múltiples productos"""
    try:
        markup = request.data.get('markup', 2.0)  # Por defecto 100% de margen (x2)
        producto_ids = request.data.get('producto_ids', [])
        
        if not producto_ids:
            # Si no se especifican IDs, aplicar a todos los productos
            productos = Product.objects.filter(precio_proveedor__isnull=False)
        else:
            productos = Product.objects.filter(id__in=producto_ids, precio_proveedor__isnull=False)
        
        actualizados = 0
        for producto in productos:
            producto.precio = producto.precio_proveedor * float(markup)
            producto.precio_manual = False
            producto.save()
            actualizados += 1
        
        return Response({
            'mensaje': f'{actualizados} productos actualizados',
            'actualizados': actualizados,
            'markup': float(markup)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Error al actualizar markup: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
