from rest_framework import permissions

class IsAdmin(permissions.BasePermission):
    """
    Permite acceso solo a usuarios con rol de administrador.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'admin'

class IsOperator(permissions.BasePermission):
    """
    Permite acceso solo a usuarios con rol de operador.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'operator'

class IsClient(permissions.BasePermission):
    """
    Permite acceso solo a usuarios con rol de cliente.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'client'

class IsAdminOrOperator(permissions.BasePermission):
    """
    Permite acceso a usuarios con rol de administrador u operador.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role in ['admin', 'operator']

class IsOwnerOrStaff(permissions.BasePermission):
    """
    Permite a un usuario ver/modificar solo sus propios recursos,
    mientras que admin y operadores pueden acceder a todos.
    """
    def has_object_permission(self, request, view, obj):
        # Admin y operadores pueden acceder a cualquier objeto
        if request.user.role in ['admin', 'operator']:
            return True
        
        # Clientes solo pueden acceder a sus propios objetos
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        return False

class AdminFullAccess(permissions.BasePermission):
    """
    Admin tiene acceso completo, otros solo pueden leer.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        if request.method in permissions.SAFE_METHODS:
            return True
            
        return request.user.role == 'admin'

class AdminOperatorFullClientReadOnly(permissions.BasePermission):
    """
    Admin y operadores tienen acceso completo, clientes solo lectura.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        if request.method in permissions.SAFE_METHODS:
            return True
            
        return request.user.role in ['admin', 'operator']

class ClientOrderPermission(permissions.BasePermission):
    """
    Clientes pueden crear órdenes y ver las suyas.
    Admin y operadores tienen acceso completo a todas las órdenes.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        # Admin y operadores tienen acceso completo
        if request.user.role in ['admin', 'operator']:
            return True
            
        # Clientes pueden crear órdenes y ver (método seguro)
        if request.user.role == 'client':
            if request.method == 'POST' or request.method in permissions.SAFE_METHODS:
                return True
                
        return False
        
    def has_object_permission(self, request, view, obj):
        # Admin y operadores pueden acceder a todas las órdenes
        if request.user.role in ['admin', 'operator']:
            return True
            
        # Clientes solo pueden ver sus propias órdenes
        if hasattr(obj, 'user'):
            return obj.user == request.user
            
        return False

# Nuevos permisos para cubrir necesidades específicas

class CategoryPermission(permissions.BasePermission):
    """
    Admin y operadores tienen acceso completo a categorías.
    Clientes solo pueden ver categorías.
    """
    def has_permission(self, request, view):
        # Permitir acceso público a métodos seguros (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Para modificaciones, requerir autenticación y rol adecuado
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ['admin', 'operator']

class ProductPermission(permissions.BasePermission):
    """
    Admin y operadores tienen acceso completo a productos.
    Clientes solo pueden ver productos.
    """
    def has_permission(self, request, view):
        # Permitir acceso público a métodos seguros (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Para modificaciones, requerir autenticación y rol adecuado
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ['admin', 'operator']
    
class OrderPermission(permissions.BasePermission):
    """
    Permisos para órdenes:
    - Admin/operadores: acceso completo a todas las órdenes
    - Clientes: acceso solo a sus propias órdenes, crear nuevas
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
            
        # Admin/operadores tienen acceso completo
        if request.user.role in ['admin', 'operator']:
            return True
            
        # Clientes solo pueden crear órdenes y usar métodos seguros
        if request.user.role == 'client':
            if request.method == 'POST' or request.method in permissions.SAFE_METHODS:
                return True
                
        return False
        
    def has_object_permission(self, request, view, obj):
        # Admin/operadores tienen acceso completo a nivel de objeto
        if request.user.role in ['admin', 'operator']:
            return True
            
        # Clientes solo pueden acceder a sus propias órdenes
        return obj.usuario == request.user
    
class AddToCartPermission(permissions.BasePermission):
    """
    Permiso específico para la acción add_to_cart.
    Permite a clientes añadir productos a sus carritos.
    """
    def has_permission(self, request, view):
        # Verificar que el usuario esté autenticado
        if not request.user or not request.user.is_authenticated:
            return False
            
        # Todos los usuarios autenticados pueden añadir productos al carrito
        return True
    
class CancelOrderPermission(permissions.BasePermission):
    """
    Permite a los clientes cancelar sus propias órdenes.
    Admin y operadores pueden cancelar cualquier orden.
    """
    def has_permission(self, request, view):
        # Verificar que el usuario esté autenticado
        return request.user and request.user.is_authenticated
        
    def has_object_permission(self, request, view, obj):
        # Admin y operadores pueden cancelar cualquier orden
        if request.user.role in ['admin', 'operator']:
            return True
        # Cliente solo puede cancelar sus propias órdenes
        return obj.usuario == request.user

class OrderDetailPermission(permissions.BasePermission):
    """
    Admin y operadores tienen acceso completo a detalles de órdenes.
    Clientes pueden ver detalles solo de sus propias órdenes.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        # Admin y operadores tienen acceso completo
        if request.user.role in ['admin', 'operator']:
            return True
            
        # Clientes solo pueden leer
        if request.user.role == 'client' and request.method in permissions.SAFE_METHODS:
            return True
                
        return False
        
    def has_object_permission(self, request, view, obj):
        # Admin y operadores pueden acceder a todos los detalles
        if request.user.role in ['admin', 'operator']:
            return True
            
        # Clientes solo pueden ver detalles de sus propias órdenes
        if hasattr(obj, 'order') and hasattr(obj.order, 'user'):
            return obj.order.user == request.user
        
        return False

class PaymentPermission(permissions.BasePermission):
    """
    Permisos para pagos:
    - Admin/operadores: acceso completo a todos los pagos
    - Clientes: acceso solo a pagos de sus propias órdenes
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
            
        # Admin/operadores tienen acceso completo
        if request.user.role in ['admin', 'operator']:
            return True
            
        # Clientes solo pueden crear pagos y usar métodos seguros
        if request.user.role == 'client':
            if request.method == 'POST' or request.method in permissions.SAFE_METHODS:
                return True
                
        return False
        
    def has_object_permission(self, request, view, obj):
        # Admin/operadores tienen acceso completo a nivel de objeto
        if request.user.role in ['admin', 'operator']:
            return True
            
        # Clientes solo pueden acceder a pagos de sus propias órdenes
        return obj.pedido.usuario == request.user

class ShipmentPermission(permissions.BasePermission):
    """
    Admin y operadores tienen acceso completo a envíos.
    Clientes solo pueden ver sus propios envíos.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        # Admin y operadores tienen acceso completo
        if request.user.role in ['admin', 'operator']:
            return True
            
        # Clientes solo pueden ver envíos
        if request.user.role == 'client' and request.method in permissions.SAFE_METHODS:
            return True
                
        return False
        
    def has_object_permission(self, request, view, obj):
        # Admin y operadores pueden acceder a todos los envíos
        if request.user.role in ['admin', 'operator']:
            return True
            
        # Clientes solo pueden ver sus propios envíos
        if hasattr(obj, 'order') and hasattr(obj.order, 'user'):
            return obj.order.user == request.user
        
        return False

class TrackingPermission(permissions.BasePermission):
    """
    Permiso que permite a cualquier usuario autenticado ver información
    de tracking, pero solo de sus propios envíos.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
        
    def has_object_permission(self, request, view, obj):
        # Admin y operadores pueden ver tracking de cualquier envío
        if request.user.role in ['admin', 'operator']:
            return True
        
        # Clientes solo pueden ver tracking de sus propios envíos
        return obj.pedido.usuario == request.user

class UserAccountPermission(permissions.BasePermission):
    """
    Admin puede gestionar todas las cuentas de usuario.
    Operadores pueden crear clientes y gestionar sus propios datos.
    Clientes solo pueden ver y modificar sus propios datos.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        # Admin tiene acceso completo
        if request.user.role == 'admin':
            return True
            
        # Operadores pueden crear nuevos usuarios (clientes)
        if request.user.role == 'operator' and request.method == 'POST':
            return True
            
        # Para otros métodos, depende del objeto (has_object_permission)
        if request.method in permissions.SAFE_METHODS:
            return True
            
        return False
        
    def has_object_permission(self, request, view, obj):
        # Admin tiene acceso completo a todas las cuentas
        if request.user.role == 'admin':
            return True
            
        # Usuarios solo pueden modificar sus propias cuentas
        return obj.id == request.user.id