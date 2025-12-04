from django.contrib import admin
from .models import *

# Register your models here.

admin.site.register(Product)
admin.site.register(Order)
admin.site.register(OrderDetail)
admin.site.register(Pay)
admin.site.register(Category)
admin.site.register(Shipment)

@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'product__nombre', 'product__name')


@admin.register(CodigoDescuento)
class CodigoDescuentoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'porcentaje_descuento', 'activo', 'usos_actuales', 'usos_maximos', 'fecha_expiracion')
    list_filter = ('activo', 'fecha_creacion', 'fecha_expiracion')
    search_fields = ('codigo', 'descripcion')
    readonly_fields = ('usos_actuales', 'fecha_creacion', 'fecha_actualizacion')
    fieldsets = (
        ('Información Básica', {
            'fields': ('codigo', 'descripcion', 'porcentaje_descuento')
        }),
        ('Estado', {
            'fields': ('activo', 'fecha_inicio', 'fecha_expiracion')
        }),
        ('Límites', {
            'fields': ('usos_maximos', 'usos_actuales', 'usos_por_usuario', 'monto_minimo')
        }),
        ('Metadata', {
            'fields': ('creado_por', 'fecha_creacion', 'fecha_actualizacion'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UsoCodigoDescuento)
class UsoCodigoDescuentoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'orden', 'usuario', 'monto_descuento', 'fecha_uso')
    list_filter = ('fecha_uso', 'codigo')
    search_fields = ('codigo__codigo', 'orden__id', 'usuario__username')
    readonly_fields = ('fecha_uso',)
    