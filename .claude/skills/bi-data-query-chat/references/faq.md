# 常见问题

## Q: 查询返回"没有圈选到任何维度指标"？

**原因**: 账号没有该业务线的指标维度权限，或元数据索引未构建。

**解决方案**:
1. **申请权限** - 联系业务线数据负责人申请指标维度权限
   - 到魔数平台申请数据权限
   - 或联系 HR/数据团队开通
2. **确认业务线** - 确认 bizId 是否正确
3. **等待索引** - 如果是新建数据集，需等待元数据索引构建（通常 T+1）

**提示**: 医药健康 bizId=247，特团 bizId=283，到餐 bizId=325

---

## Q: 查询返回"bizId is required"错误怎么办？

**原因**: 缺少业务线ID参数。

**解决方案**:
1. 确认您有正确的业务线ID（bizId）
2. 联系魔数系统管理员获取业务线ID
3. 确保在查询时传入正确的bizId参数

```bash
# 正确示例
bash scripts/mtbi_query.sh "查询近一周的订单量" 123 "[]"
```

## Q: 查询返回"权限不足"或"无权限访问"怎么办？

**原因**: 账号没有对应业务线或数据集的访问权限。

**解决方案**:
1. 确认您的账号是否有魔数系统访问权限
2. 联系业务线负责人申请数据权限
3. 确认 bizId 是否正确

## Q: 如何获取业务线ID（bizId）？

**方式**:
1. 联系魔数系统管理员
2. 在魔数平台查看业务线配置
3. 咨询数据开发团队

## Q: 认证失败或提示"Authentication required"？

**原因**: CatPaw 沙盒环境需要 CIBA 认证。

**解决方案**:
1. 提供您的 misId（美团工号，如 zhangsan）
2. CatPaw 会发起 CIBA 认证
3. 在大象 App 上确认授权
4. 认证完成后重试

## Q: 大象 App 没有收到授权推送？

**原因**: 通知设置或网络问题。

**解决方案**:
1. 检查大象 App 通知权限是否开启
2. 确认手机网络连接正常
3. 尝试重新发起认证
4. 联系 IT 支持

## Q: 会话过期（Session expired）怎么办？

**原因**: CIBA 认证有效期有限。

**解决方案**:
重新提供 misId 进行 CIBA 认证即可。

## Q: 查询超时怎么办？

**原因**: 查询数据量过大或网络问题。

**解决方案**:
1. 简化查询条件，缩小时间范围
2. 使用数据集ID限定查询范围
3. 避免高峰期查询
4. 稍后重试

## Q: mcporter not found 错误？

**解决方案**:
运行安装脚本：
```bash
# CatPaw 用户
bash ~/.catpaw/skills/bi-data-query-chat/scripts/install_helper.sh -y

# CatClaw 用户
bash ~/.catclaw/skills/bi-data-query-chat/scripts/install_helper.sh -y
```

## Q: Server 'mtbi_ai' not found 错误？

**原因**: MCP 配置文件缺失。

**解决方案**:
检查配置文件：
```bash
cat ~/.mcporter/mcporter.json
```

配置应包含：
```json
{
  "mcpServers": {
    "mtbi_ai": {
      "url": "http://mcphub-server.sankuai.com/mcphub-api/2bdb4741e6e940"
    }
  }
}
```

重新运行安装脚本会自动配置。

## Q: Node.js 版本过低？

**解决方案**:
升级 Node.js 到 18 或更高版本：
```bash
# 使用 nvm
nvm install --lts
nvm use --lts

# 或使用 fnm
fnm install --lts
fnm use --lts
```

## Q: 如何查看可用的数据集ID？

**方式**:
1. 登录魔数平台查看
2. 联系业务线负责人获取
3. 咨询数据开发团队

## Q: 自然语言查询不返回预期结果？

**可能原因**:
1. 查询描述不够清晰
2. 指标名称与系统不匹配
3. 数据集配置问题

**解决方案**:
1. 使用更明确的查询描述
2. 指定具体的数据集ID
3. 联系魔数系统支持确认指标口径
