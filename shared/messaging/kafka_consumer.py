"""
shared/messaging/kafka_consumer.py — Base async Kafka consumer (aiokafka).

Each microservice extends BaseKafkaConsumer to handle specific topics.
"""

import json
import logging
import os
from collections.abc import Callable, Coroutine
from typing import Any

from aiokafka import AIOKafkaConsumer, ConsumerRecord
from aiokafka.errors import KafkaError

logger = logging.getLogger(__name__)

HandlerFn = Callable[[dict], Coroutine[Any, Any, None]]


class BaseKafkaConsumer:
    """
    Base consumer class. Subclass and implement `handle_message()`.

    Usage:
        class NotificationConsumer(BaseKafkaConsumer):
            async def handle_message(self, topic: str, payload: dict):
                if topic == topics.USER_REGISTERED:
                    await send_welcome_email(payload)
    """

    def __init__(self, topics: list[str], group_id: str):
        self.topics = topics
        self.group_id = group_id
        self._consumer: AIOKafkaConsumer | None = None
        self._running = False

    async def start(self):
        bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self._consumer = AIOKafkaConsumer(
            *self.topics,
            bootstrap_servers=bootstrap,
            group_id=self.group_id,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        await self._consumer.start()
        self._running = True
        logger.info(
            "Kafka consumer started — group=%s topics=%s",
            self.group_id,
            self.topics,
        )

    async def stop(self):
        self._running = False
        if self._consumer:
            await self._consumer.stop()
            logger.info("Kafka consumer stopped — group=%s", self.group_id)

    async def run(self):
        """Main consume loop. Call from asyncio task."""
        await self.start()
        try:
            async for record in self._consumer:
                await self._process(record)
        except KafkaError as exc:
            logger.error("Kafka consumer error: %s", exc)
        finally:
            await self.stop()

    async def _process(self, record: ConsumerRecord):
        try:
            envelope = record.value
            topic = envelope.get("topic", record.topic)
            payload = envelope.get("payload", envelope)
            logger.debug("Kafka message received: topic=%s", topic)
            await self.handle_message(topic, payload)
        except Exception as exc:
            logger.error(
                "Error processing Kafka message on topic=%s: %s",
                record.topic,
                exc,
                exc_info=True,
            )

    async def handle_message(self, topic: str, payload: dict) -> None:
        """Override in subclass to handle messages."""
        raise NotImplementedError
