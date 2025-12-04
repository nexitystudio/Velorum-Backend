from rest_framework import serializers
from .models import *
from account_admin.serializer import UserSerializer
from rest_framework.exceptions import ValidationError
from rest_framework import parsers
import json

class CodigoDescuentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CodigoDescuento
        fields = [
            'id', 'codigo', 'descripcion', 'porcentaje_descuento', 
            'activo', 'fecha_inicio', 'fecha_expiracion', 
            'usos_maximos', 'usos_actuales', 'usos_por_usuario',
            'monto_minimo', 'fecha_creacion', 'fecha_actualizacion'
        ]
        read_only_fields = ['usos_actuales', 'fecha_creacion', 'fecha_actualizacion', 'creado_por']

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    categoria = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        required=True
    )
    imagen = serializers.ImageField(required=False, allow_null=True)
    # Campo derivado para exponer la URL de la imagen
    imagen_url = serializers.SerializerMethodField(read_only=True)
    # Campos calculados
    stock_disponible = serializers.ReadOnlyField()
    disponible = serializers.ReadOnlyField()
    imagen_principal = serializers.ReadOnlyField()
    precio_final = serializers.ReadOnlyField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'nombre', 'descripcion', 'precio', 'stock', 'categoria',
            'imagen', 'imagen_url',
            # Campos de dropshipping
            'external_id', 'slug', 'precio_proveedor', 'precio_manual',
            'stock_proveedor', 'stock_vendido', 'stock_ilimitado',
            'imagenes', 'external_url', 'last_sync',
            'en_oferta', 'precio_oferta_proveedor', 'desactivado',
            # Campos calculados
            'stock_disponible', 'disponible', 'imagen_principal', 'precio_final'
        ]

    def get_imagen_url(self, obj):
        # Si cloudinary retorna URL absoluta, esto la devuelve tal cual
        if obj.imagen:
            request = self.context.get('request')
            url = obj.imagen.url  # normalmente ya es absoluto con Cloudinary
            # si quieres forzar absolute use request.build_absolute_uri(url) cuando sea necesario
            return url
        return None
    
    def to_representation(self, instance):
        # Esto es para mostrar detalles de la categoría en las respuestas GET
        representation = super().to_representation(instance)
        representation['categoria'] = {
            'id': instance.categoria.id,
            'nombre': instance.categoria.nombre
        }
        return representation
    
class OrderDetailSerializer(serializers.ModelSerializer):
    # Para mostrar detalles del producto en GET
    producto_detalle = ProductSerializer(source='producto', read_only=True)
    # Para aceptar IDs de producto en POST/PUT
    producto = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), 
        write_only=True
    )

    class Meta:
        model = OrderDetail
        fields = ['id', 'pedido', 'producto', 'producto_detalle', 'cantidad', 'subtotal']
        read_only_fields = ['subtotal']

class OrderSerializer(serializers.ModelSerializer):
    usuario_detalle = UserSerializer(source='usuario', read_only=True)
    
    usuario = serializers.SlugRelatedField(
        queryset=User.objects.all(),
        slug_field='username',
        required=False,
        allow_null=True,
        write_only=True,
        help_text="Nombre de usuario del cliente que realiza el pedido. Opcional para compras de invitados."
    )
    
    # CAMBIO: Declaración directa del serializador de detalles.
    # Es más limpio y estándar que usar SerializerMethodField.
    detalles = OrderDetailSerializer(many=True, read_only=True)

    detalles_input = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="Lista de productos a incluir en el pedido"
    )

    class Meta:
        model = Order
        fields = ['id', 'usuario', 'usuario_detalle', 'fecha', 'estado', 'total', 'detalles', 'detalles_input', 
                  'direccion_envio', 'costo_envio', 'codigo_postal', 'zona_envio', 'metodo_pago']
        read_only_fields = ['id', 'fecha', 'total']
        extra_kwargs = {
            'estado': {'default': 'pendiente', 'help_text': "Estado del pedido (default: pendiente)"}
        }
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        # Verificar si es una solicitud para edición
        request = self.context.get('request')
        if request and request.method in ['PUT']:
            # Formato simplificado para edición
            
            # Simplificar usuario_detalle a solo username
            if 'usuario_detalle' in representation:
                username = instance.usuario.username
                representation['usuario_detalle'] = {'username': username}
            
            # Eliminar campos que no se necesitan para edición
            if 'fecha' in representation:
                del representation['fecha']
            
            if 'total' in representation:
                del representation['total']
                
            # Simplificar detalles para edición
            if 'detalles' in representation:
                simplified_details = []
                for detalle in representation['detalles']:
                    simplified_details.append({
                        'id': detalle['id'],
                        'producto': detalle['producto_detalle']['id'],
                        'cantidad': detalle['cantidad']
                    })
                representation['detalles'] = simplified_details
        return representation
    
    def create(self, validated_data):
        """
        Crea una orden con sus detalles.
        Maneja el campo write_only 'detalles_input' para crear los OrderDetail.
        """
        # Extraer detalles_input antes de crear la orden
        detalles_data = validated_data.pop('detalles_input', [])
        
        print(f"📦 Creando orden con validated_data: {validated_data}")
        print(f"📦 Detalles a crear: {detalles_data}")
        
        # Crear la orden
        order = Order.objects.create(**validated_data)
        print(f"✅ Orden creada: #{order.id}")
        
        # Crear los detalles si existen
        for detalle_data in detalles_data:
            watch_id = detalle_data.get('watch_id')
            cantidad = detalle_data.get('cantidad', 1)
            
            print(f"🔍 Buscando producto ID: {watch_id}, cantidad: {cantidad}")
            
            # Buscar el producto
            try:
                producto = Product.objects.get(id=watch_id)
                print(f"✅ Producto encontrado: {producto.nombre}")
            except Product.DoesNotExist:
                # Si el producto no existe, eliminar la orden y lanzar error
                print(f"❌ Producto con ID {watch_id} no encontrado")
                order.delete()
                raise ValidationError(f'Producto con ID {watch_id} no encontrado')
            
            # Crear el detalle
            detalle = OrderDetail.objects.create(
                pedido=order,
                producto=producto,
                cantidad=cantidad,
                subtotal=producto.precio * cantidad
            )
            print(f"✅ Detalle creado: {detalle.id}")
            
            # Actualizar stock vendido
            producto.stock_vendido += cantidad
            producto.save()
            print(f"📊 Stock vendido actualizado: {producto.stock_vendido}")
        
        # Actualizar total de la orden
        order.total_update()
        print(f"💰 Total de la orden: {order.total}")
        
        return order

class PaySerializer(serializers.ModelSerializer):
    pedido_detalle = serializers.SerializerMethodField(read_only=True)
    monto_pagado = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    creado = serializers.DateTimeField(read_only=True)
    actualizado = serializers.DateTimeField(read_only=True)
    metadata = serializers.DictField(required=False, default=dict)
    external_id = serializers.CharField(required=False, allow_blank=True, default='')
    external_redirect_url = serializers.URLField(required=False, allow_blank=True, default='')
    comprobante_url = serializers.URLField(required=False, allow_blank=True, default='')
    comprobante_archivo = serializers.FileField(required=False, allow_null=True, write_only=True)
    comprobante_archivo_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Pay
        fields = ['id', 'pedido', 'metodo', 'estado', 'monto_pagado', 'creado', 'actualizado',
                  'metadata', 'external_id', 'external_redirect_url', 'comprobante_url', 'comprobante_archivo', 'comprobante_archivo_url', 'pedido_detalle']
        read_only_fields = ['id', 'monto_pagado', 'creado', 'actualizado', 'comprobante_archivo_url']
        extra_kwargs = {
            'metodo': {'required': True},
            'estado': {'default': 'pendiente'}
        }

    def validate(self, attrs):
        pedido = attrs.get('pedido')
        metodo = attrs.get('metodo') or getattr(self.instance, 'metodo', None)
        metadata = attrs.get('metadata') or {}
        # Si metadata viene como string (multipart), parsear JSON
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                raise ValidationError('metadata debe ser un JSON válido')
            attrs['metadata'] = metadata
        # Validación por método
        if metodo == 'tarjeta':
            forbidden = {'number', 'card_number', 'cvv', 'cvc', 'exp', 'exp_month', 'exp_year'}
            if any(k in metadata for k in forbidden):
                raise ValidationError('No se permiten datos sensibles de tarjeta en metadata.')
        if pedido:
            # No permitir nuevo pago si ya está pagado
            if pedido.estado == 'pagado':
                raise ValidationError('El pedido ya está pagado.')
            # No permitir más de un pago abierto simultáneo (pendiente o en revisión)
            if pedido.pagos.filter(estado__in=['pendiente','en_revision']).exists():
                raise ValidationError('Ya existe un pago abierto para este pedido.')
        return attrs

    def get_pedido_detalle(self, obj):
        return {
            'id': obj.pedido.id,
            'total': float(obj.pedido.total),
            'estado': obj.pedido.estado,
            'fecha': obj.pedido.fecha
        }

    def create(self, validated_data):
        pedido = validated_data.get('pedido')
        if pedido and not validated_data.get('monto_pagado'):
            validated_data['monto_pagado'] = pedido.total
        # Si viene comprobante (archivo o URL), pasar a 'en_revision'
        if validated_data.get('comprobante_archivo') or validated_data.get('comprobante_url'):
            validated_data['estado'] = 'en_revision'
        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)

    def get_comprobante_archivo_url(self, obj):
        try:
            if obj.comprobante_archivo and hasattr(obj.comprobante_archivo, 'url'):
                return obj.comprobante_archivo.url
        except Exception:
            return ''
        return ''

class ShipmentSerializer(serializers.ModelSerializer):
    # Para mostrar detalles del pedido en respuestas GET
    pedido_detalle = serializers.SerializerMethodField(read_only=True)
    # Para aceptar IDs de pedido en POST/PUT
    pedido = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(),
        required=True
    )
    fecha_envio_formateada = serializers.DateTimeField(source='fecha_envio', format='%d/%m/%Y %H:%M', read_only=True)
    fecha_entrega_estimada_formateada = serializers.DateTimeField(source='fecha_entrega_estimada', format='%d/%m/%Y', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

    class Meta:
        model = Shipment
        fields = [
            'id', 'pedido', 'pedido_detalle', 'direccion_envio', 
            'empresa_envio', 'numero_guia', 'fecha_envio', 'fecha_envio_formateada',
            'fecha_entrega_estimada', 'fecha_entrega_estimada_formateada',
            'estado', 'estado_display'
        ]
        read_only_fields = ['fecha_envio']
    
    def get_pedido_detalle(self, obj):
        """Muestra información resumida del pedido asociado al envío"""
        pedido = obj.pedido
        return {
            'id': pedido.id,
            'cliente': pedido.usuario.username,
            'total': float(pedido.total),
            'estado': pedido.estado,
            'fecha': pedido.fecha,
            'productos': [
                {
                    'nombre': detalle.producto.nombre,
                    'cantidad': detalle.cantidad
                } for detalle in pedido.detalles.all()[:5]  # Limitar a 5 productos para evitar respuestas muy grandes
            ],
            'total_productos': pedido.detalles.count()
        }
    
    def validate(self, data):
        """Validaciones personalizadas para el envío"""
        # Verificar que el pedido esté en un estado válido para crear un envío
        if 'pedido' in data:
            pedido = data['pedido']
            if pedido.estado not in ['pendiente', 'preparando', 'en camino', 'entregado']:
                raise serializers.ValidationError(
                    f"No se puede crear un envío para un pedido en estado '{pedido.estado}'. "
                    f"El pedido debe estar en un estado válido para el envío."
                )
        
        return data
    
    def create(self, validated_data):
        pedido = validated_data['pedido']
        if pedido.estado == 'pendiente':
            pedido.estado = 'procesando'
            pedido.save()
        return super().create(validated_data)

class CartItemSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_descripcion = serializers.CharField(source='producto.descripcion', read_only=True)
    categoria_nombre = serializers.CharField(source='producto.categoria.nombre', read_only=True)
    precio_unitario = serializers.DecimalField(source='producto.precio', max_digits=10, decimal_places=2, read_only=True)
    subtotal = serializers.SerializerMethodField()
    
    class Meta:
        model = CartItem
        fields = ['id', 'producto', 'producto_nombre', 'producto_descripcion', 'categoria_nombre', 'cantidad', 'precio_unitario', 'subtotal']
        read_only_fields = ['id', 'producto_nombre', 'producto_descripcion', 'categoria_nombre', 'precio_unitario', 'subtotal']
    
    def get_subtotal(self, obj):
        return float(obj.subtotal())

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    cantidad_items = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Cart
        fields = ['id', 'usuario', 'items', 'total', 'cantidad_items', 'fecha_actualizacion']
        read_only_fields = ['id', 'usuario', 'fecha_actualizacion']
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['total'] = float(instance.total())
        representation['cantidad_items'] = instance.cantidad_items()
        return representation

class ProductBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ('id', 'nombre', 'precio')  # ajusta a tus campos reales (name, price, etc.)

class FavoriteSerializer(serializers.ModelSerializer):
    product = ProductBriefSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )

    class Meta:
        model = Favorite
        fields = ('id', 'product', 'product_id', 'created_at')
        read_only_fields = ('id', 'created_at')
