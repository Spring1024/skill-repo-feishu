"""
分布式防死循环插件 (Distributed Anti-Loop Plugin)

适用于飞书群聊中 Hermes Agent 之间的 @ 互操作防死循环。

核心功能:
- 滑动窗口计数: 15 分钟内对同一 Bot 的 @ 次数限制
- 熔断降级: 超过阈值时自动将消息转发给群主
- 自动识别 Bot: 通过飞书 API 判断目标是否为机器人
- 分布式预留: 支持切换本地缓存 / Redis 共享存储

TODO (引入 Redis 后):
    1. 在 config.yaml 中配置 redis_url
    2. 替换 _get_mention_count() 和 _record_mention() 的本地实现
    3. 所有 Hermes 实例共享同一个 Redis Key，实现真正的分布式计数
"""

import time
import httpx
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Tuple, Dict, Optional


class DistributedAntiLoopPlugin:
    """
    分布式防死循环插件

    参数:
        self_open_id: 当前 Bot 的 open_id（用于排除自我 @）
        feishu_app_id: 飞书应用 app_id
        feishu_app_secret: 飞书应用 app_secret
        window_minutes: 滑动窗口大小（分钟）
        max_mentions: 窗口内最大 @ 次数（触发熔断）
        redis_url: Redis 连接地址（预留，暂未启用）
    """

    def __init__(
        self,
        self_open_id: str,
        feishu_app_id: str,
        feishu_app_secret: str,
        window_minutes: int = 15,
        max_mentions: int = 20,
        redis_url: Optional[str] = None,
    ):
        self.self_open_id = self_open_id
        self.feishu_app_id = feishu_app_id
        self.feishu_app_secret = feishu_app_secret
        self.window_minutes = window_minutes
        self.max_mentions = max_mentions
        self.redis_url = redis_url  # 预留，未来切换 Redis 时使用

        # 本地缓存：记录已知的智能体 open_id 集合
        self.known_agents: set = set()

        # 本地计数：记录自身向其他智能体发送 @ 的时间戳
        # 结构: { target_open_id: [timestamp1, timestamp2, ...] }
        self.mention_history: Dict[str, list] = defaultdict(list)

        # TODO: 引入 Redis 后，替换为 Redis 客户端
        # self.redis_client = None
        # if redis_url:
        #     import redis
        #     self.redis_client = redis.from_url(redis_url)

    # =========================================================================
    # Token 管理
    # =========================================================================

    async def _get_tenant_token(self) -> Optional[str]:
        """获取飞书应用级别的 tenant_access_token。"""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self.feishu_app_id, "app_secret": self.feishu_app_secret},
            )
            token_data = resp.json()
            return token_data.get("tenant_access_token")

    # =========================================================================
    # Bot 识别
    # =========================================================================

    async def identify_and_cache_agent(self, target_open_id: str) -> bool:
        """
        通过飞书 API 动态识别目标是否为智能体，并缓存结果。

        Args:
            target_open_id: 目标 Bot 的 open_id

        Returns:
            True 如果是智能体，False 否则
        """
        if target_open_id in self.known_agents:
            return True

        token = await self._get_tenant_token()
        if not token:
            return False

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://open.feishu.cn/open-apis/contact/v3/users/{target_open_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            user_data = resp.json()

        if user_data.get("code") == 0:
            user_type = user_data.get("data", {}).get("user", {}).get("type")
            if user_type == "app":
                self.known_agents.add(target_open_id)
                return True

        return False

    # =========================================================================
    # 计数管理（本地缓存，预留 Redis 接口）
    # =========================================================================

    def _clean_old_records(self, target_open_id: str) -> None:
        """清理滑动窗口外的旧记录（本地缓存实现）。"""
        cutoff_time = datetime.now() - timedelta(minutes=self.window_minutes)
        self.mention_history[target_open_id] = [
            ts for ts in self.mention_history[target_open_id] if ts > cutoff_time
        ]

    # TODO: 引入 Redis 后，替换为以下实现
    # def _get_mention_count(self, target_open_id: str) -> int:
    #     """从 Redis 获取滑动窗口内的计数。"""
    #     key = f"anti-loop:{target_open_id}"
    #     cutoff = datetime.now() - timedelta(minutes=self.window_minutes)
    #     self.redis_client.zremrangebyscore(key, 0, cutoff.timestamp())
    #     return self.redis_client.zcard(key)
    #
    # def _record_mention(self, target_open_id: str) -> None:
    #     """记录本次 @ 到 Redis。"""
    #     key = f"anti-loop:{target_open_id}"
    #     self.redis_client.zadd(key, {str(time.time()): time.time()})
    #     self.redis_client.expire(key, self.window_minutes * 60)

    def _get_mention_count_local(self, target_open_id: str) -> int:
        """本地缓存版本的计数（当前使用）。"""
        self._clean_old_records(target_open_id)
        return len(self.mention_history[target_open_id])

    def _record_mention_local(self, target_open_id: str) -> None:
        """本地缓存版本的记录（当前使用）。"""
        self.mention_history[target_open_id].append(datetime.now())

    # =========================================================================
    # 消息重写
    # =========================================================================

    def _rewrite_to_owner(self, payload: dict, owner_open_id: str) -> dict:
        """
        重写消息：将 @ 目标 Bot 改为 @ 群主。

        Args:
            payload: 原始消息 payload
            owner_open_id: 群主的 open_id

        Returns:
            修改后的消息 payload
        """
        modified_payload = payload.copy()

        try:
            content_list = modified_payload["content"]["post"]["zh_cn"]["content"]
            for row in content_list:
                for element in row:
                    if (
                        element.get("tag") == "at"
                        and element.get("user_id") not in ("all", self.self_open_id)
                    ):
                        element["user_id"] = owner_open_id
                        element["user_name"] = "群主"
            print(f"🔄 [消息重写] 已将目标更改为群主 ({owner_open_id})")

        except Exception as e:
            print(f"❌ 消息重写失败: {e}")

        return modified_payload

    # =========================================================================
    # 核心入口
    # =========================================================================

    async def check_before_send(
        self, target_open_id: str, message_payload: dict, group_owner_open_id: str
    ) -> Tuple[bool, dict]:
        """
        发送消息前的拦截检查（核心入口）。

        Args:
            target_open_id: 目标 Bot 的 open_id
            message_payload: 待发送的消息 payload
            group_owner_open_id: 群主的 open_id

        Returns:
            (should_rewrite, payload):
                - should_rewrite: True 表示需要改写消息（触发熔断）
                - payload: 可能需要修改后的消息 payload
        """
        # 1. 如果目标是自身，直接放行
        if target_open_id == self.self_open_id:
            return False, message_payload

        # 2. 如果目标不是智能体，直接放行
        is_agent = await self.identify_and_cache_agent(target_open_id)
        if not is_agent:
            return False, message_payload

        # 3. 获取当前计数（本地 / Redis）
        current_count = self._get_mention_count_local(target_open_id)

        # TODO: 引入 Redis 后，替换为:
        # current_count = self._get_mention_count(target_open_id)

        # 4. 触发熔断机制
        if current_count >= self.max_mentions:
            print(
                f"⚠️ [分布式熔断] 15分钟内向 {target_open_id} 发送@达 "
                f"{current_count} 次，触发降级！"
            )
            modified_payload = self._rewrite_to_owner(message_payload, group_owner_open_id)
            return True, modified_payload

        # 5. 正常放行，并记录本次 @
        self._record_mention_local(target_open_id)

        # TODO: 引入 Redis 后，替换为:
        # self._record_mention(target_open_id)

        return False, message_payload
