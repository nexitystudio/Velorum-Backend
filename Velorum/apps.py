"""
Configuración de la aplicación Django Velorum
"""

from django.apps import AppConfig


class VelorumConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Velorum'
    
    def ready(self):
        """
        Hook que se ejecuta cuando Django está listo
        """
        import os
        
        # Iniciar scheduler:
        # - En desarrollo (runserver): solo cuando RUN_MAIN=true (evita duplicados en auto-reload)
        # - En producción (gunicorn/otros): siempre (RUN_MAIN no existe)
        run_main = os.environ.get('RUN_MAIN')
        is_production = run_main is None  # gunicorn no setea RUN_MAIN
        is_dev_main = run_main == 'true'  # runserver proceso principal
        
        if is_production or is_dev_main:
            try:
                from . import scheduler
                scheduler.start()
                print("✅ Scheduler iniciado correctamente")
            except Exception as e:
                print(f"❌ Error al iniciar scheduler: {e}")
