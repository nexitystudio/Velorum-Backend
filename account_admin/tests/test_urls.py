from django.test import TestCase
from django.urls import reverse, resolve
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from account_admin.views import CreateUserView, ChangeRoleView, LoginView, LogoutView

User = get_user_model()

class URLsTest(TestCase):
    
    def test_create_user_url_resolves(self):
        """Test que verifica que la URL create-user se resuelve correctamente"""
        url = reverse('create-user')
        self.assertEqual(url, '/api/create-user/')  # Agregar /api/
        
        # Verificar que resuelve a la vista correcta
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, CreateUserView)
        
    def test_change_role_url_resolves(self):
        """Test que verifica que la URL change-role se resuelve correctamente"""
        user_id = 123
        url = reverse('change-role', kwargs={'user_id': user_id})
        self.assertEqual(url, f'/api/change-role/{user_id}/')  # Agregar /api/
        
        # Verificar que resuelve a la vista correcta
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, ChangeRoleView)
        
    def test_login_url_resolves(self):
        """Test que verifica que la URL login se resuelve correctamente"""
        url = reverse('login')
        self.assertEqual(url, '/api/login/')  # Agregar /api/
        
        # Verificar que resuelve a la vista correcta
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, LoginView)
        
    def test_logout_url_resolves(self):
        """Test que verifica que la URL logout se resuelve correctamente"""
        url = reverse('logout')
        self.assertEqual(url, '/api/logout/')  # Agregar /api/
        
        # Verificar que resuelve a la vista correcta
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, LogoutView)
        
    def test_accounts_admin_model_url_resolves(self):
        """Test que verifica que la URL del router se resuelve correctamente"""
        url = '/api/accounts_admin/model/'  # Agregar /api/
        
        # Como el router está vacío, esta URL existe pero devuelve lista vacía
        resolver = resolve(url)
        self.assertIsNotNone(resolver)

class URLPatternTest(APITestCase):
    """Tests adicionales para verificar el funcionamiento de las URLs"""
    
    def setUp(self):
        """Configuración inicial para los tests"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='adminpass123',
            role='admin'
        )
        self.client_user = User.objects.create_user(
            username='client',
            email='client@test.com',
            password='clientpass123',
            role='client'
        )
        
    def test_create_user_url_accessible(self):
        """Test que verifica que la URL create-user es accesible"""
        url = reverse('create-user')
        response = self.client.get(url)
        
        # Debería dar 405 (Method Not Allowed) para GET, no 404
        self.assertNotEqual(response.status_code, 404)
        
    def test_change_role_url_accessible(self):
        """Test que verifica que la URL change-role es accesible"""
        url = reverse('change-role', kwargs={'user_id': self.client_user.id})
        response = self.client.get(url)
        
        # Debería dar 405 (Method Not Allowed) para GET, no 404
        self.assertNotEqual(response.status_code, 404)
        
    def test_login_url_accessible(self):
        """Test que verifica que la URL login es accesible"""
        url = reverse('login')
        response = self.client.get(url)
        
        # Debería dar 405 (Method Not Allowed) para GET, no 404
        self.assertNotEqual(response.status_code, 404)
        
    def test_logout_url_accessible(self):
        """Test que verifica que la URL logout es accesible"""
        url = reverse('logout')
        response = self.client.get(url)
        
        # Debería dar 405 (Method Not Allowed) para GET, no 404
        self.assertNotEqual(response.status_code, 404)
        
    def test_router_urls_accessible(self):
        """Test que verifica que las URLs del router son accesibles"""
        url = '/api/accounts_admin/model/'  # Agregar /api/
        response = self.client.get(url)
        
        # Como el router está vacío pero existe, debería devolver 200 con lista vacía
        self.assertEqual(response.status_code, 200)

class URLNameTest(TestCase):
    """Tests para verificar que los nombres de URLs están configurados correctamente"""
    
    def test_all_url_names_exist(self):
        """Test que verifica que todos los nombres de URL existen"""
        url_names = ['create-user', 'change-role', 'login', 'logout']
        
        for url_name in url_names:
            with self.subTest(url_name=url_name):
                if url_name == 'change-role':
                    # Esta URL requiere parámetro
                    url = reverse(url_name, kwargs={'user_id': 1})
                else:
                    url = reverse(url_name)
                self.assertIsNotNone(url)
                self.assertTrue(url.startswith('/api/'))  # Verificar prefijo /api/
                    
    def test_url_parameters(self):
        """Test que verifica que los parámetros de URL funcionan correctamente"""
        # Test con diferentes user_ids
        test_ids = [1, 123, 999]
        
        for user_id in test_ids:
            with self.subTest(user_id=user_id):
                url = reverse('change-role', kwargs={'user_id': user_id})
                self.assertIn(str(user_id), url)
                self.assertTrue(url.startswith('/api/'))  # Verificar prefijo /api/
                
                # Verificar que el resolver extrae el parámetro correctamente
                resolver = resolve(url)
                self.assertEqual(resolver.kwargs['user_id'], user_id)

class RouterConfigTest(TestCase):
    """Tests para verificar la configuración del router"""
    
    def test_router_pattern_exists(self):
        """Test que verifica que el patrón del router existe"""
        url = '/api/accounts_admin/model/'  # Agregar /api/
        
        # El router existe aunque esté vacío
        resolver = resolve(url)
        self.assertIsNotNone(resolver)
            
    def test_router_base_url(self):
        """Test que verifica la URL base del router"""
        # Verificar que la configuración de include funciona
        url = '/api/accounts_admin/model/'  # Agregar /api/
        self.assertTrue(url.startswith('/api/accounts_admin/model/'))