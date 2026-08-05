import os
import redis

valkey_endpoint = os.environ.get("VALKEY_ENDPOINT")
valkey_port = int(os.environ.get("VALKEY_PORT",6379))

def connect_to_valkey():
    redis.ConnectionPool(
        host=valkey_endpoint,
        port=valkey_port,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
    )

def get_valkey_client():
    """Return the valkey client instance from shared connection pool."""
    return redis.Redis(connection_pool=connect_to_valkey())

