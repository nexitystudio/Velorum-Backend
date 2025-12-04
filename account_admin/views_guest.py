from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from .models import User
from .serializer import UserSerializer
from market.models import Order


@api_view(['POST'])
def register_with_order(request):
    """
    Registra un usuario después de realizar una compra como invitado
    y asocia la orden a ese usuario.
    
    POST /api/register-with-order/
    Body: {
        "email": "user@example.com",
        "username": "username",  # opcional, si no se usa email como username
        "password": "password123",
        "first_name": "Nombre",
        "last_name": "Apellido",
        "order_id": 123  # ID de la orden a asociar
    }
    
    Returns:
        {
            "success": true,
            "user": {...},
            "access": "token...",
            "refresh": "token...",
            "order_associated": true
        }
    """
    try:
        email = request.data.get('email')
        password = request.data.get('password')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')
        order_id = request.data.get('order_id')
        
        # Validaciones
        if not email or not password:
            return Response({
                'success': False,
                'error': 'Email y contraseña son requeridos'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verificar que el email no exista
        if User.objects.filter(email=email).exists():
            return Response({
                'success': False,
                'error': 'Ya existe un usuario con este email'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Usar email como username si no se provee
        username = request.data.get('username', email.split('@')[0])
        
        # Verificar username único
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        with transaction.atomic():
            # Crear usuario
            user_data = {
                'username': username,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'role': 'client'
            }
            
            serializer = UserSerializer(data=user_data)
            if not serializer.is_valid():
                return Response({
                    'success': False,
                    'error': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user = serializer.save()
            user.set_password(password)
            user.save()
            
            # Asociar orden si se provee order_id
            order_associated = False
            if order_id:
                try:
                    order = Order.objects.get(id=order_id, usuario__isnull=True)
                    order.usuario = user
                    order.save()
                    order_associated = True
                except Order.DoesNotExist:
                    # La orden no existe o ya tiene usuario asignado
                    pass
            
            # Generar tokens JWT
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'success': True,
                'user': UserSerializer(user).data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'order_associated': order_associated
            }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
