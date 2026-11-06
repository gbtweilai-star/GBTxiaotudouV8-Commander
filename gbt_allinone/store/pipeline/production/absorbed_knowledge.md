# mangiucugna/json_repair 吞噬记录 — devour_tentacle
> 吞噬日期: 2026-11-05T07:31:15 | 来源: https://github.com/mangiucugna/json_repair
> Stars: 5132 | 语言: Python | 许可: MIT

## 项目概览
- 描述: Repair malformed JSON from LLMs, APIs, logs, and user input in Python.
- 主题: cli, json, json-repair, json-schema, llm, llm-output, malformed-json, parser, pydantic, python
- 分支: main | 最近推送: 2026-11-03

## README 摘要
[![PyPI](https://img.shields.io/pypi/v/json-repair)](https://pypi.org/project/json-repair/)
![Python version](https://img.shields.io/badge/python-3.10+-important)
[![PyPI downloads](https://img.shields.io/pypi/dm/json-repair)](https://pypi.org/project/json-repair/)
[![PyPI Downloads](https://static.pepy.tech/badge/json-repair)](https://pepy.tech/projects/json-repair)
[![Github Sponsors](https://img.shields.io/github/sponsors/mangiucugna)](https://github.com/sponsors/mangiucugna)
[![GitHub Repo stars](https://img.shields.io/github/stars/mangiucugna/json_repair?style=flat)](https://github.com/mangiucugna/json_repair/stargazers)

English | [中文](https://github.com/mangiucugna/json_repair/blob/main/README.zh.md)

# json_repair

Repair malformed JSON from LLMs, APIs, logs, and user input in Python.

- Fix missing quotes, commas, brackets, comments, stray prose, and truncated values.
- Use it as a drop-in fallback for `json.loads()` or as a schema-guided repair step.
- Install with `pip install json-repair` or try the [live demo](https://mangiucugna.github.io/json_repair/).

![banner](https://raw.githubusercontent.com/mangiucugna/json_repair/main/banner.png)

---

## Quick example

```python
import json_repair

bad_json = '{"users":[{"name":"Ada","role":"admin",}],"ok":true'
decoded_object = json_repair.loads(bad_json)

# {'users': [{'name': 'Ada', 'role': 'admin'}], 'ok': True}
```

If `json_repair` saves you time, [star the repository](https://github.com/mangiucugna/json_repair) so more people can find it.

---

# Demo
If you are unsure whether this library will fix your specific problem, or simply want your JSON validated online, try one of these:

- Live demo: https://mangiucugna.github.io/json_repair/
- Audio overview: [NotebookLM introduction](https://notebooklm.google.com/notebook/05312bb3-f6f3-4e49-a99b-bd51db64520b/audio)

## Premium sponsors
- [Icana-AI](https://github.com/Icana-AI) Makers of CallCoach, the world's best Call Centre AI Coach. Visit [https://www.icana.ai/](https://www.icana.ai/)
- [mjharte](https://github.com/mjharte)

---

# Think about sponsoring this library!
This library is free for everyone and is maintained as a side project, so if it helps your work, consider becoming a sponsor: https://github.com/sponsors/mangiucugna

---

# Motivation
Some LLMs are a bit iffy when it comes to returning well formed JSON data, sometimes they skip a parentheses and sometimes they add some words in it, because that's what an LLM does.
Luckily, the mistakes LLMs make are simple enough to be fixed without destroying the content.

I searched for a lightweight python package that was able to reliably fix this problem but couldn't find any.

*So I wrote one*

# Supported use cases

### Fixing Syntax Errors in JSON

- Missing quotes, misplaced commas, unescaped characters, and incomplete key-value pairs.
- Missing quotation marks, improperly formatted values (true, false, null), and repairs corrupted key-value structures.
- Python-style tuples: comma-separated parenthesized sequences become JSON arrays, while a single parenthesized value remains a scalar. Within arrays, objects, and tuples, `true`/`false`/`null` and `None` are recognized case-insensitively as JSON booleans or null.

### Repairing Malformed JSON Arrays and Objects

- Incomplete or broken arrays/objects by adding necessary elements (e.g., commas, brackets) or default values (null, "").
- The library can process JSON that includes extra non-JSON characters like comments or improperly placed characters, cleaning them up while maintaining valid structure.

### Auto-Completion for Missing JSON Values

- Automatically completes missing values in JSON fields with reasonable defaults (like empty strings or null), ensuring validity.

# How to use

Install the library with pip

    pip install json-repair

then you can use use it in your code like this

    from json_repair import repair_json

    good_json_string = repair_json(bad_json_string)
    # If the string was super broken this will return an empty string


You can use this library to completely replace `json.loads()`:

    import json_repair

    decoded_object = json_repair.loads(json_string)

or just

    import json_repair

    decoded_object = json_repair.repair_json(json_string, return_objects=True)

### Avoid this antipattern
Some users of this library adopt the following pattern:

    obj = {}
    try:
        obj = json.loads(string)
    except json.JSONDecodeError as e:
        obj = json_repair.loads(string)
        ...

This is wasteful because `json_repair` already does that strict `json.loads()` check for you by default. The normal flow is:

- try the built-in `json.loads()` / `json.load()` first
- if that succeeds, return the decoded object
- if that fails, run the repair parser

Use the default call unless you explicitly want to skip that initial validation step:

```python
import json_repair

decoded_object = json_repair.loads(json_string)
```

### Read json from a file or file descriptor

JSON repair provides also a drop-in replacement for `json.load()`:

    import json_repair

    try:
        file_descriptor = open(fname, 'rb')
    except OSError:
        ...

    with file_descriptor:
        decoded_object = json_repair.load(file_descriptor)

and another method to read from a file:

    import json_repair

    try:
        decoded_object = json_repair.from_file(json_file)
    except OSError:
        ...
    except IOError:
        ...

Keep in mind that the library will not catch any IO-related exception and those will need to be managed by you

### Non-Latin characters

When working with non-Latin characters (such as Chinese, Japanese, or Korean), you need to pass `ensure_ascii=False` to `repair_json()` in order to preserve the non-Latin characters in the output.

Here's an example using Chinese characters:

    repair_json("{'test_chinese_ascii':'统一码'}")

will return

    {"test_chinese_ascii": "\u7edf\u4e00\u7801"}

Instead passing `ensure_ascii=Fa

## 对 GBT 的启示
- 可吸收点: 结合仓库定位与 README 技术栈, 提炼可注入 GBT cap 的知识

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
