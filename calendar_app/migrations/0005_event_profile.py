from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('calendar_app', '0004_event_shared_with_alter_event_id_calendarshare')]
    operations = [
        migrations.AddField(
            model_name='event', name='profile',
            field=models.CharField(choices=[('work', 'Work'), ('school', 'School'), ('personal', 'Personal')],
                                   default='personal', max_length=8),
        ),
    ]
