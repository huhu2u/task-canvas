// Weekly Ranking Data - 2026-05-27
const RANKING_DATA = {
  date: "2026-05-27",
  title: "粤闽浙代运营商周排名看板",
  // Each operator's metrics and ranks
  operators: [
    {
      name: "惠州柏万",
      rank: 1,
      avgRank: 2.1,
      metrics: {
        gtv: { value: 86.8, rank: 1, unit: "%" },
        cpc_new: { value: 141.7, rank: 1, unit: "%" },
        cpc_consume: { value: 81.7, rank: 3, unit: "%" },
        mem: { value: 60.0, rank: 3, unit: "%" },
        loss_rate: { value: 3.2, rank: 3, unit: "%", inverted: true },
        work_rate: { value: 95.7, rank: 2, unit: "%" },
        staff_rate: { value: 128.6, rank: 2, unit: "%" },
        score_rate: { value: 33.1, rank: 2, unit: "%" },
        dongxiao_rate: { value: 28.4, rank: 2, unit: "%" },
        bml_lose: { value: 7.7, rank: 2, unit: "%", inverted: true }
      }
    },
    {
      name: "义乌汐洋",
      rank: 2,
      avgRank: 2.8,
      metrics: {
        gtv: { value: 85.8, rank: 2, unit: "%" },
        cpc_new: { value: 56.2, rank: 6, unit: "%" },
        cpc_consume: { value: 90.5, rank: 1, unit: "%" },
        mem: { value: 66.7, rank: 2, unit: "%" },
        loss_rate: { value: 1.6, rank: 1, unit: "%", inverted: true },
        work_rate: { value: 88.9, rank: 4, unit: "%" },
        staff_rate: { value: 100.0, rank: 5, unit: "%" },
        score_rate: { value: 33.9, rank: 1, unit: "%" },
        dongxiao_rate: { value: 29.9, rank: 1, unit: "%" },
        bml_lose: { value: 33.3, rank: 5, unit: "%", inverted: true }
      }
    },
    {
      name: "惠安广通",
      rank: 3,
      avgRank: 3.5,
      metrics: {
        gtv: { value: 81.9, rank: 4, unit: "%" },
        cpc_new: { value: 111.1, rank: 2, unit: "%" },
        cpc_consume: { value: 84.2, rank: 2, unit: "%" },
        mem: { value: 47.5, rank: 5, unit: "%" },
        loss_rate: { value: 3.2, rank: 4, unit: "%", inverted: true },
        work_rate: { value: 91.7, rank: 3, unit: "%" },
        staff_rate: { value: 120.0, rank: 4, unit: "%" },
        score_rate: { value: 30.0, rank: 3, unit: "%" },
        dongxiao_rate: { value: 25.2, rank: 4, unit: "%" },
        bml_lose: { value: 30.8, rank: 4, unit: "%", inverted: true }
      }
    },
    {
      name: "惠州巨浪",
      rank: 4,
      avgRank: 4.1,
      metrics: {
        gtv: { value: 79.1, rank: 6, unit: "%" },
        cpc_new: { value: 93.3, rank: 4, unit: "%" },
        cpc_consume: { value: 81.3, rank: 4, unit: "%" },
        mem: { value: 69.1, rank: 1, unit: "%" },
        loss_rate: { value: 5.1, rank: 6, unit: "%", inverted: true },
        work_rate: { value: 73.9, rank: 6, unit: "%" },
        staff_rate: { value: 122.2, rank: 3, unit: "%" },
        score_rate: { value: 30.0, rank: 4, unit: "%" },
        dongxiao_rate: { value: 21.2, rank: 6, unit: "%" },
        bml_lose: { value: 0.0, rank: 1, unit: "%", inverted: true }
      }
    },
    {
      name: "泉州小花猫",
      rank: 5,
      avgRank: 4.1,
      metrics: {
        gtv: { value: 83.7, rank: 3, unit: "%" },
        cpc_new: { value: 75.0, rank: 5, unit: "%" },
        cpc_consume: { value: 74.8, rank: 6, unit: "%" },
        mem: { value: 48.8, rank: 4, unit: "%" },
        loss_rate: { value: 2.7, rank: 2, unit: "%", inverted: true },
        work_rate: { value: 88.2, rank: 5, unit: "%" },
        staff_rate: { value: 171.4, rank: 1, unit: "%" },
        score_rate: { value: 28.2, rank: 6, unit: "%" },
        dongxiao_rate: { value: 26.5, rank: 3, unit: "%" },
        bml_lose: { value: 35.7, rank: 6, unit: "%", inverted: true }
      }
    },
    {
      name: "慈溪哲光",
      rank: 6,
      avgRank: 4.4,
      metrics: {
        gtv: { value: 81.3, rank: 5, unit: "%" },
        cpc_new: { value: 106.2, rank: 3, unit: "%" },
        cpc_consume: { value: 78.7, rank: 5, unit: "%" },
        mem: { value: 46.9, rank: 6, unit: "%" },
        loss_rate: { value: 4.9, rank: 5, unit: "%", inverted: true },
        work_rate: { value: 96.8, rank: 1, unit: "%" },
        staff_rate: { value: 88.9, rank: 6, unit: "%" },
        score_rate: { value: 29.4, rank: 5, unit: "%" },
        dongxiao_rate: { value: 23.8, rank: 5, unit: "%" },
        bml_lose: { value: 28.6, rank: 3, unit: "%", inverted: true }
      }
    }
  ],
  // Scoring weights
  weights: {
    core: { label: "核心业绩", weight: 40, metrics: ["gtv", "cpc_new", "cpc_consume", "mem"] },
    health: { label: "健康度", weight: 20, metrics: ["loss_rate"] },
    process: { label: "过程管理", weight: 40, metrics: ["work_rate", "staff_rate", "score_rate", "dongxiao_rate", "bml_lose"] }
  }
};
