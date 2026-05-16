# create 命令 — Agent 实时进度推送详细流程

## Poll 循环示意图

```
用户 ──"帮我创建一个TODO应用"──→ Agent
  │
  ├─ exec(background=true): nocode create "TODO应用" → pid
  │
  ├─ [poll 第1轮, timeout=15s]
  │   ├─ 读到: {"type":"progress","step":1,"message":"正在创建应用并发起 AI 生成..."}
  │   └─ 立即推送用户："⏳ 正在创建应用并发起 AI 生成..."
  │
  ├─ [poll 第2轮, timeout=15s]
  │   ├─ 读到: {"type":"progress","step":2,"message":"AI 正在生成页面..."}
  │   ├─ 读到: {"type":"ai_text","delta":"好的，我来帮你..."}（忽略）
  │   └─ 立即推送用户："⏳ AI 正在生成页面..."
  │
  ├─ [poll 第3~N轮, timeout=15s]  ← AI 生成中，持续 poll
  │   └─ 读到 ai_text 事件（忽略，继续 poll）
  │
  ├─ [poll 第N+1轮, timeout=15s]
  │   ├─ 读到: {"type":"progress","step":3,"message":"等待渲染就绪..."}
  │   └─ 立即推送用户："⏳ 等待渲染就绪..."
  │
  ├─ [poll 第N+2轮, timeout=15s]
  │   ├─ 读到: {"type":"progress","step":4,"message":"正在截图预览..."}
  │   └─ 立即推送用户："⏳ 正在截图预览..."
  │
  └─ [poll 最后一轮]
      ├─ 读到: {"type":"done","status":"success","chatId":"abc-123","chatUrl":"https://...","screenshotUrl":"https://s3-xxx/..."}
      ├─ 立即推送用户："✅ 创建完成！"
      ├─ 立即推送用户："🔗 [abc-123](https://nocode.sankuai.com/...)"
      └─ 展示截图（如有 screenshotUrl，不展示 renderUrl）
```

## NDJSON 示例输出

每行一个 JSON：

```
{"type":"progress","step":1,"total":4,"message":"正在创建应用并发起 AI 生成..."}
{"type":"progress","step":2,"total":4,"message":"AI 正在生成页面..."}
{"type":"ai_text","delta":"好的，我来帮你创建一个 TODO 应用。\n\n"}
{"type":"ai_text","delta":"首先，我们需要..."}
{"type":"tool_call","toolName":"create_file"}
{"type":"progress","step":3,"total":4,"message":"等待渲染就绪..."}
{"type":"progress","step":3,"total":4,"message":"渲染就绪","data":{"renderUrl":"https://sandbox-xxx.sankuai.com/..."}}
{"type":"progress","step":4,"total":4,"message":"正在截图预览..."}
{"type":"done","status":"success","chatId":"abc-123","chatUrl":"https://...","renderUrl":"https://...","screenshotUrl":"https://s3-xxx/abc-123.png","aiResponse":"完整AI响应文本...","totalDuration":48000}
```
