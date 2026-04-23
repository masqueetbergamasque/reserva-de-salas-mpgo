from django.views.generic import TemplateView, ListView
from django.http import JsonResponse
from django.views import View
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_datetime
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Prefetch, Q
from .models import Notification, Reservation, Room, RoomImage, RoomLayout, UserProfile
import json
PASTEL_COLORS = [
    '#AEC6CF', '#FFB347', '#77DD77', '#FF6961',
    '#CFCFC4', '#F49AC2', '#CB99C9', '#FFD1DC'
]

def get_color_for_room(room_id):
    index = (room_id - 1) % len(PASTEL_COLORS)
    return PASTEL_COLORS[index]


class HomeView(TemplateView):
    template_name = 'calendario_home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rooms = list(Room.objects.all())
        selected_room_id = self.request.GET.get('sala', '').strip()
        for room in rooms:
            room.color = get_color_for_room(room.id)
        context['rooms'] = rooms
        context['selected_room_id'] = selected_room_id
        context['open_reserva_modal'] = self.request.GET.get('open_reserva') == '1'
        return context


class RoomListView(TemplateView):
    template_name = 'salas_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rooms = Room.objects.prefetch_related(
            'layouts_permitidos',
            Prefetch('fotos', queryset=RoomImage.objects.order_by('ordem', 'id')),
        ).all()

        search = self.request.GET.get('q', '').strip()
        min_capacity = self.request.GET.get('capacidade_min', '').strip()
        layout_id = self.request.GET.get('layout', '').strip()
        building = self.request.GET.get('predio', '').strip()
        selected_features = {
            feature: (self.request.GET.get(feature) == '1')
            for feature in ('projetor', 'tela', 'videoconferencia', 'quadro_branco', 'acessibilidade')
        }

        if search:
            rooms = rooms.filter(Q(nm_sala__icontains=search) | Q(obs_sala__icontains=search))
        if min_capacity:
            rooms = rooms.filter(qtd_capacidade__gte=min_capacity)
        if layout_id:
            rooms = rooms.filter(layouts_permitidos__id=layout_id)
        if building:
            rooms = rooms.filter(nm_predio=building)
        for feature, enabled in selected_features.items():
            if enabled:
                rooms = rooms.filter(**{feature: True})

        rooms = rooms.distinct().order_by('nm_predio', 'nm_sala')

        context['rooms'] = rooms
        context['layouts'] = RoomLayout.objects.order_by('nome')
        context['predios'] = (
            Room.objects.exclude(nm_predio__isnull=True)
            .exclude(nm_predio__exact='')
            .values_list('nm_predio', flat=True)
            .distinct()
            .order_by('nm_predio')
        )
        context['filters'] = {
            'q': search,
            'capacidade_min': min_capacity,
            'layout': layout_id,
            'predio': building,
            **selected_features,
        }
        return context


class RoomDetailJSONView(View):
    def get(self, request, pk, *args, **kwargs):
        room = get_object_or_404(
            Room.objects.prefetch_related(
                'layouts_permitidos',
                Prefetch('fotos', queryset=RoomImage.objects.order_by('ordem', 'id')),
            ),
            pk=pk,
        )

        fotos = [
            {
                'url': foto.arquivo.url,
                'legenda': foto.legenda or '',
                'is_principal': foto.is_principal,
            }
            for foto in room.fotos.all()
        ]

        data = {
            'id': room.id,
            'nome': room.nm_sala,
            'predio': room.nm_predio or '',
            'andar': room.nr_andar or '',
            'endereco': room.end_sala or '',
            'google_maps': room.link_google_maps or '',
            'codigo': room.cdg_sala or '',
            'capacidade': room.qtd_capacidade,
            'metragem_m2': float(room.metragem_m2) if room.metragem_m2 is not None else None,
            'descricao': room.descricao_detalhada or room.obs_sala or '',
            'observacoes': room.obs_sala or '',
            'planta_baixa': room.planta_baixa.url if room.planta_baixa else '',
            'exige_aprovacao': room.exige_aprovacao,
            'recursos': room.get_recursos(),
            'layouts': [layout.nome for layout in room.layouts_permitidos.all()],
            'fotos': fotos,
        }
        return JsonResponse(data)


# ── Events ────────────────────────────────────────────────────────────────────

class EventsJSONView(View):
    def get(self, request, *args, **kwargs):
        sala_id = request.GET.get('sala_id')
        reservations = Reservation.objects.select_related(
            'sala', 'usuario', 'usuario__perfil'
        ).exclude(tp_status='R')

        if sala_id:
            reservations = reservations.filter(sala_id=sala_id)

        events = []
        for r in reservations:
            perfil = getattr(r.usuario, 'perfil', None)
            nm_completo = r.usuario.get_full_name() or r.usuario.username

            # Tooltip aprimorado
            tooltip_parts = [
                f"<b>{r.sala.nm_sala}</b>",
                f"Assunto: {r.obs_reserva or '<i>Sem observações</i>'}",
                f"De: {nm_completo}",
                f"E-mail: {r.usuario.email}"
            ]
            if perfil and perfil.nr_ramal:
                tooltip_parts.append(f'Ramal: {perfil.nr_ramal}')
            if perfil and perfil.nm_setor:
                tooltip_parts.append(f'Setor: {perfil.nm_setor}')

            can_cancel = (
                request.user.is_authenticated and (
                    r.usuario_id == request.user.id or request.user.is_staff
                )
            )

            color = get_color_for_room(r.sala.id)

            is_pending = (r.tp_status == 'P')
            class_name = 'event-pendente' if is_pending else ''
            
            if is_pending:
                tooltip_parts.insert(0, "<span class='badge bg-warning text-dark mb-1'><i class='bi bi-hourglass-split'></i> Aprovação Pendente</span>")

            events.append({
                'id': r.id,
                'title': f'{r.sala.nm_sala} — {perfil.nm_setor if (perfil and perfil.nm_setor) else nm_completo}',
                'start': r.dth_inicio.isoformat(),
                'end': r.dth_fim.isoformat(),
                'can_cancel': can_cancel,
                'tooltip_info': '<br>'.join(tooltip_parts),
                'backgroundColor': color,
                'borderColor': color,
                'className': class_name,
                'obs_reserva': r.obs_reserva or '',
                'sala_id': r.sala.id,
                'nm_solicitante_real': nm_completo,
            })

        return JsonResponse(events, safe=False)


class ReservationCreateView(View):
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {'status': 'error', 'errors': ['Login obrigatório para criar reservas.']},
                status=401,
            )
        try:
            data = json.loads(request.body)
            sala = Room.objects.get(pk=data.get('sala_id'))
            reserva = Reservation(
                sala=sala,
                usuario=request.user,
                dth_inicio=parse_datetime(data.get('start')),
                dth_fim=parse_datetime(data.get('end')),
                obs_reserva=data.get('obs_reserva', '').strip() or None,
            )
            reserva.clean()
            reserva.save()
            return JsonResponse({'status': 'success'})
        except ValidationError as e:
            return JsonResponse({'status': 'error', 'errors': e.messages}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'errors': [str(e)]}, status=400)


class ReservationCancelView(View):
    def post(self, request, pk, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {'status': 'error', 'errors': ['Autenticação necessária.']},
                status=401,
            )
        try:
            reserva = Reservation.objects.get(pk=pk)
        except Reservation.DoesNotExist:
            return JsonResponse(
                {'status': 'error', 'errors': ['Reserva não encontrada.']},
                status=404,
            )

        eh_dono = reserva.usuario_id == request.user.id
        eh_admin = request.user.is_staff

        if not (eh_dono or eh_admin):
            return JsonResponse(
                {'status': 'error', 'errors': ['Sem permissão para cancelar esta reserva.']},
                status=403,
            )

        reserva.delete()
        return JsonResponse({'status': 'success'})


class ReservationEditView(View):
    def post(self, request, pk, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'status': 'error', 'errors': ['Autenticação necessária.']}, status=401)
        try:
            reserva = Reservation.objects.get(pk=pk)
        except Reservation.DoesNotExist:
            return JsonResponse({'status': 'error', 'errors': ['Reserva não encontrada.']}, status=404)

        eh_dono = reserva.usuario_id == request.user.id
        eh_admin = request.user.is_staff

        if not (eh_dono or eh_admin):
            return JsonResponse({'status': 'error', 'errors': ['Sem permissão para editar esta reserva.']}, status=403)

        try:
            data = json.loads(request.body)
            sala = Room.objects.get(pk=data.get('sala_id'))
            
            reserva.sala = sala
            reserva.dth_inicio = parse_datetime(data.get('start'))
            reserva.dth_fim = parse_datetime(data.get('end'))
            reserva.obs_reserva = data.get('obs_reserva', '').strip() or None
            
            reserva.clean()
            reserva.save()
            return JsonResponse({'status': 'success'})
        except ValidationError as e:
            return JsonResponse({'status': 'error', 'errors': e.messages}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'errors': [str(e)]}, status=400)


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserRegisterView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            nm_completo = data.get('nm_completo', '').strip()
            desc_email = data.get('desc_email', '').strip()
            senha = data.get('senha', '')
            senha_confirmacao = data.get('senha_confirmacao', '')
            nr_ramal = data.get('nr_ramal', '').strip()
            nm_setor = data.get('nm_setor', '').strip()

            erros = []
            if not nm_completo:
                erros.append('Nome completo é obrigatório.')
            if not desc_email:
                erros.append('E-mail é obrigatório.')
            elif User.objects.filter(email=desc_email).exists():
                erros.append('Este e-mail já está cadastrado.')
            if not senha:
                erros.append('Senha é obrigatória.')
            elif len(senha) < 8:
                erros.append('A senha deve ter no mínimo 8 caracteres.')
            if senha != senha_confirmacao:
                erros.append('As senhas não coincidem.')

            if erros:
                return JsonResponse({'status': 'error', 'errors': erros}, status=400)

            partes = nm_completo.split(' ', 1)
            usuario = User.objects.create_user(
                username=desc_email,
                email=desc_email,
                password=senha,
                first_name=partes[0],
                last_name=partes[1] if len(partes) > 1 else '',
            )
            UserProfile.objects.create(
                usuario=usuario,
                nr_ramal=nr_ramal or None,
                nm_setor=nm_setor or None,
            )
            login(request, usuario)
            return JsonResponse({
                'status': 'success',
                'usuario': {
                    'nm_completo': usuario.get_full_name(),
                    'desc_email': usuario.email,
                    'is_staff': usuario.is_staff,
                },
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'errors': [str(e)]}, status=500)


class UserLoginView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            desc_email = data.get('desc_email', '').strip()
            senha = data.get('senha', '')
            usuario = authenticate(request, username=desc_email, password=senha)
            if usuario is not None:
                login(request, usuario)
                return JsonResponse({
                    'status': 'success',
                    'usuario': {
                        'nm_completo': usuario.get_full_name(),
                        'desc_email': usuario.email,
                        'is_staff': usuario.is_staff,
                    },
                })
            return JsonResponse(
                {'status': 'error', 'errors': ['E-mail ou senha inválidos.']},
                status=400,
            )
        except Exception as e:
            return JsonResponse({'status': 'error', 'errors': [str(e)]}, status=500)


class UserLogoutView(View):
    def post(self, request, *args, **kwargs):
        logout(request)
        return JsonResponse({'status': 'success'})


class UserSessionView(View):
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            perfil = getattr(request.user, 'perfil', None)
            # Notificações de sistema (lidas ao carregar)
            from .models import Notification, Reservation
            notificacoes = list(Notification.objects.filter(usuario=request.user, lido=False).values('id', 'mensagem'))
            if notificacoes:
                Notification.objects.filter(usuario=request.user, lido=False).update(lido=True)
            
            # Contagem de aprovações pendentes onde o usuário logado é o aprovador
            qt_pendentes = Reservation.objects.filter(
                tp_status='P', 
                sala__aprovador=request.user
            ).count()

            return JsonResponse({
                'autenticado': True,
                'usuario': {
                    'nm_completo': request.user.get_full_name(),
                    'desc_email': request.user.email,
                    'is_staff': request.user.is_staff,
                    'nr_ramal': perfil.nr_ramal if perfil else '',
                    'nm_setor': perfil.nm_setor if perfil else '',
                },
                'notificacoes': notificacoes,
                'qt_pendentes_aprovacao': qt_pendentes,
            })
        return JsonResponse({'autenticado': False})


from django.contrib.auth import update_session_auth_hash

class UserProfileEditView(View):
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'status': 'error', 'errors': ['Autenticação necessária.']}, status=401)
            
        try:
            data = json.loads(request.body)
            nm_completo = data.get('nm_completo', '').strip()
            nr_ramal = data.get('nr_ramal', '').strip()
            nm_setor = data.get('nm_setor', '').strip()
            
            senha_antiga = data.get('senha_antiga', '')
            senha_nova = data.get('senha_nova', '')
            senha_confirmacao = data.get('senha_nova_confirmacao', '')
            
            erros = []
            if not nm_completo:
                erros.append('Nome completo é obrigatório.')
                
            if senha_nova:
                if not senha_antiga:
                    erros.append('A senha antiga é obrigatória para realizar a troca.')
                elif not request.user.check_password(senha_antiga):
                    erros.append('A senha antiga está incorreta.')
                    
                if len(senha_nova) < 8:
                    erros.append('A nova senha deve ter no mínimo 8 caracteres.')
                if senha_nova != senha_confirmacao:
                    erros.append('A confirmação da nova senha não coincide.')
                    
            if erros:
                return JsonResponse({'status': 'error', 'errors': erros}, status=400)
                
            # Atualiza info principal
            partes = nm_completo.split(' ', 1)
            request.user.first_name = partes[0]
            request.user.last_name = partes[1] if len(partes) > 1 else ''
            
            if senha_nova:
                request.user.set_password(senha_nova)
                
            request.user.save()
            
            if senha_nova:
                update_session_auth_hash(request, request.user)
                
            perfil, created = UserProfile.objects.get_or_create(usuario=request.user)
            perfil.nr_ramal = nr_ramal or None
            perfil.nm_setor = nm_setor or None
            perfil.save()
            
            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'errors': [str(e)]}, status=500)


# ── Approvals & Notifications ──────────────────────────────────────────────────

class AprovacaoListView(LoginRequiredMixin, ListView):
    model = Reservation
    template_name = 'aprovacao_list.html'
    context_object_name = 'reservas_pendentes'

    def get_queryset(self):
        return Reservation.objects.filter(
            tp_status='P',
            sala__aprovador=self.request.user
        ).select_related('sala', 'usuario').order_by('dth_inicio')


class AprovarReservaView(LoginRequiredMixin, View):
    def post(self, request, pk):
        reserva = get_object_or_404(Reservation, pk=pk, sala__aprovador=request.user)
        reserva.tp_status = 'A'
        reserva.save()
        
        Notification.objects.create(
            usuario=reserva.usuario,
            mensagem=f"Sua reserva para a sala {reserva.sala.nm_sala} foi aprovada!"
        )
        messages.success(request, f"Reserva de {reserva.usuario.get_full_name()} aprovada!")
        return redirect('aprovacao_list')


class RecusarReservaView(LoginRequiredMixin, View):
    def post(self, request, pk):
        reserva = get_object_or_404(Reservation, pk=pk, sala__aprovador=request.user)
        reserva.tp_status = 'R'
        reserva.save()
        
        Notification.objects.create(
            usuario=reserva.usuario,
            mensagem=f"Sua reserva para a sala {reserva.sala.nm_sala} foi recusada."
        )
        messages.warning(request, f"Reserva de {reserva.usuario.get_full_name()} recusada.")
        return redirect('aprovacao_list')
