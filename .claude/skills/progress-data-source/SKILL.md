---
name: progress-data-source
description: 阿波罗进度数据源参考文档。提供工作计划数据、头号玩家门店业绩数据、门店优惠码数据的获取方法说明。当其他 Skill（如 progress-broadcast）需要了解如何获取工作进度数据、门店业绩数据、门店优惠码数据、或需要查询数据源接口文档时使用。包含：(1) apollo plan sub 命令使用方法，(2) MCP 数据调用方式，(3) 完整字段列表和说明。

metadata:
  skillhub.creator: "chenxianpeng02"
  skillhub.updater: "chenxianpeng02"
  skillhub.version: "V1"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "4614"
---

# 阿波罗进度数据源

## 数据源列表

本 Skill 提供以下三种数据源的获取方法：

1. **工作计划数据**：销售的工作计划、任务信息、完成进度
2. **头号玩家门店业绩**：门店 GTV、订单数、履约率等 76 个业绩字段
3. **门店优惠码**：查询门店的二维码门相关信息

其他 Skill 根据需要选择对应的数据源进行获取。

---

## 1. 工作计划数据

**来源**：`apollo plan sub` 命令

**参数**：

- `日期`（可选）：格式 YYYY-MM-DD，如 `2026-03-12`
- 如果调用方不指定日期，默认使用当天日期

**调用示例**：

```bash
apollo plan sub 2026-03-12
```

**返回数据**：

```json
{
  "success": true,
  "date": "2026-03-12",
  "total": 4,
  "data": [
    {
      "executor": {
        "empId": 46993,
        "name": "杨超",
        "mis": "yangchao09"
      },
      "planProgress": {
        "completedTaskCnt": 0,
        "totalTaskCnt": 2,
        "completedTaskPercent": 0
      },
      "plans": [
        {
          "planId": 79558,
          "shop": {
            "shopId": 527674489,
            "shopName": "千禧造型(美发沙龙)"
          },
          "tasks": [
            {
              "taskId": 25554,
              "taskName": "AI新签邀约拜访",
              "completed": false
            }
          ],
          "visitStatus": 1
        }
      ]
    }
  ]
}
```

**关键字段说明**：

- `data[].executor.mis`: 销售 MIS 账号
- `data[].executor.name`: 销售姓名
- `data[].planProgress.totalTaskCnt`: 总任务数
- `data[].planProgress.completedTaskCnt`: 已完成任务数
- `data[].plans[].shop.shopId`: 门店 ID
- `data[].plans[].tasks[].taskName`: 任务名称
- `data[].plans[].tasks[].completed`: 任务是否完成

---

## 2. 头号玩家门店业绩

**来源**：参考 `friday-mcp` Skill的流程调用 `strategy_touhaowanjia_query` MCP获取数据

**MCP 接入点 URL**：`http://mcphub-server.sankuai.com/mcphub-b/33d39fae2ba242`

**MCP Server Name**：`strategy_touhaowanjia_query`

**tool_name**：`strategy_touhaowanjia_query`

**tool 参数示例**：

```json
{
  "loginId": 22716275,
  "request": {
    "dateType": "daily",
    "params": {
      "partition_date": ["2026-03-10"],
      "dp_shop_id": "511488339"
    },
    "moduleCode": "M464FCDEF",
    "tenantId": "1"
  }
}
```

**参数说明**：

- `loginId`: 用户登录 ID（默认 22716275）
- `request.dateType`: 时间查询类型（默认 "daily"）
- `request.params.partition_date`: 查询日期数组（不指定则默认当天）
- `request.params.dp_shop_id`: 点评门店 ID（没有参数则要求用户指定）
- `request.moduleCode`: 模块 code（固定 "M464FCDEF"）
- `request.tenantId`: 租户 ID（默认 "1"）

**提供字段**：

提供 76 个业绩字段，分为 10 个类别：

- 基础信息（3 个字段）
- 年框信息（15 个字段）
- 经营评分（2 个字段）
- 核销实付 GTV（8 个字段）
- 店转核销 GTV（8 个字段）
- 平台 GTV（12 个字段）
- 流量数据（4 个字段）
- 成交用户（4 个字段）
- 拜访数据（4 个字段）
- ROI 数据（12 个字段）
- 其他（4 个字段）

**完整字段列表**：见 [references/touhaowanjia_fields.md](references/touhaowanjia_fields.md)

---

## 3. 门店优惠码

**来源**：参考 `friday-mcp` Skill的流程调用 `shop_details_query` MCP获取数据

**MCP 接入点 URL**：`http://mcphub-server.sankuai.com/mcphub-b/d35e323597e94d`

**MCP Server Name**：`shop_details_query`

**tool_name**：`qr_men_xiang_query`

**tool 参数示例**：

```json
{
  "loginId": 23231253,
  "request": {
    "dateType": "daily",
    "params": {
      "partition_date": ["2026-03-12"],
      "shop_id": "527674489"
    },
    "moduleCode": "MDA9E8771",
    "tenantId": "1"
  }
}
```

**参数说明**：

- `loginId`: 用户登录 ID（默认 23231253）
- `request.dateType`: 时间查询类型（默认 "daily"）
- `request.params.partition_date`: 查询日期数组（不指定则默认当天）
- `request.params.shop_id`: 点评门店 ID（没有参数则要求用户指定）
- `request.moduleCode`: 模块 code（固定 "MDA9E8771"）
- `request.tenantId`: 租户 ID（默认 "1"）

**提供字段**：

提供 10 个优惠码相关字段，包含 5 个核心指标及其环比数据：

| 字段 Key                                               | 字段名称              | 说明                                                         |
| ------------------------------------------------------ | --------------------- | ------------------------------------------------------------ |
| `qr_user_cnt_real`                                     | 今日优惠码扫码人数    | 当天累计到最新数据更新时间，有过优惠码扫码记录的人数         |
| `qr_user_cnt_real_circle_rate_change_rate`             | 环比                  | 扫码人数环比变化率                                           |
| `qr_order_pk_cnt_real`                                 | 今日优惠码扫码订单量  | 当天累计到最新数据更新时间，用户通过扫优惠码后下单的订单量   |
| `qr_order_pk_cnt_real_circle_rate_change_rate`         | 环比                  | 扫码订单量环比变化率                                         |
| `qr_actual_pay_amt_real`                               | 今日优惠码实付GTV     | 当天累计到最新数据更新时间，用户通过优惠码下单的实际支付金额 |
| `qr_actual_pay_amt_real_circle_rate_change_rate`       | 环比                  | 实付GTV环比变化率                                            |
| `qr_consume_coupon_cnt_real`                           | 今日优惠码核销券数    | 当天累计到最新数据更新时间，用户通过优惠码下单的核销券数     |
| `qr_consume_coupon_cnt_real_circle_rate_change_rate`   | 环比                  | 核销券数环比变化率                                           |
| `qr_actual_pay_share_amt_real`                         | 今日优惠码核销实付GTV | 当天累计到最新数据更新时间，用户核销的实际支付金额           |
| `qr_actual_pay_share_amt_real_circle_rate_change_rate` | 环比                  | 核销实付GTV环比变化率                                        |
