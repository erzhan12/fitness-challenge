from supabase import create_client, Client
from app.config import settings
from src.core.repositories import (
    exercise_type_repo,
    challenge_repo,
    log_repo,
    user_stats_repo,
)

# Initialize Supabase client (kept for data migration script)
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


def get_supabase() -> Client:
    """Get Supabase client (deprecated - kept for data migration only)."""
    return supabase


# Repository getters for dependency injection
def get_exercise_type_repo():
    """Get ExerciseType repository."""
    return exercise_type_repo


def get_challenge_repo():
    """Get ExerciseChallenge repository."""
    return challenge_repo


def get_log_repo():
    """Get ExerciseLog repository."""
    return log_repo


def get_user_stats_repo():
    """Get UserStats repository."""
    return user_stats_repo
