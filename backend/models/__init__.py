"""
Database models package initialization.
This file sets up all the SQLAlchemy models and exports them for easy import.
"""


# Import all models to register them with SQLAlchemy
from .user_model import User
from .document_models import Document, DocumentChunk
from .conversation_models import Conversation, Message, MessageSource
from .feedback_model import Feedback
from .notification_model import Notification, NotificationRead

# Export all models for easy import
__all__ = [

    "User",
    "Document",
    "DocumentChunk",
    "Conversation",
    "Message",
    "MessageSource",
    "Feedback",
    "Notification",
    "NotificationRead",
]

# Utility function to get all models for Alembic migrations
def get_all_models():
    """
    Return a list of all SQLAlchemy models.
    Useful for Alembic migrations and metadata operations.
    """
    return [
        User,
        Document,
        DocumentChunk,
        Conversation,
        Message,
        MessageSource,
        Feedback,
        Notification,
        NotificationRead,
    ]
