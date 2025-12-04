# Servicio de Mercado Pago
import mercadopago
from django.conf import settings
from django.core.cache import cache
from decimal import Decimal
import os

FRONT_URL = os.getenv("FRONT_URL")

if not FRONT_URL:
    raise ValueError("FRONT_URL no está definida en el entorno.")

FRONT_URL = FRONT_URL.rstrip("/")

BACK_URL = os.getenv("BACK_URL")

if not BACK_URL:
    raise ValueError("BACK_URL no está definida en el entorno.")

BACK_URL = BACK_URL.rstrip("/")

def create_preference(order_data, request=None):
    """
    Crea una preferencia de pago en Mercado Pago
    
    Args:
        order_data: dict con datos del pedido
            - order_id: ID del pedido
            - items: lista de productos
            - payer_email: email del comprador
            - total: total del pedido
        request: HttpRequest object (opcional, para compatibilidad)
    
    Returns:
        dict con preference_id e init_point
    """
    # Inicializar SDK de Mercado Pago
    sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)
    
    # Preparar items para MP
    items = []
    for item in order_data['items']:
        items.append({
            "title": item['name'],
            "quantity": item['quantity'],
            "unit_price": float(item['price']),
            "currency_id": "ARS"  # Pesos argentinos
        })
    
    # URLs fijas - MP agrega parámetros automáticamente (payment_id, external_reference, etc.)
    preference_data = {
        "items": items,
        "payer": {
            "name": order_data.get('payer_name', 'Test User'),
            "surname": "Test",
            "email": order_data['payer_email'],
            "phone": {
                "area_code": "",
                "number": order_data.get('payer_phone', '')
            },
            "address": {
                "street_name": order_data.get('payer_address', {}).get('street_name', ''),
                "street_number": order_data.get('payer_address', {}).get('street_number', ''),
                "zip_code": order_data.get('payer_address', {}).get('zip_code', '')
            }
        },
        "back_urls": {
            "success": f"{FRONT_URL}/checkout/success/",
            "failure": f"{FRONT_URL}/checkout/failure/",
            "pending": f"{FRONT_URL}/checkout/pending/",
        },
        "auto_return": "approved",
        "external_reference": str(order_data['order_id']),
        "notification_url": F"{BACK_URL}/api/market/mp/webhook/",
        "statement_descriptor": "VELORUM"
    }
    
    print(f"📤 Preference data a enviar: {preference_data}")
    
    # Crear preferencia
    preference_response = sdk.preference().create(preference_data)
    
    print(f"📨 Respuesta de MP: {preference_response}")
    
    # Verificar si hubo error
    if preference_response.get("status") != 201:
        error_msg = preference_response.get("response", {}).get("message", "Error desconocido de Mercado Pago")
        print(f"❌ Error de MP: {error_msg}")
        raise Exception(f"Error de Mercado Pago: {error_msg}")
    
    preference = preference_response["response"]
    
    # Verificar que tengamos los datos necesarios
    if "id" not in preference or "init_point" not in preference:
        print(f"❌ Respuesta de MP incompleta: {preference}")
        raise Exception("Mercado Pago no devolvió preference_id o init_point. Verificá tus credenciales.")
    
    return {
        "preference_id": preference["id"],
        "init_point": preference["init_point"],  # URL para redirigir al usuario
        "sandbox_init_point": preference.get("sandbox_init_point", "")  # URL de prueba
    }


def process_payment_notification(payment_id):
    """
    Procesa una notificación de pago de Mercado Pago
    
    Args:
        payment_id: ID del pago en Mercado Pago
    
    Returns:
        dict con información del pago
    """
    sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)
    
    # Obtener información del pago
    payment_info = sdk.payment().get(payment_id)
    payment = payment_info["response"]
    
    return {
        "status": payment["status"],  # approved, pending, rejected, etc.
        "status_detail": payment["status_detail"],
        "order_id": payment.get("external_reference"),  # Nuestro order_id
        "transaction_amount": payment["transaction_amount"],
        "payment_method_id": payment["payment_method_id"],
        "payment_id": payment["id"]
    }
