# -*- coding: utf-8 -*-
"""负对照 · 故意犯下每一条「AI 代码味」（第二轮扩充版）。

用途：`audit_code_taste.py --selftest` 要求本文件的**每条罪都命中**。
判据两边都红/都绿，说明判据没在干活。
"""
import json
import os


# ❌ P1-8 教程味占位命名
foo = 1
bar = 2
baz = foo + bar

# ❌ P1-13 布尔名什么都没说（flag / result / temp 这类）
flag = True

# ❌ P1-14 同一文件里 snake_case 与 camelCase 并存
my_value = 1
other_value = 2
third_value = 3
myValue = 1
otherValue = 2
thirdValue = 3


def get_data():
    # ❌ P0-2 占位 / 未实现
    raise NotImplementedError


def export_all(rows):
    # 已实现导出 # ❌ P0-6 注释说谎（完成声明 + 空实现）
    pass


def handle_stuff():
    try:
        return json.loads("{}")
    except Exception:
        pass  # ❌ P0-1 静默吞错


def classify(raw):
    # ❌ P1-4 错误处理一把抓（generic 占比 100%）
    try:
        return int(raw)
    except Exception:
        return 0


def load(raw):
    try:
        return json.loads(raw)
    except Exception:
        return {}


def debug_me(payload):
    breakpoint()  # ❌ P0-3 调试残留
    return payload


class UserManager:  # ❌ P1-10 后缀滥用（三个起报）
    pass


class OrderHelper:
    pass


class DateUtil:
    pass


class Store:  # ❌ P1-12 单方法类
    def load(self, key):
        return key


class Report:  # ❌ P1-13c 上下文重复（类名又在方法名里）
    def report_send(self, payload):
        return payload


def process(rows):  # ❌ P1-13b 超通用函数名
    return rows


def fetch_record(name):  # ❌ P1-12b 只转发参数的包装
    return load_record(name)


def load_record(name):
    return {"name": name}


def long_one():
    # ❌ P1-5 函数过长（> 80 行）
    a1 = 1
    a2 = 2
    a3 = 3
    a4 = 4
    a5 = 5
    a6 = 6
    a7 = 7
    a8 = 8
    a9 = 9
    a10 = 10
    a11 = 11
    a12 = 12
    a13 = 13
    a14 = 14
    a15 = 15
    a16 = 16
    a17 = 17
    a18 = 18
    a19 = 19
    a20 = 20
    a21 = 21
    a22 = 22
    a23 = 23
    a24 = 24
    a25 = 25
    a26 = 26
    a27 = 27
    a28 = 28
    a29 = 29
    a30 = 30
    a31 = 31
    a32 = 32
    a33 = 33
    a34 = 34
    a35 = 35
    a36 = 36
    a37 = 37
    a38 = 38
    a39 = 39
    a40 = 40
    a41 = 41
    a42 = 42
    a43 = 43
    a44 = 44
    a45 = 45
    a46 = 46
    a47 = 47
    a48 = 48
    a49 = 49
    a50 = 50
    a51 = 51
    a52 = 52
    a53 = 53
    a54 = 54
    a55 = 55
    a56 = 56
    a57 = 57
    a58 = 58
    a59 = 59
    a60 = 60
    a61 = 61
    a62 = 62
    a63 = 63
    a64 = 64
    a65 = 65
    a66 = 66
    a67 = 67
    a68 = 68
    a69 = 69
    a70 = 70
    a71 = 71
    a72 = 72
    a73 = 73
    a74 = 74
    a75 = 75
    a76 = 76
    a77 = 77
    a78 = 78
    a79 = 79
    a80 = 80
    a81 = 81
    a82 = 82
    a83 = 83
    a84 = 84
    a85 = 85
    return a85


def deep_one(rows):
    # ❌ P1-6 嵌套过深（if/for/while/with/try 叠 ≥5 层）
    for row in rows:
        if row:
            for cell in row:
                if cell:
                    while cell:
                        try:
                            return cell
                        except Exception:
                            break
    return None


def duplicate_one(x):
    total = x + 1
    total = total * 2
    total = total - 3
    total = total / 4
    total = total + 5
    total = total * 6
    total = total - 7
    total = total / 8
    # ❌ P1-7 重复块（上面 8 行在这里再来一遍）
    total = x + 1
    total = total * 2
    total = total - 3
    total = total / 4
    total = total + 5
    total = total * 6
    total = total - 7
    total = total / 8
    return total


def create_user(name):
    # create user record  # ❌ P1-9 叙述性注释（下一行把它写进了标识符）
    user = create_user_record(name)
    return user


def create_user_record(name):
    return {"name": name}


# ❌ P2-11 注释掉的代码块
# old_total = compute_total(items)
# if old_total > 0:
#     emit(old_total)

if os.name == "nt":  # end if  # ❌ P2-12 闭合括号标签
    FOO = 1
