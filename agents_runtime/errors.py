"""agents_runtime 专用异常。"""


class AgentsRuntimeError(Exception):
    """基类。"""


class PromptLoadError(AgentsRuntimeError):
    """prompt md 解析失败或文档切片找不到。"""


class ForbiddenInputError(AgentsRuntimeError):
    """装配上下文时命中 forbidden_inputs 规则。"""

    def __init__(self, message: str, *, field: str | None = None, path: str | None = None):
        super().__init__(message)
        self.field = field
        self.path = path


class LLMJsonParseError(AgentsRuntimeError):
    """两次尝试后仍无法把模型输出解析为 JSON object。"""

    def __init__(self, message: str, *, raw_text: str | None = None):
        super().__init__(message)
        self.raw_text = raw_text
