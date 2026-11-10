# JSON Contract Helpers

[English overview](../README.md) | [中文项目介绍](../README.zh-CN.md)

These helpers are extracted from the Builder's input-handling implementation.
They run with the Python standard library and contain no model calls,
robot-specific parameters, or deployment configuration.

| Function | Purpose |
| --- | --- |
| `loads(text)` | Parse JSON, rejecting duplicate keys and nonfinite constants. |
| `canonical(value)` | Serialize sorted JSON without NaN or infinity. |
| `fields(value, allowed)` | Require an object and reject unsupported keys. |
| `number(value, low, high)` | Require a finite number within inclusive bounds; reject booleans. |
| `choice(value, allowed)` | Require a string from an allowed list. |

The field helper rejects extra fields; required fields are checked by the caller.

From the `examples/` directory:

```python
from json_contract import canonical, fields, loads, number

request = loads('{"label":"example","duration":5}')
fields(request, {"label", "duration"})
duration = number(request["duration"], 1, 60)
print(canonical({"duration": duration, "label": request["label"]}))
```

原始函数来自 Builder 的通用 JSON 处理部分。此处只保留解析、序列化与校验工具，
不含角色参数、模型调用或部署配置。`fields` 检查未知字段，必填字段由调用方检查。

Copyright 2026 Unbound Maker contributors. [Apache-2.0](../LICENSE).
