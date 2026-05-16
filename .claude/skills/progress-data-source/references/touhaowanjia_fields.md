# 头号玩家门店数据字段列表

本文档列出了通过 `strategy_touhaowanjia_query` MCP 服务可获取的所有字段。

## 基础信息

- `shop_name`: 门店名称
- `employee_name`: 销售名称
- `dp_shop_id`: 点评门店 ID

## 年框信息

- `annualframe_activity_id`: 框架 ID
- `annualframe_rule_begin_date`: 年框开始日期
- `annualframe_rule_end_date`: 年框结束日期
- `return_ration_value`: 返佣比例
- `return_ration_value_circle_rate_change_val`: 返佣比例环比
- `annualframe_higher_gtv_target_gov`: 最大签框目标
- `annualframe_higher_gtv_target_gov_circle_rate_change_rate`: 最大签框目标环比
- `annualframe_complete_share_shop_gtv`: 剔风控年框累计结算 GTV
- `annualframe_complete_share_shop_gtv_circle_rate_change_rate`: 剔风控年框累计结算 GTV 环比
- `annualframe_complete_gtv_m`: 本月剔风控年框结算 GTV
- `annualframe_complete_gtv_m_circle_rate_change_rate`: 本月剔风控年框结算 GTV 环比
- `annualframe_complete_gtv_rate`: 年框履约达成率
- `annualframe_complete_gtv_rate_circle_rate_change_val`: 年框履约达成率环比
- `annualframe_time_progress_new`: 年框履约进度（新）
- `annualframe_time_progress_new_circle_rate_change_val`: 年框履约进度环比

## 经营评分

- `business_total_score`: 经营评分分数
- `business_total_score_circle_rate_change_rate`: 经营评分环比

## 核销实付 GTV

- `month_consume_actual_pay_gtv`: 本月核销实付 GTV
- `month_consume_actual_pay_gtv_circle_rate_change_rate`: 本月核销实付 GTV 环比
- `consume_actual_pay_gtv_l1m`: 上月核销实付 GTV
- `consume_actual_pay_gtv_l1m_circle_rate_change_rate`: 上月核销实付 GTV 环比
- `month_excl_risk_consume_actual_pay_gtv`: 本月剔风控核销实付 GTV
- `month_excl_risk_consume_actual_pay_gtv_circle_rate_change_rate`: 本月剔风控核销实付 GTV 环比
- `excl_risk_consume_actual_pay_gtv_l1m`: 上月剔风控核销实付 GTV
- `excl_risk_consume_actual_pay_gtv_l1m_circle_rate_change_rate`: 上月剔风控核销实付 GTV 环比

## 店转核销 GTV

- `month_tran_excl_risk_consume_actual_pay_gtv`: 本月剔风控店转核销实付 GTV
- `month_tran_excl_risk_consume_actual_pay_gtv_circle_rate_change_rate`: 本月剔风控店转核销实付 GTV 环比
- `excl_tran_risk_consume_actual_pay_gtv_l1m`: 上月剔风控店转核销实付 GTV
- `excl_tran_risk_consume_actual_pay_gtv_l1m_circle_rate_change_rate`: 上月剔风控店转核销实付 GTV 环比
- `month_tran_excl_risk_consume_order_cnt`: 本月剔风控店转核销实付订单量
- `month_tran_excl_risk_consume_order_cnt_circle_rate_change_rate`: 本月剔风控店转核销实付订单量环比
- `month_tran_excl_risk_consume_actual_pay_gtv_avg_price`: 本月剔风控店转核销实付订单均价
- `month_tran_excl_risk_consume_actual_pay_gtv_avg_price_circle_rate_change_rate`: 本月剔风控店转核销实付订单均价环比

## 平台 GTV

- `month_mt_actual_pay_gtv`: 本月美团实付 GTV
- `month_mt_actual_pay_gtv_circle_rate_change_rate`: 本月美团实付 GTV 环比
- `mt_actual_pay_gtv_l1m`: 上月美团实付 GTV
- `mt_actual_pay_gtv_l1m_circle_rate_change_rate`: 上月美团实付 GTV 环比
- `dj_buy_suc_actual_pay_gtv_m`: 本月 D+ 实付 GTV
- `dj_buy_suc_actual_pay_gtv_m_circle_rate_change_rate`: 本月 D+ 实付 GTV 环比
- `dj_actual_pay_gtv_l1m`: 上月 D+ 实付 GTV
- `dj_actual_pay_gtv_l1m_circle_rate_change_rate`: 上月 D+ 实付 GTV 环比
- `month_dj_mt_actual_pay_gtv`: 本月双侧实付 GTV
- `month_dj_mt_actual_pay_gtv_circle_rate_change_rate`: 本月双侧实付 GTV 环比
- `dj_mt_actual_pay_gtv_l1m`: 上月双侧实付 GTV
- `dj_mt_actual_pay_gtv_l1m_circle_rate_change_rate`: 上月双侧实付 GTV 环比

## 流量数据

- `month_intend_uv_avg`: 本月日均意向页面曝光 UV
- `month_intend_uv_avg_circle_rate_change_rate`: 本月日均意向页面曝光 UV 环比
- `intend_uv_avg_l1m`: 上月日均意向页面曝光 UV
- `intend_uv_avg_l1m_circle_rate_change_rate`: 上月日均意向页面曝光 UV 环比

## 成交用户

- `excl_risk_mtu`: 本月剔风控成交用户数
- `excl_risk_mtu_circle_rate_change_rate`: 本月剔风控成交用户数环比
- `excl_risk_mtu_l1m`: 上月剔风控成交用户数
- `excl_risk_mtu_l1m_circle_rate_change_rate`: 上月剔风控成交用户数环比

## 拜访数据

- `month_valid_visit_cnt`: 本月有效拜访次数
- `month_valid_visit_cnt_circle_rate_change_rate`: 本月有效拜访次数环比
- `valid_visit_cnt_l1m`: 上月有效拜访次数
- `valid_visit_cnt_l1m_circle_rate_change_rate`: 上月有效拜访次数环比

## ROI 数据

- `zf_annualframe_income`: 签框增量收入
- `zf_annualframe_income_circle_rate_change_rate`: 签框增量收入环比
- `zf_annualframe_cost`: 签框投入成本
- `zf_annualframe_cost_circle_rate_change_rate`: 签框投入成本环比
- `zf_annualframe_income_roi`: 签框 ROI
- `zf_annualframe_income_roi_circle_rate_change_rate`: 签框 ROI 环比
- `zf_fulfillment_annualframe_income`: 履约增量收入
- `zf_fulfillment_annualframe_income_circle_rate_change_rate`: 履约增量收入环比
- `zf_fulfillment_annualframe_cost`: 履约增量成本
- `zf_fulfillment_annualframe_cost_circle_rate_change_rate`: 履约增量成本环比
- `zf_fulfillment_annualframe_income_roi`: 履约 ROI
- `zf_fulfillment_annualframe_income_roi_circle_rate_change_rate`: 履约 ROI 环比

## 其他

- `zf_annualframe_commission_base_amt`: 计佣金额累计
- `zf_annualframe_commission_base_amt_circle_rate_change_rate`: 计佣金额累计环比
- `zf_annualframe_onlineoff_cnt`: 上下框次数
- `zf_annualframe_onlineoff_cnt_circle_rate_change_rate`: 上下框次数环比
