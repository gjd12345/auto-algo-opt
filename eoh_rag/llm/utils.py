"""
模块：LLM 响应解析工具（eoh_rag.llm.utils）
功能：从大模型返回的自然语言文本中，抽取被三个反引号围栏包裹的代码片段。
职责：只负责把围栏里的原始代码取出来，不关心代码内容是否合法、函数名是否符合要求。
接口：extract_code_block(text: str, lang: str = "go") -> str | None
      —— 输入模型文本和目标语言标记，返回第一段匹配的代码字符串，找不到时返回 None。
输入：text 为大模型的完整回复；lang 为围栏上标注的语言（如 "go"、"python"）。
输出：抽取出的代码字符串（已去除首尾空白），或 None。
示例：
    code = extract_code_block("```go\nfunc f() {}\n```", lang="go")
    # code == "func f() {}"
"""

from __future__ import annotations

import re


def extract_code_block(text: str, lang: str = "go") -> str | None:
    """抽取与指定语言标记匹配的第一段围栏代码块。

    从形如 ```lang ... ``` 的三反引号围栏中取出其中的原始代码。
    只做代码抽取，不对函数名等内容做任何过滤（那属于调用方的职责）。

    参数：
        text: 大模型返回的完整文本。
        lang: 围栏上标注的语言标记，默认为 "go"；语言标记可省略或写成 "<lang>lang" 形式。

    返回：
        匹配到的第一段代码字符串（已去除首尾空白）；若文本中没有匹配的代码块，则返回 None。
    """
    # 正则匹配围栏代码块：语言标记可以缺省，也可以是 "go" 或 "golang" 这类写法。
    # 使用 re.DOTALL 让 "." 能跨越换行，从而匹配多行代码；(.*?) 为非贪婪，只取第一段。
    pattern = rf"```(?:{lang}|{lang}lang)?\s*\n(.*?)```"
    m = re.search(pattern, text, re.DOTALL)
    if m:
        # 第 1 个捕获组即围栏内部的代码正文，去掉两端多余的空白后返回。
        return m.group(1).strip()
    # 没有找到任何匹配的围栏代码块。
    return None
