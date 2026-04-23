from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User


class RoomLayout(models.Model):
    nome = models.CharField(max_length=100, unique=True, db_column='nm_layout', verbose_name='Nome do Layout')

    class Meta:
        db_table = 'tb_layout_sala'
        verbose_name = 'Layout de Sala'
        verbose_name_plural = 'Layouts de Sala'
        ordering = ('nome',)

    def __str__(self):
        return self.nome


class Room(models.Model):
    id = models.AutoField(primary_key=True, db_column='id')
    nm_sala = models.CharField(max_length=150, db_column='nm_sala', verbose_name='Nome da Sala')
    qtd_capacidade = models.IntegerField(db_column='qtd_capacidade', verbose_name='Capacidade (Qtd)')
    projetor = models.BooleanField(default=False, db_column='projetor', verbose_name='Possui Projetor')
    tela = models.BooleanField(default=False, db_column='tela', verbose_name='Possui Tela')
    obs_sala = models.CharField(max_length=255, blank=True, null=True, db_column='obs_sala', verbose_name='Observações da Sala')

    nm_predio = models.CharField(max_length=150, blank=True, null=True, db_column='nm_predio', verbose_name='Nome do Prédio')
    end_sala = models.CharField(max_length=255, blank=True, null=True, db_column='end_sala', verbose_name='Endereço Completo')
    nr_andar = models.CharField(max_length=50, blank=True, null=True, db_column='nr_andar', verbose_name='Número do Andar')
    cdg_sala = models.CharField(max_length=50, blank=True, null=True, db_column='cdg_sala', verbose_name='Identificação (Código)')

    quadro_branco = models.BooleanField(default=False, db_column='quadro_branco', verbose_name='Possui Quadro Branco')
    videoconferencia = models.BooleanField(default=False, db_column='videoconferencia', verbose_name='Possui Videoconferência')
    acessibilidade = models.BooleanField(default=False, db_column='acessibilidade', verbose_name='Possui Acessibilidade')

    exige_aprovacao = models.BooleanField(default=False, db_column='exige_aprovacao', verbose_name='Exige Aprovação')
    metragem_m2 = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        blank=True,
        null=True,
        db_column='metragem_m2',
        verbose_name='Metragem (m²)',
    )
    descricao_detalhada = models.TextField(
        blank=True,
        null=True,
        db_column='descricao_detalhada',
        verbose_name='Descrição Detalhada',
    )
    planta_baixa = models.FileField(
        upload_to='room_plans/',
        blank=True,
        null=True,
        db_column='planta_baixa',
        verbose_name='Planta Baixa (PDF)',
    )
    link_google_maps = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        db_column='link_google_maps',
        verbose_name='Link do Google Maps',
    )
    aprovador = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='salas_aprovacao',
        db_column='aprovador_id',
        verbose_name='Aprovador Responsável'
    )
    layouts_permitidos = models.ManyToManyField(
        RoomLayout,
        blank=True,
        related_name='salas',
        db_table='tb_sala_layout',
        verbose_name='Layouts Permitidos',
    )

    class Meta:
        db_table = 'tb_sala'

    def clean(self):
        if self.exige_aprovacao and not self.aprovador:
            raise ValidationError("Uma sala que exige aprovação precisa ter um Aprovador designado.")

    @property
    def foto_principal(self):
        principal = next((foto for foto in self.fotos.all() if foto.is_principal), None)
        return principal or next(iter(self.fotos.all()), None)

    def get_recursos(self):
        recursos = []
        if self.projetor:
            recursos.append('Projetor')
        if self.tela:
            recursos.append('Tela/TV')
        if self.quadro_branco:
            recursos.append('Quadro Branco')
        if self.videoconferencia:
            recursos.append('Videoconferência')
        if self.acessibilidade:
            recursos.append('Acessibilidade')
        return recursos

    def __str__(self):
        return self.nm_sala


class RoomImage(models.Model):
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name='fotos',
        db_column='sala_id',
        verbose_name='Sala',
    )
    arquivo = models.FileField(upload_to='room_images/', db_column='arquivo', verbose_name='Arquivo da Foto')
    legenda = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        db_column='legenda',
        verbose_name='Legenda',
    )
    ordem = models.PositiveIntegerField(default=0, db_column='ordem', verbose_name='Ordem')
    is_principal = models.BooleanField(default=False, db_column='is_principal', verbose_name='Foto Principal')

    class Meta:
        db_table = 'tb_foto_sala'
        verbose_name = 'Foto da Sala'
        verbose_name_plural = 'Fotos da Sala'
        ordering = ('ordem', 'id')

    def clean(self):
        if self.is_principal:
            conflito = RoomImage.objects.filter(room=self.room, is_principal=True)
            if self.pk:
                conflito = conflito.exclude(pk=self.pk)
            if conflito.exists():
                raise ValidationError('A sala já possui outra foto principal definida.')

    def __str__(self):
        return self.legenda or f'Foto de {self.room.nm_sala}'


class UserProfile(models.Model):
    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        db_column='usuario_id',
        related_name='perfil',
    )
    nr_ramal = models.CharField(max_length=20, blank=True, null=True, db_column='nr_ramal')
    nm_setor = models.CharField(max_length=100, blank=True, null=True, db_column='nm_setor')

    class Meta:
        db_table = 'tb_perfil_usuario'

    def __str__(self):
        return f"Perfil de {self.usuario.get_full_name() or self.usuario.username}"


class Reservation(models.Model):
    id = models.AutoField(primary_key=True, db_column='id')
    sala = models.ForeignKey(Room, on_delete=models.CASCADE, db_column='sala_id')
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='usuario_id',
        related_name='reservas',
    )
    dth_inicio = models.DateTimeField(db_column='dth_inicio')
    dth_fim = models.DateTimeField(db_column='dth_fim')
    obs_reserva = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        db_column='obs_reserva',
    )
    
    STATUS_CHOICES = (
        ('P', 'Pendente'),
        ('A', 'Aprovada'),
        ('R', 'Recusada'),
    )
    tp_status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='A', db_column='tp_status')

    class Meta:
        db_table = 'tb_reserva'

    def clean(self):
        if self.dth_inicio and self.dth_fim:
            if self.dth_inicio >= self.dth_fim:
                raise ValidationError("Data/Hora de fim deve ser posterior à de início.")

            overlapping = Reservation.objects.filter(
                sala_id=self.sala_id,
                dth_inicio__lt=self.dth_fim,
                dth_fim__gt=self.dth_inicio,
                tp_status='A',
            )
            if self.pk:
                overlapping = overlapping.exclude(pk=self.pk)

            if overlapping.exists():
                raise ValidationError("Já existe uma reserva aprovada para esta sala neste horário.")

    def save(self, *args, **kwargs):
        if not self.pk and self.sala and self.sala.exige_aprovacao:
            self.tp_status = 'P'
        super().save(*args, **kwargs)

    def __str__(self):
        nome = self.usuario.get_full_name() or self.usuario.email
        return f"[{self.get_tp_status_display()}] {nome} — {self.sala.nm_sala}"


class Notification(models.Model):
    id = models.AutoField(primary_key=True, db_column='id')
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, db_column='usuario_id', related_name='notificacoes')
    mensagem = models.CharField(max_length=255, db_column='mensagem')
    lido = models.BooleanField(default=False, db_column='lido')
    dth_criacao = models.DateTimeField(auto_now_add=True, db_column='dth_criacao')

    class Meta:
        db_table = 'tb_notificacao'
