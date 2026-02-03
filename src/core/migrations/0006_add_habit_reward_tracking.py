from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_add_registration_controls"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersettings",
            name="habit_reward_api_key",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="habit_reward_habit_id",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="last_habit_reward_sent_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
