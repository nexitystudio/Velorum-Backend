from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from account_admin.models import User
from account_admin.views import CreateUserView, ChangeRoleView, LoginView, LogoutView
from faker import Faker

fake = Faker()

class CreateUserViewTest(APITestCase):
    
    def setUp(self):
        """Configuración inicial para los tests"""
        self.client = APIClient()
        
        # Crear usuarios de diferentes roles
        self.admin_user = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='adminpass123',
            role='admin'
        )
        
        self.operator_user = User.objects.create_user(
            username='operator_test',
            email='operator@test.com',
            password='operatorpass123',
            role='operator'
        )
        
        self.client_user = User.objects.create_user(
            username='client_test',
            email='client@test.com',
            password='clientpass123',
            role='client'
        )
        
        self.user_data = {
            'username': fake.unique.user_name(),
            'email': fake.unique.email(),
            'password': 'newuserpass123',
            'name': fake.name(),
            'role': 'client'
        }
        
    def test_create_user_admin_success(self):
        """Test que verifica que un admin puede crear usuarios con cualquier rol"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Admin puede crear usuario con rol admin
        admin_data = self.user_data.copy()
        admin_data['role'] = 'admin'
        admin_data['username'] = fake.unique.user_name()
        admin_data['email'] = fake.unique.email()
        
        url = reverse('create-user')
        response = self.client.post(url, admin_data, format='json')  # Agregar format='json'
        
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['role'], 'admin')
        
        # Verificar que el usuario se creó en la base de datos
        new_user = User.objects.get(username=admin_data['username'])
        self.assertEqual(new_user.role, 'admin')
        
    def test_create_user_operator_success(self):
        """Test que verifica que un operador puede crear usuarios pero solo clientes"""
        self.client.force_authenticate(user=self.operator_user)
        
        # Operator intenta crear admin pero se fuerza a client
        operator_data = self.user_data.copy()
        operator_data['role'] = 'admin'  # Intenta crear admin
        operator_data['username'] = fake.unique.user_name()
        operator_data['email'] = fake.unique.email()
        
        url = reverse('create-user')
        response = self.client.post(url, operator_data, format='json')  # Agregar format='json'
        
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['role'], 'client')  # Forzado a client
        
        # Verificar en la base de datos
        new_user = User.objects.get(username=operator_data['username'])
        self.assertEqual(new_user.role, 'client')
        
    def test_create_user_client_forbidden(self):
        """Test que verifica que un cliente no puede crear usuarios"""
        self.client.force_authenticate(user=self.client_user)
        
        url = reverse('create-user')
        response = self.client.post(url, self.user_data, format='json')
        
        self.assertEqual(response.status_code, 403)
        self.assertIn('No tienes permiso para crear usuarios', str(response.data))
        
    def test_create_user_unauthenticated(self):
        """Test que verifica que usuarios no autenticados no pueden crear usuarios"""
        url = reverse('create-user')
        response = self.client.post(url, self.user_data, format='json')
        
        self.assertEqual(response.status_code, 403)  # Cambiar de 401 a 403
        
    def test_create_user_invalid_data(self):
        """Test que verifica validación de datos inválidos"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Datos inválidos (sin username)
        invalid_data = {
            'email': fake.email(),
            'password': 'testpass123'
            # Falta username
        }
        
        url = reverse('create-user')
        response = self.client.post(url, invalid_data, format='json')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('username', str(response.data))
        
    def test_create_user_duplicate_username(self):
        """Test que verifica validación de username duplicado"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Intentar crear usuario con username que ya existe
        duplicate_data = self.user_data.copy()
        duplicate_data['username'] = self.admin_user.username  # Username duplicado
        
        url = reverse('create-user')
        response = self.client.post(url, duplicate_data, format='json')
        
        self.assertEqual(response.status_code, 400)

class ChangeRoleViewTest(APITestCase):
    
    def setUp(self):
        """Configuración inicial para los tests"""
        self.client = APIClient()
        
        self.admin_user = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='adminpass123',
            role='admin'
        )
        
        self.target_user = User.objects.create_user(
            username='target_user',
            email='target@test.com',
            password='targetpass123',
            role='client'
        )
        
        self.operator_user = User.objects.create_user(
            username='operator_test',
            email='operator@test.com',
            password='operatorpass123',
            role='operator'
        )
        
    def test_change_role_admin_success(self):
        """Test que verifica que un admin puede cambiar roles"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('change-role', kwargs={'user_id': self.target_user.id})
        data = {'role': 'admin'}
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('Rol actualizado correctamente', str(response.data))
        
        # Verificar que el rol se actualizó en la base de datos
        self.target_user.refresh_from_db()
        self.assertEqual(self.target_user.role, 'admin')
        
    def test_change_role_invalid_role(self):
        """Test que verifica validación de rol inválido"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('change-role', kwargs={'user_id': self.target_user.id})
        data = {'role': 'invalid_role'}
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('Rol inválido', str(response.data))
        
        # Verificar que el rol NO cambió
        self.target_user.refresh_from_db()
        self.assertEqual(self.target_user.role, 'client')  # Sigue siendo client
        
    def test_change_role_user_not_found(self):
        """Test que verifica error cuando el usuario no existe"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('change-role', kwargs={'user_id': 99999})  # ID inexistente
        data = {'role': 'admin'}
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, 404)
        self.assertIn('Usuario no encontrado', str(response.data))
        
    def test_change_role_non_admin_forbidden(self):
        """Test que verifica que no-admins no pueden cambiar roles"""
        self.client.force_authenticate(user=self.operator_user)
        
        url = reverse('change-role', kwargs={'user_id': self.target_user.id})
        data = {'role': 'admin'}
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, 403)
        
    def test_change_role_unauthenticated(self):
        """Test que verifica que usuarios no autenticados no pueden cambiar roles"""
        url = reverse('change-role', kwargs={'user_id': self.target_user.id})
        data = {'role': 'admin'}
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, 403)  # Cambiar de 401 a 403
        
    def test_change_role_all_valid_roles(self):
        """Test que verifica que se pueden asignar todos los roles válidos"""
        self.client.force_authenticate(user=self.admin_user)
        
        valid_roles = ['admin', 'operator', 'client']
        
        for role in valid_roles:
            with self.subTest(role=role):
                url = reverse('change-role', kwargs={'user_id': self.target_user.id})
                data = {'role': role}
                response = self.client.put(url, data, format='json')
                
                self.assertEqual(response.status_code, 200)
                
                # Verificar que el rol se actualizó
                self.target_user.refresh_from_db()
                self.assertEqual(self.target_user.role, role)

class LoginViewTest(APITestCase):
    
    def setUp(self):
        """Configuración inicial para los tests"""
        self.client = APIClient()
        
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            role='client'
        )
        
    def test_login_success(self):
        """Test que verifica login exitoso"""
        url = reverse('login')
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('Login exitoso', str(response.data))
        self.assertEqual(response.data['username'], 'testuser')
        self.assertEqual(response.data['role'], 'client')
        
    def test_login_invalid_credentials(self):
        """Test que verifica login con credenciales inválidas"""
        url = reverse('login')
        data = {
            'username': 'testuser',
            'password': 'wrongpassword'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('Credenciales inválidas', str(response.data))
        
    def test_login_user_does_not_exist(self):
        """Test que verifica login con usuario inexistente"""
        url = reverse('login')
        data = {
            'username': 'nonexistentuser',
            'password': 'testpass123'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('Credenciales inválidas', str(response.data))
        
    def test_login_missing_username(self):
        """Test que verifica login sin username"""
        url = reverse('login')
        data = {
            'password': 'testpass123'
            # Falta username
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('Credenciales inválidas', str(response.data))
        
    def test_login_missing_password(self):
        """Test que verifica login sin password"""
        url = reverse('login')
        data = {
            'username': 'testuser'
            # Falta password
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('Credenciales inválidas', str(response.data))
        
    def test_login_empty_credentials(self):
        """Test que verifica login con credenciales vacías"""
        url = reverse('login')
        data = {
            'username': '',
            'password': ''
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('Credenciales inválidas', str(response.data))

class LogoutViewTest(APITestCase):
    
    def setUp(self):
        """Configuración inicial para los tests"""
        self.client = APIClient()
        
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            role='client'
        )
        
    def test_logout_success(self):
        """Test que verifica logout exitoso"""
        self.client.force_authenticate(user=self.test_user)
        
        url = reverse('logout')
        response = self.client.post(url, format='json')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('Logout exitoso', str(response.data))
        
    def test_logout_unauthenticated(self):
        """Test que verifica que usuarios no autenticados no pueden hacer logout"""
        url = reverse('logout')
        response = self.client.post(url, format='json')
        
        self.assertEqual(response.status_code, 403)  # Cambiar de 401 a 403

class ViewsIntegrationTest(APITestCase):
    """Tests de integración para verificar el flujo completo"""
    
    def setUp(self):
        """Configuración inicial para los tests"""
        self.client = APIClient()
        
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='adminpass123',
            role='admin'
        )
        
    def test_complete_user_lifecycle(self):
        """Test que verifica el ciclo completo: login -> crear usuario -> cambiar rol -> logout"""
        # 1. Login como admin
        login_url = reverse('login')
        login_data = {
            'username': 'admin',
            'password': 'adminpass123'
        }
        login_response = self.client.post(login_url, login_data, format='json')
        self.assertEqual(login_response.status_code, 200)
        
        # 2. Autenticar para siguientes requests
        self.client.force_authenticate(user=self.admin_user)
        
        # 3. Crear nuevo usuario
        create_url = reverse('create-user')
        create_data = {
            'username': 'newuser',
            'email': 'new@test.com',
            'password': 'newpass123',
            'role': 'client'
        }
        create_response = self.client.post(create_url, create_data, format='json')
        self.assertEqual(create_response.status_code, 201)
        
        # 4. Obtener el usuario creado
        new_user = User.objects.get(username='newuser')
        
        # 5. Cambiar rol del usuario
        change_role_url = reverse('change-role', kwargs={'user_id': new_user.id})
        change_role_data = {'role': 'operator'}
        change_role_response = self.client.put(change_role_url, change_role_data, format='json')
        self.assertEqual(change_role_response.status_code, 200)
        
        # 6. Verificar que el rol cambió
        new_user.refresh_from_db()
        self.assertEqual(new_user.role, 'operator')
        
        # 7. Logout
        logout_url = reverse('logout')
        logout_response = self.client.post(logout_url, format='json')
        self.assertEqual(logout_response.status_code, 200)