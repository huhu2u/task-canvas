# Auth And QR

当流程中任意一步出现以下依赖时，直接执行本文件，不需要额外征求用户是否允许开始认证：

- 换票
- MOA
- 浏览器 Cookie
- MissID 获取
- 页面或接口权限要求

## 处理原则

- 不要因为认证依赖而中断整体流程设计
- 不要先问“要不要扫码”
- 直接向用户发送浏览器二维码认证截图，并提醒其在 2 分钟内完成扫码认证
- 如果上传脚本返回“被重定向到登录页”或出现 Cookie/MissID 依赖，也按本文件处理

建议文案：

```text
当前步骤依赖企业认证，请在 2 分钟内完成扫码认证；完成后我会继续后续取数/分析流程。
```

## 图片发送优先级

1. **当前对话环境支持图片消息**
   - 直接发送浏览器二维码认证截图
2. **当前对话环境不支持图片消息**
   - 先把二维码截图保存为本地图片
   - 再运行下面的脚本，把该图片上传为 S3

```bash
python scripts/prepare_analysis_input.py --json ./auth-qr.png --archive-name moa-auth-qr
```

然后把返回的 `s3_url` 作为图片链接发给用户，继续提醒其在 2 分钟内完成扫码认证。

## 扫码后续动作

- 用户完成扫码后，回到刚才被阻塞的步骤继续
- 如果仍失败，记录失败发生在：
  - 换票
  - MOA
  - Cookie
  - MissID
  - 权限校验
- 然后把“现象 + 最短解法”按需沉淀到 `../.bi-analysis-moshu-meta/learnings.md`

本步骤结束后：

- 如果原目标是 MDBI 取数，回到 [mdbi-input.md](mdbi-input.md)
- 如果原目标是正式分析，回到 [analysis-execution.md](analysis-execution.md)
