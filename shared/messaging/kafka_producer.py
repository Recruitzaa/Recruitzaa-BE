"""
shared/messaging/kafka_producer.py — Async Kafka producer (aiokafka).

Usage:
    from shared.messaging.kafka_producer import get_producer
    from shared.messaging.topics import USER_REGISTERED

    producer = await get_producer()
    await producer.send_event(USER_REGISTERED, {"user_id": "...", "email": "..."})
"""
from __future__ import annotations


import json
import logging
import os
from datetime import datetime, timezone
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
        global _producer
        if _producer is None:
            bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
            _producer = AIOKafkaProducer(
                bootstrap_servers=bootstrap,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",
                enable_idempotence=True,
                compression_type="gzip",
            )
            await _producer.start()
            logger.info("Kafka producer started — brokers: %s", bootstrap)
        self._raw = _producer

    async def send_event(
        self,
        topic: str,
        payload: dict[str, Any],
        key: str | None = None,
    ) -> None:
        """Send a structured event to a Kafka topic."""
        await self._ensure_started()
        envelope = {
            "event_id": str(uuid4()),
            "topic": topic,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        try:
            await self._raw.send_and_wait(topic, value=envelope, key=key)
            logger.debug("Kafka event sent: topic=%s key=%s", topic, key)
        except KafkaError as exc:
            logger.error("Kafka send failed: topic=%s error=%s", topic, exc)
            raise

    async def close(self):
        global _producer
        if _producer:
            await _producer.stop()
            _producer = None
