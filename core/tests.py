from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Reservation, Room, RoomImage, RoomLayout


class ReservationOverlapTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='teste@mpgo.mp.br',
            email='teste@mpgo.mp.br',
            password='senha-segura-123',
        )
        self.room = Room.objects.create(
            nm_sala='Sala de Reunioes 1',
            qtd_capacidade=10,
            projetor=True,
            tela=True,
            obs_sala='Sala principal',
        )
        self.now = timezone.now().replace(second=0, microsecond=0)

    def test_double_booking_raises_error(self):
        start_time1 = self.now.replace(hour=10, minute=0)
        end_time1 = start_time1 + timedelta(hours=1)

        Reservation.objects.create(
            sala=self.room,
            usuario=self.user,
            dth_inicio=start_time1,
            dth_fim=end_time1,
        )

        start_time2 = start_time1 + timedelta(minutes=30)
        end_time2 = start_time2 + timedelta(hours=1)

        reservation2 = Reservation(
            sala=self.room,
            usuario=self.user,
            dth_inicio=start_time2,
            dth_fim=end_time2,
        )

        with self.assertRaises(ValidationError):
            reservation2.clean()

    def test_valid_reservations(self):
        start_time1 = self.now.replace(hour=8, minute=0)
        end_time1 = start_time1 + timedelta(hours=1)

        Reservation.objects.create(
            sala=self.room,
            usuario=self.user,
            dth_inicio=start_time1,
            dth_fim=end_time1,
        )

        start_time2 = end_time1
        end_time2 = start_time2 + timedelta(hours=1)

        reservation2 = Reservation(
            sala=self.room,
            usuario=self.user,
            dth_inicio=start_time2,
            dth_fim=end_time2,
        )
        reservation2.clean()
        reservation2.save()
        self.assertEqual(Reservation.objects.count(), 2)

    def test_invalid_time_range(self):
        reservation = Reservation(
            sala=self.room,
            usuario=self.user,
            dth_inicio=self.now,
            dth_fim=self.now - timedelta(hours=1),
        )

        with self.assertRaises(ValidationError):
            reservation.clean()


class RoomCatalogViewTests(TestCase):
    def setUp(self):
        self.layout_auditorio, _ = RoomLayout.objects.get_or_create(nome='Auditório')
        self.layout_u, _ = RoomLayout.objects.get_or_create(nome='Formato U')

        self.room = Room.objects.create(
            nm_sala='Sala Azul',
            qtd_capacidade=20,
            nm_predio='Sede',
            nr_andar='2 andar',
            projetor=True,
            tela=True,
            videoconferencia=True,
            metragem_m2='42.50',
            end_sala='Rua Exemplo, 123',
            link_google_maps='https://maps.google.com/?q=Rua+Exemplo+123',
            descricao_detalhada='Sala para reunioes ampliadas.',
        )
        self.room.layouts_permitidos.add(self.layout_auditorio, self.layout_u)
        RoomImage.objects.create(
            room=self.room,
            arquivo=SimpleUploadedFile('foto-sala.jpg', b'fake-image-content', content_type='image/jpeg'),
            legenda='Vista frontal',
            is_principal=True,
        )

    def test_room_list_view_renders(self):
        response = self.client.get(reverse('room_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sala Azul')
        self.assertContains(response, 'Formato U')

    def test_room_list_filters_by_feature(self):
        response = self.client.get(reverse('room_list'), {'videoconferencia': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['rooms']), [self.room])

    def test_room_detail_json_returns_expected_fields(self):
        response = self.client.get(reverse('api_room_detail', args=[self.room.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['nome'], 'Sala Azul')
        self.assertIn('Formato U', data['layouts'])
        self.assertIn('Videoconferência', data['recursos'])
        self.assertEqual(len(data['fotos']), 1)

    def test_home_respects_preselected_room(self):
        response = self.client.get(reverse('home'), {'sala': self.room.id, 'open_reserva': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_room_id'], str(self.room.id))
        self.assertTrue(response.context['open_reserva_modal'])
