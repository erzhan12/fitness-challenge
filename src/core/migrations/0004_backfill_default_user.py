# Data migration to backfill existing data to a default user
from django.db import migrations
from django.utils import timezone


def create_default_user_and_backfill(apps, schema_editor):
    """
    Create a default user for existing single-user data and backfill all records.

    This migration:
    1. Creates a default AppUser with telegram_user_id=0 (placeholder)
    2. Creates UserSettings for the default user, copying from AppSettings
    3. Assigns all existing ExerciseTypes, ExerciseChallenges, ExerciseLogs,
       and UserStats to the default user
    """
    AppUser = apps.get_model('core', 'AppUser')
    UserSettings = apps.get_model('core', 'UserSettings')
    AppSettings = apps.get_model('core', 'AppSettings')
    ExerciseType = apps.get_model('core', 'ExerciseType')
    ExerciseChallenge = apps.get_model('core', 'ExerciseChallenge')
    ExerciseLog = apps.get_model('core', 'ExerciseLog')
    UserStats = apps.get_model('core', 'UserStats')

    # Check if there's any data to migrate
    has_data = (
        ExerciseType.objects.exists() or
        ExerciseChallenge.objects.exists() or
        ExerciseLog.objects.exists() or
        UserStats.objects.exists()
    )

    if not has_data:
        # No existing data, skip migration
        return

    # Create default user (will be updated with real telegram_user_id later)
    default_user, created = AppUser.objects.get_or_create(
        telegram_user_id=0,  # Placeholder - will be updated when user registers
        defaults={
            'username': 'default_user',
            'first_name': 'Default User',
            'timezone': 'Asia/Almaty',
            'status': 'approved',
            'approved_at': timezone.now(),
        }
    )

    # Copy settings from AppSettings singleton to UserSettings
    try:
        app_settings = AppSettings.objects.get(id=1)
        UserSettings.objects.get_or_create(
            user=default_user,
            defaults={
                'telegram_chat_id': app_settings.telegram_chat_id,
                'is_reminder_active': app_settings.is_reminder_active,
                'last_reminder_21_date': app_settings.last_reminder_21_date,
                'last_reminder_22_date': app_settings.last_reminder_22_date,
                'last_reminder_23_date': app_settings.last_reminder_23_date,
            }
        )
    except AppSettings.DoesNotExist:
        # No AppSettings, create empty UserSettings
        UserSettings.objects.get_or_create(
            user=default_user,
            defaults={
                'is_reminder_active': True,
            }
        )

    # Backfill all existing records to the default user
    ExerciseType.objects.filter(user__isnull=True).update(user=default_user)
    ExerciseChallenge.objects.filter(user__isnull=True).update(user=default_user)
    ExerciseLog.objects.filter(user__isnull=True).update(user=default_user)
    UserStats.objects.filter(user__isnull=True).update(user=default_user)


def reverse_backfill(apps, schema_editor):
    """
    Reverse the backfill by setting user to null on all records.
    Note: This doesn't delete the default user.
    """
    ExerciseType = apps.get_model('core', 'ExerciseType')
    ExerciseChallenge = apps.get_model('core', 'ExerciseChallenge')
    ExerciseLog = apps.get_model('core', 'ExerciseLog')
    UserStats = apps.get_model('core', 'UserStats')

    # Set user to null on all records (reverse of backfill)
    ExerciseType.objects.all().update(user=None)
    ExerciseChallenge.objects.all().update(user=None)
    ExerciseLog.objects.all().update(user=None)
    UserStats.objects.all().update(user=None)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_add_multi_user_support'),
    ]

    operations = [
        migrations.RunPython(
            create_default_user_and_backfill,
            reverse_backfill,
        ),
    ]
