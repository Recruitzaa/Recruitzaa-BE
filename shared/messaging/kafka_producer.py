"""
shared/messaging/kafka_producer.py — Async Kafka producer (aiokafka).

Usage:
    from shared.messaging.kafka_producer import get_producer
    from shared.messaging.topics import USER_REGISTERED

    producer = await get_producer()
    await producer.send_event(USER_REGISTERED, {"user_id": "...", "email": "..."})
"""

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

logger = logging.getLogger(__name__)

_producer: AIOKafkaProducer | None = None


async def get_producer() -> "RecruitzaaProducer":
    return RecruitzaaProducer()


class RecruitzaaProducer:
    """Thin wrapper around AIOKafkaProducer with structured event envelope."""

    def __init__(self):
        self._raw: AIOKafkaProducer | None = None

    async def _ensure_started(self):
        # Kafka disabled for local testing without Docker
        pass

    async def send_event(
        self,
        topic: str,
        payload: dict[str, Any],
        key: str | None = None,
    ) -> None:
        """Send a structured event to a Kafka topic."""
        # Kafka disabled for local testing without Docker
        logger.info("Kafka disabled. Skipping event send: topic=%s", topic)

    async def close(self):
        global _producer
        if _producer:
            await _producer.stop()
            _producer = None
