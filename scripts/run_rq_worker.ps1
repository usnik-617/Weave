param(
  [string]$RedisUrl = "redis://127.0.0.1:6379/0",
  [string]$QueueName = "weave-media"
)

$env:WEAVE_REDIS_URL = $RedisUrl
$env:WEAVE_MEDIA_QUEUE_NAME = $QueueName
python scripts/run_rq_worker.py
