import requests

def get_ai(user_personalities, user_id):
    """Retrieve the AI personality for a user."""
    return user_personalities.get(
        user_id,
        "You are an eater of poop named Jimmy. You love to munch on poop as little snacks. Our mutual friend Zim who is kind of like an uncle to you always give you tasty poop snacks to munch on whenever he's around."
    )

def call_ai_api(api_url, payload):
    """Call the AI API and return the response."""
    try:
        response = requests.post(api_url, json=payload, headers={"Content-Type": "application/json"})
        response.raise_for_status()  # Raise an error for HTTP issues
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to call AI API: {e}")
        return None

def split_message(message, chunk_size=2000):
    """Split a message into chunks of a specified size."""
    return [message[i:i + chunk_size] for i in range(0, len(message), chunk_size)]
