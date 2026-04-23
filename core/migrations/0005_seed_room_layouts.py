from django.db import migrations


def seed_room_layouts(apps, schema_editor):
    RoomLayout = apps.get_model('core', 'RoomLayout')
    for nome in ('Formato U', 'Auditório', 'Formato Reunião'):
        RoomLayout.objects.get_or_create(nome=nome)


def unseed_room_layouts(apps, schema_editor):
    RoomLayout = apps.get_model('core', 'RoomLayout')
    RoomLayout.objects.filter(nome__in=('Formato U', 'Auditório', 'Formato Reunião')).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_roomlayout_room_descricao_detalhada_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_room_layouts, unseed_room_layouts),
    ]
