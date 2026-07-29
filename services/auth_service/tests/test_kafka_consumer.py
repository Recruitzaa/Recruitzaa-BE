"""Unit tests for shared.messaging.kafka_consumer.BaseKafkaConsumer."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiokafka.errors import KafkaError

from shared.messaging.kafka_consumer import BaseKafkaConsumer


class FakeAIOKafkaConsumer:
    """Stands in for AIOKafkaConsumer, supporting `async for` iteration."""

    def __init__(self, records=None, raise_on_iter=None):
        self._records = records or []
        self._raise_on_iter = raise_on_iter
        self.start = AsyncMock()
        self.stop = AsyncMock()

    async def __aiter__(self):
        for record in self._records:
            yield record
        if self._raise_on_iter:
            raise self._raise_on_iter


class RecordingConsumer(BaseKafkaConsumer):
    """Concrete consumer that records what handle_message received."""

    def __init__(self, topics, group_id, fail=False):
        super().__init__(topics, group_id)
        self.handled: list[tuple[str, dict]] = []
        self._fail = fail

    async def handle_message(self, topic: str, payload: dict) -> None:
        if self._fail:
            raise ValueError("handler blew up")
        self.handled.append((topic, payload))


def make_record(topic="raw.topic", value=None):
    return SimpleNamespace(topic=topic, value=value if value is not None else {})


@pytest.mark.asyncio
async def test_start_configures_consumer_from_env():
    fake = FakeAIOKafkaConsumer()
    consumer = RecordingConsumer(["a.topic", "b.topic"], "test-group")

    with (
        patch.dict(os.environ, {"KAFKA_BOOTSTRAP_SERVERS": "broker:9092"}),
        patch(
            "shared.messaging.kafka_consumer.AIOKafkaConsumer", return_value=fake
        ) as mock_cls,
    ):
        await consumer.start()

    args, kwargs = mock_cls.call_args
    assert args == ("a.topic", "b.topic")
    assert kwargs["bootstrap_servers"] == "broker:9092"
    assert kwargs["group_id"] == "test-group"
    assert kwargs["auto_offset_reset"] == "earliest"
    assert kwargs["enable_auto_commit"] is True

    # The deserializer must turn raw UTF-8 JSON bytes into a dict.
    assert kwargs["value_deserializer"](b'{"k": "v"}') == {"k": "v"}

    fake.start.assert_awaited_once()
    assert consumer._running is True


@pytest.mark.asyncio
async def test_start_falls_back_to_localhost_bootstrap():
    fake = FakeAIOKafkaConsumer()
    consumer = RecordingConsumer(["t"], "g")

    env_without_kafka = {
        k: v for k, v in os.environ.items() if k != "KAFKA_BOOTSTRAP_SERVERS"
    }
    with (
        patch.dict(os.environ, env_without_kafka, clear=True),
        patch(
            "shared.messaging.kafka_consumer.AIOKafkaConsumer", return_value=fake
        ) as mock_cls,
    ):
        await consumer.start()

    assert mock_cls.call_args.kwargs["bootstrap_servers"] == "localhost:9092"


@pytest.mark.asyncio
async def test_stop_is_safe_before_start():
    consumer = RecordingConsumer(["t"], "g")
    await consumer.stop()
    assert consumer._running is False


@pytest.mark.asyncio
async def test_stop_closes_active_consumer():
    fake = FakeAIOKafkaConsumer()
    consumer = RecordingConsumer(["t"], "g")

    with patch("shared.messaging.kafka_consumer.AIOKafkaConsumer", return_value=fake):
        await consumer.start()
    await consumer.stop()

    fake.stop.assert_awaited_once()
    assert consumer._running is False


@pytest.mark.asyncio
async def test_process_unwraps_envelope():
    consumer = RecordingConsumer(["t"], "g")
    record = make_record(
        topic="raw.topic",
        value={"topic": "user.registered", "payload": {"uid": "u1"}},
    )

    await consumer._process(record)

    assert consumer.handled == [("user.registered", {"uid": "u1"})]


@pytest.mark.asyncio
async def test_process_falls_back_to_record_topic_and_whole_value():
    consumer = RecordingConsumer(["t"], "g")
    record = make_record(topic="fallback.topic", value={"uid": "u2"})

    await consumer._process(record)

    assert consumer.handled == [("fallback.topic", {"uid": "u2"})]


@pytest.mark.asyncio
async def test_process_swallows_handler_errors():
    """A failing handler must not kill the consume loop."""
    consumer = RecordingConsumer(["t"], "g", fail=True)

    await consumer._process(make_record(value={"payload": {}}))

    assert consumer.handled == []


@pytest.mark.asyncio
async def test_run_consumes_all_records_then_stops():
    records = [
        make_record(value={"topic": "t1", "payload": {"n": 1}}),
        make_record(value={"topic": "t2", "payload": {"n": 2}}),
    ]
    fake = FakeAIOKafkaConsumer(records=records)
    consumer = RecordingConsumer(["t"], "g")

    with patch("shared.messaging.kafka_consumer.AIOKafkaConsumer", return_value=fake):
        await consumer.run()

    assert consumer.handled == [("t1", {"n": 1}), ("t2", {"n": 2})]
    fake.stop.assert_awaited_once()
    assert consumer._running is False


@pytest.mark.asyncio
async def test_run_handles_kafka_error_and_still_stops():
    fake = FakeAIOKafkaConsumer(raise_on_iter=KafkaError("broker gone"))
    consumer = RecordingConsumer(["t"], "g")

    with patch("shared.messaging.kafka_consumer.AIOKafkaConsumer", return_value=fake):
        await consumer.run()

    fake.stop.assert_awaited_once()
    assert consumer._running is False


@pytest.mark.asyncio
async def test_base_handle_message_is_abstract():
    base = BaseKafkaConsumer(["t"], "g")
    with pytest.raises(NotImplementedError):
        await base.handle_message("t", {})
