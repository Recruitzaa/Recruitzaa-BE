from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# 1. Test exceptions
from shared.utils.exceptions import (
    NotFoundException,
    UnauthorizedException,
    ForbiddenException,
    ConflictException,
    UnprocessableException,
    ServiceUnavailableException,
)

def test_custom_exceptions():
    assert NotFoundException().status_code == 404
    assert UnauthorizedException().status_code == 401
    assert ForbiddenException().status_code == 403
    assert ConflictException().status_code == 409
    assert UnprocessableException().status_code == 422
    assert ServiceUnavailableException().status_code == 503


# 2. Test pagination
from shared.utils.pagination import paginate, get_skip

def test_pagination():
    res = paginate(items=["a", "b"], total=5, page=2, page_size=2)
    assert res.items == ["a", "b"]
    assert res.total == 5
    assert res.page == 2
    assert res.page_size == 2
    assert res.has_next is True
    assert res.has_prev is True

    res2 = paginate(items=["a"], total=5, page=3, page_size=2)
    assert res2.has_next is False
    assert res2.has_prev is True

    assert get_skip(page=3, page_size=10) == 20


# 3. Test caching helpers
from shared.utils.cache import cache_get, cache_set, cache_delete, cache_delete_pattern

@pytest.mark.asyncio
async def test_cache_helpers():
    with patch("shared.utils.cache.get_redis_client") as mock_get_redis:
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        # Test cache_get hit
        mock_redis.get.return_value = '"value"'
        val = await cache_get("test_key")
        assert val == "value"
        mock_redis.get.assert_called_with("test_key")

        # Test cache_get miss
        mock_redis.get.return_value = None
        val_miss = await cache_get("test_key")
        assert val_miss is None

        # Test cache_get exception handling
        mock_redis.get.side_effect = Exception("Redis error")
        val_err = await cache_get("test_key")
        assert val_err is None
        mock_redis.get.side_effect = None

        # Test cache_set
        await cache_set("test_key", {"foo": "bar"}, ttl=100)
        mock_redis.setex.assert_called_with("test_key", 100, '{"foo": "bar"}')

        # Test cache_delete
        await cache_delete("test_key")
        mock_redis.delete.assert_called_with("test_key")

        # Test cache_delete_pattern
        mock_redis.keys.return_value = ["k1", "k2"]
        mock_redis.delete.return_value = 2
        deleted = await cache_delete_pattern("test:*")
        assert deleted == 2
        mock_redis.keys.assert_called_with("test:*")
        mock_redis.delete.assert_called_with("k1", "k2")


# 4. Test MongoDB Database Helper
from shared.database.mongo import get_mongo_client, get_mongo_db

@patch.dict(os.environ, {"MONGODB_URL": "mongodb://localhost:27017", "MONGO_DB": "test_db"})
@patch("shared.database.mongo.AsyncIOMotorClient")
def test_mongo_helpers(mock_motor_client):
    import shared.database.mongo as mongo
    mongo._client = None

    client = get_mongo_client()
    assert client is not None
    mock_motor_client.assert_called_with("mongodb://localhost:27017")

    db = get_mongo_db()
    assert db is not None


# 5. Test Redis Database Helper
from shared.database.redis_client import get_redis_client, close_redis

@pytest.mark.asyncio
async def test_redis_helpers():
    with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}), \
         patch("shared.database.redis_client.from_url") as mock_from_url:
        import shared.database.redis_client as redis_client
        redis_client._redis = None

        mock_redis_instance = AsyncMock()
        mock_from_url.return_value = mock_redis_instance

        client = await get_redis_client()
        assert client == mock_redis_instance
        mock_from_url.assert_called_with("redis://localhost:6379/0", decode_responses=True)

        await close_redis()
        mock_redis_instance.aclose.assert_called_once()
        assert redis_client._redis is None


# 6. Test MinIO Storage Helper
from shared.storage.minio_client import get_minio_client, ensure_bucket, upload_file, get_presigned_url, delete_file

@patch.dict(os.environ, {
    "MINIO_ENDPOINT": "localhost:9000",
    "MINIO_ACCESS_KEY": "access",
    "MINIO_SECRET_KEY": "secret",
    "MINIO_USE_SSL": "false"
})
@patch("shared.storage.minio_client.Minio")
def test_minio_helpers(mock_minio):
    import shared.storage.minio_client as minio_client
    minio_client._client = None

    mock_minio_instance = MagicMock()
    mock_minio.return_value = mock_minio_instance

    client = get_minio_client()
    assert client == mock_minio_instance
    mock_minio.assert_called_with(
        endpoint="localhost:9000",
        access_key="access",
        secret_key="secret",
        secure=False
    )

    # Test ensure_bucket
    mock_minio_instance.bucket_exists.return_value = False
    ensure_bucket("test-bucket")
    mock_minio_instance.make_bucket.assert_called_with("test-bucket")

    # Test upload_file
    mock_minio_instance.bucket_exists.return_value = True
    url = upload_file("test-bucket", "test.txt", b"hello", "text/plain")
    assert url == "http://localhost:9000/test-bucket/test.txt"
    mock_minio_instance.put_object.assert_called()

    # Test get_presigned_url
    mock_minio_instance.presigned_get_object.return_value = "http://presigned"
    p_url = get_presigned_url("test-bucket", "test.txt")
    assert p_url == "http://presigned"

    # Test delete_file
    delete_file("test-bucket", "test.txt")
    mock_minio_instance.remove_object.assert_called_with("test-bucket", "test.txt")


# 7. Test Kafka Producer
from shared.messaging.kafka_producer import get_producer

@pytest.mark.asyncio
async def test_kafka_producer():
    with patch.dict(os.environ, {"KAFKA_BOOTSTRAP_SERVERS": "localhost:9092"}), \
         patch("shared.messaging.kafka_producer.AIOKafkaProducer") as mock_aiokafka:
        import shared.messaging.kafka_producer as kafka_producer
        kafka_producer._producer = None

        mock_prod_instance = AsyncMock()
        mock_aiokafka.return_value = mock_prod_instance

        producer = await get_producer()
        assert producer is not None

        # Test send_event
        await producer.send_event("test_topic", {"foo": "bar"})
        assert producer._raw == mock_prod_instance
        mock_prod_instance.send_and_wait.assert_called()
