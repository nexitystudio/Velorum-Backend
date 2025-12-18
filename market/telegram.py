import threading
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def _send_text(token, chat_id, text, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.exception("Error sending Telegram message: %s", e)
        return False


def send_order_paid_notification(order):
    """Envía una notificación a Telegram sobre un pedido pagado.

    Usa las variables de entorno `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`
    expuestas en `settings`.
    """
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    chat_id = getattr(settings, "TELEGRAM_CHAT_ID", None)
    if not token or not chat_id:
        logger.debug("Telegram token o chat_id no configurados; omitiendo notificación")
        return

    def _format_price(value):
        try:
            val = float(value)
        except Exception:
            return str(value)
        # Mostrar sin decimales si son ceros, con separador de miles como punto
        if val.is_integer():
            s = f"{int(val):,}".replace(",", ".")
            return s
        s = f"{val:,.2f}".replace(",", ".")
        return s

    # Cliente: preferir los datos que ingresó el cliente en el checkout (campos de la orden),
    # y solo si están vacíos usar datos del perfil
    def _prefer_order_or_profile(order_obj, user_obj, order_attr, profile_attr):
        val = (getattr(order_obj, order_attr, '') or '').strip()
        if val:
            return val
        if user_obj:
            return (getattr(user_obj, profile_attr, '') or '').strip()
        return ''

    user_obj = getattr(order, 'usuario', None)
    nombre = _prefer_order_or_profile(order, user_obj, 'nombre_invitado', 'first_name')
    apellido = _prefer_order_or_profile(order, user_obj, 'apellido_invitado', 'last_name')
    email = _prefer_order_or_profile(order, user_obj, 'email_invitado', 'email')
    # Teléfono: preferir telefono_invitado, luego profile phone/telefono
    telefono = (getattr(order, 'telefono_invitado', '') or '').strip()
    if not telefono and user_obj:
        telefono = (getattr(user_obj, 'phone', '') or getattr(user_obj, 'telefono', '') or '').strip()

    # Dirección: intentar descomponer los elementos comunes
    direccion_raw = (getattr(order, 'direccion_envio', '') or '').strip()
    calle = ''
    numero = ''
    piso = ''
    departamento = ''
    ciudad = ''
    provincia = ''
    codigo_postal = getattr(order, 'codigo_postal', '') or ''
    zona_envio = getattr(order, 'zona_envio', '') or ''

    if direccion_raw:
        # Separar por comas para intentar extraer ciudad/provincia al final
        parts = [p.strip() for p in direccion_raw.split(',') if p.strip()]
        if len(parts) >= 3:
            # Ej: "Calle Falsa 123, Ciudad, Provincia"
            ciudad = parts[-2]
            provincia = parts[-1]
            street_part = ','.join(parts[:-2])
        elif len(parts) == 2:
            ciudad = parts[-1]
            street_part = parts[0]
        else:
            street_part = parts[0]

        # Buscar piso/departamento en la parte de la calle
        import re
        # piso
        m_piso = re.search(r"\b(piso|p\.?|piso\b)\s*[:#-]?\s*(\w+)", street_part, flags=re.I)
        if m_piso:
            piso = m_piso.group(2)
            street_part = street_part.replace(m_piso.group(0), '').strip()
        # departamento
        m_depto = re.search(r"\b(dpto|depto|dept|departamento|apt|apto|unidad)\s*[:#-]?\s*(\w+)", street_part, flags=re.I)
        if m_depto:
            departamento = m_depto.group(2)
            street_part = street_part.replace(m_depto.group(0), '').strip()

        # intentar separar calle y numero (ej: "Calle Falsa 123 bis")
        m = re.match(r"^(?P<calle>.*?\D)\s+(?P<numero>\d[\w\-\s/]*)$", street_part)
        if m:
            calle = m.group('calle').strip()
            numero = m.group('numero').strip()
        else:
            calle = street_part

    # Detalles del pedido formateados
    detalle_lines = []
    try:
        detalles = order.detalles.all()
        for d in detalles:
            prod = getattr(d, 'producto', None)
            nombre_prod = getattr(prod, 'nombre', None) if prod else getattr(d, 'nombre', 'Producto')
            cantidad = getattr(d, 'cantidad', 0)
            # precio unitario: preferir producto.precio cuando exista
            unit = None
            try:
                if prod and getattr(prod, 'precio', None) is not None:
                    unit = float(prod.precio)
                else:
                    unit = float(d.subtotal) / float(cantidad) if cantidad else 0
            except Exception:
                unit = getattr(d, 'subtotal', 0)
            subtotal = getattr(d, 'subtotal', 0)
            unit_s = _format_price(unit)
            subtotal_s = _format_price(subtotal)
            detalle_lines.append(f"• {nombre_prod} ({cantidad}x ${unit_s}) — ${subtotal_s}")
    except Exception:
        detalle_lines = []

    detalle_productos = "\n".join(detalle_lines) if detalle_lines else '—'

    # Total
    try:
        total = float(order.total)
    except Exception:
        total = getattr(order, 'total', 0)
    total_s = _format_price(total)

    # Notas de envío (si existe el campo y tiene contenido)
    notas_envio = getattr(order, 'notas_envio', None)
    if notas_envio:
        notas_envio = str(notas_envio).strip()

    # Construir mensaje siguiendo la estructura solicitada
    lines = []
    lines.append("🛒 NUEVO PEDIDO CONFIRMADO")
    # Número de pedido
    try:
        pid = int(getattr(order, 'id', None))
        lines.append(f"Pedido: #{pid}")
    except Exception:
        lines.append(f"Pedido: {getattr(order, 'id', '')}")
    lines.append("")
    lines.append(f"👤 Cliente: {nombre} {apellido}".strip())
    lines.append(f"📧 Email: {email}")
    lines.append(f"📞 Teléfono: {telefono}")
    lines.append("")
    lines.append("📍 Dirección:")
    # Primera línea dirección: calle numero piso depto
    addr_line1_parts = []
    if calle:
        addr_line1_parts.append(calle)
    if numero:
        addr_line1_parts.append(numero)
    line1 = ' '.join(addr_line1_parts)
    if piso:
        line1 += f" {piso if piso.startswith('P') else 'Piso ' + piso}" if line1 else f"Piso {piso}"
    if departamento:
        line1 += f" {departamento if departamento.startswith('D') else 'Depto ' + departamento}" if line1 else f"Depto {departamento}"
    lines.append(line1 or direccion_raw or '—')
    # Segunda línea: ciudad, provincia
    cityprov = ', '.join(p for p in [ciudad, provincia] if p)
    lines.append(cityprov or '—')
    lines.append(f"CP {codigo_postal} – Zona: {zona_envio}".strip())
    lines.append("")
    lines.append("📦 Pedido:")
    lines.append(detalle_productos)
    lines.append("")
    lines.append(f"💰 Total del pedido: ${total_s}")
    if notas_envio:
        lines.append("")
        lines.append("📝 Notas de envío:")
        lines.append(notas_envio)

    text = "\n".join(lines)

    # Enviar en hilo para no bloquear la respuesta del webhook
    t = threading.Thread(target=_send_text, args=(token, chat_id, text))
    t.daemon = True
    t.start()
