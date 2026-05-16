# 输出格式参考

## 基础格式

```json
{
  "data": [{"date": "2026-03-01", "value": 1234}],
  "meta": {"query_time": "2026-03-10 10:30:00"}
}
```

## 多指标维度格式

### 方案A: 分别展示
```json
{
  "analysis_type": "separate_metrics",
  "results": [
    {"metric": "GMV", "data": [{"city": "北京", "value": 1234}]},
    {"metric": "订单量", "data": [{"city": "北京", "value": 567}]}
  ]
}
```

### 方案B: 合并展示
```json
{
  "analysis_type": "combined_metrics",
  "data": [
    {"city": "北京", "gmv": 1234, "order_count": 567}
  ],
  "meta": {"metrics": ["GMV", "订单量"], "dimensions": ["城市"]}
}
```

### 方案C: 主次维度
```json
{
  "analysis_type": "primary_secondary_dims",
  "primary_dimension": "城市",
  "secondary_dimension": "品类",
  "data": [
    {"city": "北京", "details": [{"category": "餐饮", "gmv": 1234}]}
  ]
}
```
