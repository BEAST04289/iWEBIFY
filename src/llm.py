from openai import OpenAI
from src.config import settings
import time

client = OpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url=settings.OPENROUTER_BASE_URL,
)

# Robust list of models to try in order
FALLBACK_MODELS = [
    settings.MODEL_NAME,  # The one from .env
    "google/gemma-4-31b-it:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "google/gemma-2-9b-it:free",
    "openrouter/free" # Let OpenRouter pick as a last resort
]

def generate_json_with_fallback(prompt: str, max_retries: int = 3) -> str:
    """Generate JSON using OpenRouter with automatic fallback and exponential backoff."""
    last_error = None
    
    # De-duplicate models while preserving order
    models_to_try = []
    for m in FALLBACK_MODELS:
        if m not in models_to_try:
            models_to_try.append(m)
            
    for model in models_to_try:
        retries = 0
        backoff = 3
        while retries < max_retries:
            try:
                print(f"Attempting generation with model: {model} (Attempt {retries+1})...")
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    timeout=30.0,
                )
                
                # Safely check if choices exist (OpenRouter sometimes returns 200 OK with error payloads)
                if not getattr(response, "choices", None) or len(response.choices) == 0:
                    raise ValueError(f"Malformed response (no choices): {response}")
                    
                raw = response.choices[0].message.content
                if raw:
                    print(f"Success with model: {model}")
                    return raw
            except Exception as e:
                last_error = str(e)
                print(f"Model {model} failed: {last_error}.")
                if "429" in last_error or "free-models-per-min" in last_error:
                    print(f"Rate limited. Backing off for {backoff} seconds...")
                    time.sleep(backoff)
                    retries += 1
                    backoff *= 2 # Exponential backoff
                    continue # Retry SAME model
                else:
                    time.sleep(1)
                    break # Break out of while loop, try NEXT model
            
    raise ValueError(f"All fallback models failed. Last error: {last_error}")


def generate_validated_model(prompt: str, schema_class, max_repairs: int = 3):
    """
    Validation + Repair Engine (CORE REQUIREMENT)
    Generates JSON and strictly validates it against the Pydantic schema_class.
    If validation fails (missing keys, hallucinated fields, type errors), 
    it automatically constructs a repair prompt and asks the LLM to fix it,
    avoiding a blind retry.
    """
    from pydantic import ValidationError
    from src.utils import clean_json
    
    raw_json = generate_json_with_fallback(prompt)
    
    repairs = 0
    while repairs < max_repairs:
        try:
            return schema_class.model_validate_json(clean_json(raw_json))
        except ValidationError as e:
            repairs += 1
            print(f"Schema validation failed! Initiating Repair {repairs}/{max_repairs}...")
            
            repair_prompt = f"""You previously generated a JSON response that FAILED strict schema validation.

Validation Errors:
{str(e)}

Your Invalid JSON:
{raw_json}

The Original Instructions:
{prompt}

CRITICAL TASK: 
Fix the JSON so it strictly complies with the schema. 
Pay close attention to the validation errors above (e.g., missing fields, incorrect types).
Return ONLY the corrected, valid JSON object."""

            raw_json = generate_json_with_fallback(repair_prompt)
            
    # Final attempt
    return schema_class.model_validate_json(clean_json(raw_json))
