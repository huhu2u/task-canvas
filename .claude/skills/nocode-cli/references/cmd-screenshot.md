# screenshot 命令详细规则

## screenshot — 截图预览

截图作品渲染页面并自动上传到 S3，返回 S3 URL。

```bash
nocode screenshot <chatId>
nocode screenshot <chatId> --output /tmp/preview.png --width 1440 --height 900
```

**内部流程：** 获取作品 clientId → SSO 换票 → 获取渲染 URL → 截图 → 上传 S3

**自动检查容器状态：** 执行前会自动检查容器状态，如容器已停止会自动触发冷启动（最长等待 5 分钟）。

**输出：** S3 地址 + 可选本地文件路径。

## ⚠️ 使用场景

1. **create 完成后补截图**：`done` 事件中无 `screenshotUrl` 或截图空白时使用
2. **send 完成后查看效果**：修改完成后截图确认效果
3. **独立截图**：随时截取当前状态

## ⚠️ 注意事项

- Playwright 未安装时会报错提示安装
- 截图失败不应阻塞后续流程（如部署）
- 截图返回的是 S3 URL，可直接展示给用户

