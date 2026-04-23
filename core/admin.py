from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Reservation, Room, RoomImage, RoomLayout, UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Perfil Estendido'


class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


class RoomImageInline(admin.TabularInline):
    model = RoomImage
    extra = 1
    fields = ('arquivo', 'legenda', 'ordem', 'is_principal')


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('nm_sala', 'nm_predio', 'nr_andar', 'qtd_capacidade', 'metragem_m2', 'exige_aprovacao')
    search_fields = ('nm_sala', 'nm_predio', 'cdg_sala', 'end_sala')
    list_filter = ('nm_predio', 'exige_aprovacao', 'projetor', 'tela', 'videoconferencia', 'acessibilidade')
    filter_horizontal = ('layouts_permitidos',)
    inlines = (RoomImageInline,)
    fieldsets = (
        ('Informações Básicas', {
            'fields': (
                'nm_sala', 'nm_predio', 'nr_andar', 'end_sala', 'link_google_maps',
                'cdg_sala', 'qtd_capacidade', 'metragem_m2', 'obs_sala', 'descricao_detalhada'
            )
        }),
        ('Recursos Físicos e Configurações da Sala', {
            'fields': ('projetor', 'tela', 'quadro_branco', 'videoconferencia', 'acessibilidade')
        }),
        ('Arquivos e Layouts', {
            'fields': ('planta_baixa', 'layouts_permitidos')
        }),
        ('Regras de Reserva', {
            'fields': ('exige_aprovacao', 'aprovador')
        }),
    )


@admin.register(RoomLayout)
class RoomLayoutAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)


admin.site.register(Reservation)
