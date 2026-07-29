"""
shared/auth/firebase_admin.py — Firebase Admin SDK initialization.
"""

import logging
import os

import firebase_admin
from firebase_admin import credentials

logger = logging.getLogger(__name__)

_app: firebase_admin.App | None = None


def get_firebase_app() -> firebase_admin.App:
    """Initialize Firebase Admin SDK (singleton). Safe to call multiple times."""
    global _app
    if _app is not None:
        return _app

    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path and os.path.isfile(cred_path):
        cred = credentials.Certificate(cred_path)
        _app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin initialized from service account: %s", cred_path)
    else:
        # Application Default Credentials (GCP Cloud Run / CI)
        _app = firebase_admin.initialize_app()
        logger.info("Firebase Admin initialized via Application Default Credentials")

    return _app
