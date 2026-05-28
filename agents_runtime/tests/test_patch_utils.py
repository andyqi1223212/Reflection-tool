"""_patch_utils 单元测试。"""
from __future__ import annotations

import unittest

from agents_runtime._patch_utils import (
    apply_patch,
    apply_patches_safely,
    locate_section_bounds,
    validate_patches,
)


SAMPLE = """# Doc

## 2. 童年 / 家族 Timeline

| 时段 | 事件 |
|------|------|
| 小学 | 事件 A |

## 3. 其它

正文
"""


class TestPatchUtils(unittest.TestCase):
    def test_locate_section_2(self) -> None:
        start, end = locate_section_bounds(SAMPLE, "§2")
        self.assertIn("童年", SAMPLE[start:end])

    def test_append_to_section(self) -> None:
        out = apply_patch(
            SAMPLE,
            {
                "section": "§2",
                "action": "append",
                "new_content": "- 测试追加",
            },
        )
        self.assertIn("测试追加", out)

    def test_apply_safely_rollback(self) -> None:
        patches = [
            {
                "id": "ok",
                "section": "§2",
                "action": "append",
                "new_content": "- ok",
            },
            {
                "id": "bad",
                "action": "replace_line",
                "anchor_text": "___不存在___",
                "new_content": "x",
            },
        ]
        new_text, failed = apply_patches_safely(SAMPLE, patches)
        self.assertEqual(new_text, SAMPLE)
        self.assertEqual(failed, ["bad"])

    def test_validate_patches(self) -> None:
        failed = validate_patches(
            SAMPLE,
            [{"id": "p1", "action": "replace_line", "anchor_text": "NOPE", "new_content": "x"}],
        )
        self.assertEqual(failed, ["p1"])


if __name__ == "__main__":
    unittest.main()
