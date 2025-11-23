import json
from typing import List, Dict, Any
from openai import OpenAI
from app.config import settings
from app.models import ParseResult, ExerciseType

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def parse_workout_message(text: str, exercise_types: List[ExerciseType]) -> ParseResult:
    """
    Uses OpenAI to parse the user's message into structured exercise data.
    """
    
    # Prepare list of valid exercises for the prompt
    exercises_info = [
        f"{et.name} (aliases: {', '.join(et.aliases or [])}, unit: {et.unit})"
        for et in exercise_types
    ]
    
    system_prompt = f"""
    You are a fitness log parser. Extract exercise data from natural language text.
    
    Constraint: You ONLY accept these exercise types:
    {json.dumps(exercises_info, indent=2)}
    
    Rules:
    1. If the user provides a number without an exercise name, default to 'pushups'.
    2. For time-based exercises (like plank), 'count' should be the display value (e.g. minutes), and 'duration_seconds' must be the total seconds.
       - If user says "2 min plank", count=2, duration_seconds=120.
       - If user says "90 sec plank", count=1 (rounded min is okay for display) or 1.5, duration_seconds=90.
    3. For rep-based exercises, 'count' is the number of reps, 'duration_seconds' is null.
    4. Handle multiple exercises in one message (e.g., "20 pushups and 30 squats").
    5. Return strict JSON.
    
    Schema:
    {{
      "entries": [
        {{
          "exercise_type_name": "string (must match one of the 'name' fields provided)",
          "count": "integer (reps or minutes)",
          "duration_seconds": "integer (or null)",
          "notes": "string (optional context)",
          "confidence": "float (0.0 to 1.0)"
        }}
      ],
      "is_valid": boolean,
      "error_reason": "string (friendly reply if no exercises found, else null)"
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"},
            temperature=0
        )
        
        content = response.choices[0].message.content
        data = json.loads(content)
        return ParseResult(**data)
        
    except Exception as e:
        # Fallback for API errors
        return ParseResult(entries=[], is_valid=False, error_reason=f"AI parsing failed: {str(e)}")

def generate_motivational_response(exercise_name: str, stats: Dict[str, Any]) -> str:
    """
    Generates a short, witty, exercise-aware comment.
    stats includes: today_total, target_total, day_number, status ('ahead', 'behind', 'on_track'), streak
    """
    
    system_prompt = """
    You are a sarcastic but kind fitness coach bot.
    Generate a VERY SHORT (1-2 sentences max) witty comment based on the user's progress.
    Tone: Playful, slightly judging but encouraging.
    """
    
    user_content = f"""
    Exercise: {exercise_name}
    Status: {stats.get('status')}
    Today's Count: {stats.get('today_total')}
    Challenge Day: {stats.get('day_number')}
    Streak: {stats.get('streak')}
    
    Write a one-liner.
    """
    
    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.7,
            max_tokens=60
        )
        return response.choices[0].message.content.strip()
    except:
        return "Keep crushing it! 💪"

