from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loja_web', '0009_alter_entradaestoque_quantidade'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemvenda',
            name='garantia_ate',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='itemvenda',
            name='garantia_dias',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='produto',
            name='garantia_dias',
            field=models.PositiveIntegerField(default=0, help_text='Informe 0 para produtos sem garantia.', verbose_name='Garantia (dias)'),
        ),
    ]
