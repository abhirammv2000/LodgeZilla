import logging
import secrets
import string

from ..config import settings

# Excludes whitespace, which `string.printable` would otherwise put into
# generated passwords.
_PASSWORD_ALPHABET = string.ascii_letters + string.digits + string.punctuation


def configure_logging():
    logging.basicConfig(
        filename=settings.LOG_FILE,
        level=settings.LOG_LEVEL,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def generate_password(length=10):
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))
