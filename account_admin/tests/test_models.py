from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from account_admin.models import User
from faker import Faker

fake = Faker()

class UserModelTest(TestCase):
    
    def setUp(self):
        """Configuración inicial para los tests"""
        self.user_data = {
            'username': fake.unique.user_name(),
            'email': fake.unique.email(),
            'password': 'testpass123',
            'name': fake.unique.name(),
            'address': fake.address(),
            'phone': fake.phone_number()[:15],  # Limitar a 15 caracteres
        }
    
    def test_user_creation_default_values(self):
        """Test que verifica los valores por defecto al crear un usuario"""
        user = User.objects.create_user(
            username=self.user_data['username'],
            email=self.user_data['email'],
            password=self.user_data['password']
        )
        
        # Verificar valores por defecto
        self.assertEqual(user.role, 'client')  # Default role
        self.assertEqual(user.name, 'Anonimo')  # Default name
        self.assertEqual(user.address, '')  # Default empty
        self.assertEqual(user.phone, '')  # Default empty
        self.assertIsNotNone(user.register_date)  # auto_now_add=True
        
    def test_user_creation_with_all_fields(self):
        """Test que verifica la creación de usuario con todos los campos"""
        user = User.objects.create_user(
            username=self.user_data['username'],
            email=self.user_data['email'],
            password=self.user_data['password'],
            name=self.user_data['name'],
            address=self.user_data['address'],
            phone=self.user_data['phone'],
            role='admin'
        )
        
        # Verificar que todos los campos se guardaron correctamente
        self.assertEqual(user.username, self.user_data['username'])
        self.assertEqual(user.email, self.user_data['email'])
        self.assertEqual(user.name, self.user_data['name'])
        self.assertEqual(user.address, self.user_data['address'])
        self.assertEqual(user.phone, self.user_data['phone'])
        self.assertEqual(user.role, 'admin')
        self.assertTrue(user.check_password(self.user_data['password']))
        
    def test_user_role_choices(self):
        """Test que verifica todas las opciones de rol válidas"""
        valid_roles = ['admin', 'operator', 'client']
        
        for role in valid_roles:
            user = User.objects.create_user(
                username=fake.unique.user_name(),
                email=fake.unique.email(),
                password='testpass123',
                role=role
            )
            self.assertEqual(user.role, role)
            
    def test_user_str_method(self):
        """Test que verifica el método __str__ del modelo User"""
        user = User.objects.create_user(
            username=self.user_data['username'],
            email=self.user_data['email'],
            password=self.user_data['password']
        )
        
        self.assertEqual(str(user), self.user_data['username'])
            
    def test_user_username_unique_constraint(self):
        """Test que verifica que el campo username es único (heredado de AbstractUser)"""
        # Crear primer usuario
        User.objects.create_user(
            username='testuser',
            email=fake.unique.email(),
            password='testpass123'
        )
        
        # Intentar crear segundo usuario con el mismo username
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username='testuser',  # Mismo username
                email=fake.unique.email(),
                password='testpass123'
            )
            
    def test_user_phone_max_length(self):
        """Test que verifica la longitud máxima del campo phone"""
        user = User.objects.create_user(
            username=self.user_data['username'],
            email=self.user_data['email'],
            password=self.user_data['password'],
            phone='1' * 15  # Exactamente 15 caracteres
        )
        
        self.assertEqual(len(user.phone), 15)
        
    def test_user_name_max_length(self):
        """Test que verifica la longitud máxima del campo name"""
        long_name = 'A' * 100  # Exactamente 100 caracteres
        
        user = User.objects.create_user(
            username=self.user_data['username'],
            email=self.user_data['email'],
            password=self.user_data['password'],
            name=long_name
        )
        
        self.assertEqual(len(user.name), 100)
        
    def test_user_role_max_length(self):
        """Test que verifica la longitud máxima del campo role"""
        # El campo role tiene max_length=20, probamos con los valores válidos
        user = User.objects.create_user(
            username=self.user_data['username'],
            email=self.user_data['email'],
            password=self.user_data['password'],
            role='operator'  # 8 caracteres, dentro del límite
        )
        
        self.assertEqual(user.role, 'operator')
        
    def test_user_register_date_auto_now_add(self):
        """Test que verifica que register_date se asigna automáticamente"""
        from django.utils import timezone
        import datetime
        
        before_creation = timezone.now()
        
        user = User.objects.create_user(
            username=self.user_data['username'],
            email=self.user_data['email'],
            password=self.user_data['password']
        )
        
        after_creation = timezone.now()
        
        # Verificar que la fecha está entre antes y después de la creación
        self.assertGreaterEqual(user.register_date, before_creation)
        self.assertLessEqual(user.register_date, after_creation)
        
    def test_user_meta_verbose_names(self):
        """Test que verifica los nombres verbose del modelo"""
        meta = User._meta
        self.assertEqual(meta.verbose_name, "User")
        self.assertEqual(meta.verbose_name_plural, "Users")
        
    def test_user_address_text_field(self):
        """Test que verifica que el campo address puede almacenar texto largo"""
        long_address = fake.text(max_nb_chars=500)
        
        user = User.objects.create_user(
            username=self.user_data['username'],
            email=self.user_data['email'],
            password=self.user_data['password'],
            address=long_address
        )
        
        self.assertEqual(user.address, long_address)
        
    def test_user_inherits_from_abstract_user(self):
        """Test que verifica que User hereda correctamente de AbstractUser"""
        user = User.objects.create_user(
            username=self.user_data['username'],
            email=self.user_data['email'],
            password=self.user_data['password']
        )
        
        # Verificar que tiene los campos heredados de AbstractUser
        self.assertTrue(hasattr(user, 'is_active'))
        self.assertTrue(hasattr(user, 'is_staff'))
        self.assertTrue(hasattr(user, 'is_superuser'))
        self.assertTrue(hasattr(user, 'last_login'))
        self.assertTrue(hasattr(user, 'date_joined'))
        
        # Verificar que los métodos heredados funcionan
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)