# deploy 命令详细规则

## deploy — 部署应用

部署应用到线上。自动从版本列表获取最新版本的 commitId 进行部署，也可通过 `--commit-id` 指定版本。

```bash
nocode deploy <chatId>                           # 部署最新版本
nocode deploy <chatId> --commit-id <commitId>    # 部署指定版本
```

**流程：**
1. 获取版本列表（`getVersions`）
2. 使用最新版本的 commitId（或用户指定的 commitId）
3. 检查最新版本渲染状态，渲染失败则中止部署并报错
4. 调用部署 API（`deploy`）

**注意：** 部署不需要容器运行，只需要有效的 commitId。

## ⚠️ 渲染失败拦截

如果最新版本渲染失败（`renderStatus === false`），CLI 会直接报错中止：

```
最新版本 (xxxxxxxx) 渲染失败，无法部署。请进入对话查看异常渲染情况，有问题请联系 NoCode 研发协助处理
```

**⛔ 遇到此错误时，严禁自行尝试修复（如尝试通过 `nocode send` 修复渲染问题、反复重试部署等）。** 必须立即停止操作，引导用户联系 NoCode 研发排查处理。

## ⚠️ 最终展示格式（强制）

部署成功后，向用户展示地址时，使用 Markdown 格式链接：

```
"✅ 部署成功！\n链接: [{externalUrl}]({externalUrl})"
```

## ⚠️ 常见错误

| 错误信息 | 处理方式 |
|---------|---------|
| `暂无可部署版本` | 先执行创建或修改命令生成代码 |
| `最新版本渲染失败，无法部署` | **⛔ 禁止自行修复**，引导用户联系 NoCode 研发排查处理 |
| `指定的版本不存在` | 使用 `nocode versions <chatId>` 查看可用版本 |

