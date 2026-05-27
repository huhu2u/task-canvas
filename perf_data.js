// 绩效看板数据 - 2026-05-27
const PERF_DATA = {
  date: "2026-05-27",

  // 权重配置（可在规则页修改）
  weights: {
    gtv: 15, cpc_new: 5, cpc_consume: 15, mem: 5,
    loss: 10, fengkong: 10,
    work: 8, staff: 8, score: 8, dongxiao: 8, bml: 8
  },

  // 评分阈值
  thresholds: {
    gtv:         { base: 0.75, full: 1.00, invert: false },
    cpc_new:     { base: 0.70, full: 1.00, invert: false },
    cpc_consume: { base: 0.75, full: 1.00, invert: false },
    mem:         { base: 0.60, full: 0.85, invert: false },
    loss:        { bad:  0.08, good: 0.02, invert: true  },
    fengkong:    { bad:  0.10, good: 0.04, invert: true  },
    work:        { base: 0.80, full: 1.00, invert: false },
    staff:       { base: 0.85, full: 1.10, invert: false },
    score:       { base: 0.20, full: 0.40, invert: false },
    dongxiao:    { base: 0.20, full: 0.40, invert: false },
    bml:         { bad:  0.40, good: 0.10, invert: true  }
  },

  // 原始完成率/指标值
  ops: [
    { name: "惠州柏万",  leader: "林启梁",
      raw: { gtv:0.8676, cpc_new:1.4167, cpc_consume:0.8166, mem:0.6000, loss:0.0316, fengkong:0.0861, work:0.9565, staff:1.286, score:0.3312, dongxiao:0.2838, bml:0.0769 },
      monthly: { core:30.4, health:10.4, process:36.3, total:77.2,
        detail:{ gtv:11.8, cpc_new:5.0, cpc_consume:10.6, mem:3.0, loss:8.1, fengkong:2.3, work:7.3, staff:8.0, score:6.9, dongxiao:6.1, bml:8.0 } },
      weekRank: 1, weekAvgRank: 2.4
    },
    { name: "惠安广通",  leader: "陈昌平",
      raw: { gtv:0.8189, cpc_new:1.1111, cpc_consume:0.8420, mem:0.4750, loss:0.0321, fengkong:0.0387, work:0.9167, staff:1.200, score:0.3002, dongxiao:0.2522, bml:0.3077 },
      monthly: { core:29.2, health:18.0, process:29.2, total:76.4,
        detail:{ gtv:10.7, cpc_new:5.0, cpc_consume:11.2, mem:2.4, loss:8.0, fengkong:10.0, work:6.7, staff:8.0, score:6.4, dongxiao:5.6, bml:2.5 } },
      weekRank: 3, weekAvgRank: 3.3
    },
    { name: "义乌汐洋",  leader: "汪强",
      raw: { gtv:0.8577, cpc_new:0.5625, cpc_consume:0.9048, mem:0.6667, loss:0.0156, fengkong:0.0841, work:0.8889, staff:1.000, score:0.3389, dongxiao:0.2992, bml:0.3333 },
      monthly: { core:30.2, health:12.7, process:28.1, total:71.0,
        detail:{ gtv:11.6, cpc_new:2.4, cpc_consume:12.7, mem:3.5, loss:10.0, fengkong:2.6, work:6.2, staff:6.7, score:7.0, dongxiao:6.4, bml:1.8 } },
      weekRank: 2, weekAvgRank: 2.9
    },
    { name: "惠州巨浪",  leader: "陈少华",
      raw: { gtv:0.7914, cpc_new:0.9333, cpc_consume:0.8131, mem:0.6909, loss:0.0513, fengkong:0.0957, work:0.7391, staff:1.222, score:0.2998, dongxiao:0.2118, bml:0.0000 },
      monthly: { core:28.8, health:5.5,  process:31.8, total:66.1,
        detail:{ gtv:10.0, cpc_new:4.6, cpc_consume:10.5, mem:3.7, loss:4.8, fengkong:0.7, work:4.4, staff:8.0, score:6.4, dongxiao:5.0, bml:8.0 } },
      weekRank: 6, weekAvgRank: 4.3
    },
    { name: "慈溪哲光",  leader: "陈文飞",
      raw: { gtv:0.8135, cpc_new:1.0625, cpc_consume:0.7874, mem:0.4694, loss:0.0486, fengkong:0.0698, work:0.9677, staff:0.889, score:0.2940, dongxiao:0.2381, bml:0.2857 },
      monthly: { core:27.8, health:10.3, process:27.5, total:65.6,
        detail:{ gtv:10.5, cpc_new:5.0, cpc_consume:9.9, mem:2.3, loss:5.2, fengkong:5.0, work:7.5, staff:5.3, score:6.3, dongxiao:5.4, bml:3.0 } },
      weekRank: 5, weekAvgRank: 4.2
    },
    { name: "泉州小花猫", leader: "张建华",
      raw: { gtv:0.8369, cpc_new:0.7500, cpc_consume:0.7482, mem:0.4878, loss:0.0271, fengkong:0.0828, work:0.8824, staff:1.714, score:0.2819, dongxiao:0.2652, bml:0.3571 },
      monthly: { core:25.8, health:11.7, process:27.2, total:64.7,
        detail:{ gtv:11.1, cpc_new:3.3, cpc_consume:9.0, mem:2.4, loss:8.8, fengkong:2.9, work:6.1, staff:8.0, score:6.1, dongxiao:5.8, bml:1.1 } },
      weekRank: 4, weekAvgRank: 4.0
    }
  ],

  metricLabels: {
    gtv:"GTV完成率", cpc_new:"CPC新签", cpc_consume:"CPC消耗", mem:"MEM续约",
    loss:"剔除率", fengkong:"感知风控",
    work:"工单闭环", staff:"满编率", score:"经营评分", dongxiao:"好店动销", bml:"BML Lose"
  },

  categories: {
    core:    { label:"核心业绩", color:"#1565c0", keys:["gtv","cpc_new","cpc_consume","mem"] },
    health:  { label:"健康度",   color:"#2e7d32", keys:["loss","fengkong"] },
    process: { label:"过程管理", color:"#6a1b9a", keys:["work","staff","score","dongxiao","bml"] }
  }
};
