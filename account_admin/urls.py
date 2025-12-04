from django.urls import path, include 
from rest_framework import routers
from .views import *
from .views_guest import register_with_order
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

router = routers.DefaultRouter()

urlpatterns = [
    path('accounts_admin/model/', include(router.urls)),
    path('create-user/', CreateUserView.as_view(), name='create-user'),
    path('change-role/<int:user_id>/', ChangeRoleView.as_view(), name='change-role'),
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('profile/', user_profile, name='user_profile'),
    path('change-password/', change_password, name='change_password'),
    path('users/', list_users, name='list_users'),  # GET - Listar usuarios
    path('users/<int:user_id>/', manage_user, name='manage_user'),  # GET, PUT, DELETE - Gestionar usuario específico
    path('register-with-order/', register_with_order, name='register_with_order'),  # POST - Registrar después de compra
]