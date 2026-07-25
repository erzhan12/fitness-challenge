from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_per_user_reminder_cutover"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="usersettings",
            index=models.Index(
                fields=["is_reminder_active", "telegram_chat_id"],
                name="user_settings_reminder_q_idx",
            ),
        ),
    ]
