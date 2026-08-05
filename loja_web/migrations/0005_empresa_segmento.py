from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loja_web', '0004_log_auditoria'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresa',
            name='segmento',
            field=models.CharField(
                choices=[
                    ('autopecas', 'Autopeças / Oficina'),
                    ('sorveteria', 'Sorveteria / Açaí'),
                ],
                default='autopecas',
                max_length=30,
            ),
        ),
    ]
