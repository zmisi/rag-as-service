"""F06 Agent Loop constants."""

MAX_STEPS = 5
HISTORY_COMPRESS_AFTER_MESSAGES = 20
KEEP_RECENT_MESSAGES = 6
LLM_TIMEOUT_S = 60
TOP_K = 5

TOOL_SEARCH_KNOWLEDGE = "search_knowledge"
TOOL_WHITELIST = frozenset({TOOL_SEARCH_KNOWLEDGE})

NO_HIT_PHRASE = "知识库无相关内容"
ERROR_REPLY = "抱歉，处理您的请求时出错，请稍后重试。"
TRUNCATED_REPLY = "已达到本轮最大推理步数，以下是基于目前信息的总结。"
