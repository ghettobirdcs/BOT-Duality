def add_to_conversation(conversation_history, user_id, message):
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    conversation_history[user_id].append(message)
