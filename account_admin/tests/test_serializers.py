from django.test import TestCase
from rest_framework.test import APIRequestFactory
from account_admin.serializer import UserSerializer
from account_admin.models import User
from faker import Faker

fake = Faker()

class UserSerializerTest(TestCase):
    
    def setUp(self):
        """Configuración inicial para los tests"""
        self.factory = APIRequestFactory()
        self.user_data = {
            'username': fake.unique.user_name(),
            'email': fake.unique.email(),
            'password': 'testpass123',
            'name': fake.name(),
            'address': fake.address(),
            'phone': fake.phone_number()[:15],
            'role': 'client'
        }
        
    def test_user_serializer_valid_data(self):
        """Test que verifica la serialización con datos válidos"""
        serializer = UserSerializer(data=self.user_data)
        self.assertTrue(serializer.is_valid())
        
    def test_user_serializer_create_user(self):
        """Test que verifica la creación de usuario a través del serializer"""
        serializer = UserSerializer(data=self.user_data)
        self.assertTrue(serializer.is_valid())
        
        user = serializer.save()
        
        # Verificar que el usuario se creó correctamente
        self.assertEqual(user.username, self.user_data['username'])
        self.assertEqual(user.email, self.user_data['email'])
        self.assertEqual(user.name, self.user_data['name'])
        self.assertEqual(user.address, self.user_data['address'])
        self.assertEqual(user.phone, self.user_data['phone'])
        self.assertEqual(user.role, self.user_data['role'])
        
    def test_user_serializer_update_user(self):
        """Test que verifica la actualización de usuario a través del serializer"""
        # Crear usuario inicial
        user = User.objects.create_user(
            username=self.user_data['username'],
            email=self.user_data['email'],
            password=self.user_data['password']
        )
        
        # Datos para actualizar
        update_data = {
            'name': 'Nuevo Nombre',
            'address': 'Nueva Dirección',
            'phone': '123456789',
            'role': 'admin'
        }
        
        serializer = UserSerializer(user, data=update_data, partial=True)
        self.assertTrue(serializer.is_valid())
        
        updated_user = serializer.save()
        
        # Verificar que se actualizó correctamente
        self.assertEqual(updated_user.name, 'Nuevo Nombre')
        self.assertEqual(updated_user.address, 'Nueva Dirección')
        self.assertEqual(updated_user.phone, '123456789')
        self.assertEqual(updated_user.role, 'admin')
        
    def test_user_serializer_serialize_existing_user(self):
        """Test que verifica la serialización de un usuario existente"""
        user = User.objects.create_user(
            username=self.user_data['username'],
            email=self.user_data['email'],
            password=self.user_data['password'],
            name=self.user_data['name'],
            address=self.user_data['address'],
            phone=self.user_data['phone'],
            role=self.user_data['role']
        )
        
        serializer = UserSerializer(user)
        data = serializer.data
        
        # Verificar que todos los campos están presentes
        self.assertEqual(data['username'], user.username)
        self.assertEqual(data['email'], user.email)
        self.assertEqual(data['name'], user.name)
        self.assertEqual(data['address'], user.address)
        self.assertEqual(data['phone'], user.phone)
        self.assertEqual(data['role'], user.role)
        self.assertIn('id', data)
        self.assertIn('register_date', data)
        
    def test_user_serializer_required_fields(self):
        """Test que verifica los campos requeridos"""
        # Solo username y password son requeridos por defecto en AbstractUser
        minimal_data = {
            'username': fake.unique.user_name(),
            'password': 'testpass123'
        }
        
        serializer = UserSerializer(data=minimal_data)
        self.assertTrue(serializer.is_valid())
        
    def test_user_serializer_invalid_role(self):
        """Test que verifica validación de rol inválido"""
        invalid_data = self.user_data.copy()
        invalid_data['role'] = 'invalid_role'
        
        serializer = UserSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('role', serializer.errors)
        
    def test_user_serializer_duplicate_username(self):
        """Test que verifica validación de username duplicado"""
        # Crear primer usuario
        User.objects.create_user(
            username='duplicate_user',
            email='first@test.com',
            password='testpass123'
        )
        
        # Intentar crear segundo usuario con mismo username
        duplicate_data = {
            'username': 'duplicate_user',
            'email': 'second@test.com',
            'password': 'testpass123'
        }
        
        serializer = UserSerializer(data=duplicate_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('username', serializer.errors)
        
    def test_user_serializer_invalid_email(self):
        """Test que verifica validación de email inválido"""
        invalid_data = self.user_data.copy()
        invalid_data['email'] = 'invalid_email'
        
        serializer = UserSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)
        
    def test_user_serializer_max_length_fields(self):
        """Test que verifica validación de longitud máxima de campos"""
        # Test para name (max_length=100)
        long_name_data = self.user_data.copy()
        long_name_data['name'] = 'A' * 101  # Excede el límite
        
        serializer = UserSerializer(data=long_name_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)
        
        # Test para phone (max_length=15)
        long_phone_data = self.user_data.copy()
        long_phone_data['phone'] = '1' * 16  # Excede el límite
        
        serializer = UserSerializer(data=long_phone_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('phone', serializer.errors)
        
        # Test para role (max_length=20)
        long_role_data = self.user_data.copy()
        long_role_data['role'] = 'A' * 21  # Excede el límite
        
        serializer = UserSerializer(data=long_role_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('role', serializer.errors)
        
    def test_user_serializer_default_values(self):
        """Test que verifica los valores por defecto en la serialización"""
        minimal_data = {
            'username': fake.unique.user_name(),
            'password': 'testpass123'
        }
        
        serializer = UserSerializer(data=minimal_data)
        self.assertTrue(serializer.is_valid())
        
        user = serializer.save()
        
        # Verificar valores por defecto
        self.assertEqual(user.role, 'client')
        self.assertEqual(user.name, 'Anonimo')
        self.assertEqual(user.address, '')
        self.assertEqual(user.phone, '')
        
    def test_user_serializer_fields_included(self):
        """Test que verifica que todos los campos están incluidos en fields='__all__'"""
        user = User.objects.create_user(
            username=self.user_data['username'],
            email=self.user_data['email'],
            password=self.user_data['password']
        )
        
        serializer = UserSerializer(user)
        data = serializer.data
        
        # Verificar campos personalizados
        expected_custom_fields = ['role', 'name', 'address', 'phone', 'register_date']
        for field in expected_custom_fields:
            self.assertIn(field, data)
            
        # Verificar algunos campos heredados de AbstractUser
        expected_inherited_fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active']
        for field in expected_inherited_fields:
            self.assertIn(field, data)
            
    def test_user_serializer_partial_update(self):
        """Test que verifica actualización parcial"""
        user = User.objects.create_user(
            username=self.user_data['username'],
            email=self.user_data['email'],
            password=self.user_data['password'],
            name='Original Name'
        )
        
        # Actualizar solo el nombre
        partial_data = {'name': 'Updated Name'}
        
        serializer = UserSerializer(user, data=partial_data, partial=True)
        self.assertTrue(serializer.is_valid())
        
        updated_user = serializer.save()
        
        # Verificar que solo se actualizó el nombre
        self.assertEqual(updated_user.name, 'Updated Name')
        self.assertEqual(updated_user.username, self.user_data['username'])  # No cambió
        self.assertEqual(updated_user.email, self.user_data['email'])  # No cambió
        