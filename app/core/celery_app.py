import logging
from celery import Celery
import redis
from app.core.config import settings

logger = logging.getLogger("rag_celery")

def is_redis_available(redis_url: str) -> bool:
    """探测 Redis 服务是否连通"""
    try:
        r = redis.from_url(redis_url, socket_connect_timeout=1)
        r.ping()
        return True
    except Exception:
        return False

# 探测 Redis 连接状态并动态初始化 Celery
if is_redis_available(settings.REDIS_URL):
    print("🔴 [Celery & Redis] 成功连接至 Redis 6379 任务队列 Broker 与 Backend！")
    celery_app = Celery(
        "enterprise_rag_worker",
        broker=settings.REDIS_URL,
        backend=settings.REDIS_URL
    )
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
    )
else:
    print("⚠️  [Celery & Redis] 未检测到本地运行的 Redis (6379) 实例")
    print("🔄 [Celery & Redis] 已激活内存队列 (memory://) 与 task_always_eager 弹性模式...")
    celery_app = Celery(
        "enterprise_rag_worker",
        broker="memory://",
        backend="cache+memory://"
    )
    celery_app.conf.update(
        task_always_eager=True,          # 在本地测试/无 Redis 环境下自动同步/异步执行，避免任务阻塞
        task_eager_propagates=True,
        task_store_eager_result=True,    # 保存 eager 执行结果与最终 SUCCESS 状态
        task_serializer="json",
        result_serializer="json"
    )
