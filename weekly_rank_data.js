// Weekly Ranking Data - 2026-05-27 (含感知风控率，共11项)
const RANKING_DATA = {
  date: "2026-05-27",
  title: "粤闽浙代运营商周排名看板",
  operators: [
    {
      name: "惠州柏万", rank: 1, avgRank: 2.4,
      highlights: ["GTV第1","CPC新签第1","多项前三"],
      weaknesses: ["感知风控第5"],
      metrics: {
        gtv:          { label:"GTV",       value:86.8,  rank:1, unit:"%", inverted:false },
        cpc_new:      { label:"CPC新签",   value:141.7, rank:1, unit:"%", inverted:false },
        cpc_consume:  { label:"CPC消耗",   value:81.7,  rank:3, unit:"%", inverted:false },
        mem:          { label:"MEM续约",   value:60.0,  rank:3, unit:"%", inverted:false },
        loss_rate:    { label:"剔除率",    value:3.2,   rank:3, unit:"%", inverted:true  },
        fengkong:     { label:"感知风控",  value:8.61,  rank:5, unit:"%", inverted:true  },
        work_rate:    { label:"工单闭环",  value:95.7,  rank:2, unit:"%", inverted:false },
        staff_rate:   { label:"满编率",    value:128.6, rank:2, unit:"%", inverted:false },
        score_rate:   { label:"经营评分",  value:33.1,  rank:2, unit:"%", inverted:false },
        dongxiao:     { label:"好店动销",  value:28.4,  rank:2, unit:"%", inverted:false },
        bml_lose:     { label:"BML Lose",  value:7.7,   rank:2, unit:"%", inverted:true  }
      }
    },
    {
      name: "义乌汐洋", rank: 2, avgRank: 2.9,
      highlights: ["剔除率最低","经营评分第1","动销第1"],
      weaknesses: ["CPC新签第6","满编率第5"],
      metrics: {
        gtv:          { label:"GTV",       value:85.8,  rank:2, unit:"%", inverted:false },
        cpc_new:      { label:"CPC新签",   value:56.2,  rank:6, unit:"%", inverted:false },
        cpc_consume:  { label:"CPC消耗",   value:90.5,  rank:1, unit:"%", inverted:false },
        mem:          { label:"MEM续约",   value:66.7,  rank:2, unit:"%", inverted:false },
        loss_rate:    { label:"剔除率",    value:1.6,   rank:1, unit:"%", inverted:true  },
        fengkong:     { label:"感知风控",  value:8.41,  rank:4, unit:"%", inverted:true  },
        work_rate:    { label:"工单闭环",  value:88.9,  rank:4, unit:"%", inverted:false },
        staff_rate:   { label:"满编率",    value:100.0, rank:5, unit:"%", inverted:false },
        score_rate:   { label:"经营评分",  value:33.9,  rank:1, unit:"%", inverted:false },
        dongxiao:     { label:"好店动销",  value:29.9,  rank:1, unit:"%", inverted:false },
        bml_lose:     { label:"BML Lose",  value:33.3,  rank:5, unit:"%", inverted:true  }
      }
    },
    {
      name: "惠安广通", rank: 3, avgRank: 3.3,
      highlights: ["感知风控最优","CPC相关前3"],
      weaknesses: ["MEM续约第5","动销第4"],
      metrics: {
        gtv:          { label:"GTV",       value:81.9,  rank:4, unit:"%", inverted:false },
        cpc_new:      { label:"CPC新签",   value:111.1, rank:2, unit:"%", inverted:false },
        cpc_consume:  { label:"CPC消耗",   value:84.2,  rank:2, unit:"%", inverted:false },
        mem:          { label:"MEM续约",   value:47.5,  rank:5, unit:"%", inverted:false },
        loss_rate:    { label:"剔除率",    value:3.2,   rank:4, unit:"%", inverted:true  },
        fengkong:     { label:"感知风控",  value:3.87,  rank:1, unit:"%", inverted:true  },
        work_rate:    { label:"工单闭环",  value:91.7,  rank:3, unit:"%", inverted:false },
        staff_rate:   { label:"满编率",    value:120.0, rank:4, unit:"%", inverted:false },
        score_rate:   { label:"经营评分",  value:30.0,  rank:3, unit:"%", inverted:false },
        dongxiao:     { label:"好店动销",  value:25.2,  rank:4, unit:"%", inverted:false },
        bml_lose:     { label:"BML Lose",  value:30.8,  rank:4, unit:"%", inverted:true  }
      }
    },
    {
      name: "泉州小花猫", rank: 4, avgRank: 4.0,
      highlights: ["满编率第1","剔除率第2"],
      weaknesses: ["CPC消耗第6","经营评分第6","BML第6"],
      metrics: {
        gtv:          { label:"GTV",       value:83.7,  rank:3, unit:"%", inverted:false },
        cpc_new:      { label:"CPC新签",   value:75.0,  rank:5, unit:"%", inverted:false },
        cpc_consume:  { label:"CPC消耗",   value:74.8,  rank:6, unit:"%", inverted:false },
        mem:          { label:"MEM续约",   value:48.8,  rank:4, unit:"%", inverted:false },
        loss_rate:    { label:"剔除率",    value:2.7,   rank:2, unit:"%", inverted:true  },
        fengkong:     { label:"感知风控",  value:8.28,  rank:3, unit:"%", inverted:true  },
        work_rate:    { label:"工单闭环",  value:88.2,  rank:5, unit:"%", inverted:false },
        staff_rate:   { label:"满编率",    value:171.4, rank:1, unit:"%", inverted:false },
        score_rate:   { label:"经营评分",  value:28.2,  rank:6, unit:"%", inverted:false },
        dongxiao:     { label:"好店动销",  value:26.5,  rank:3, unit:"%", inverted:false },
        bml_lose:     { label:"BML Lose",  value:35.7,  rank:6, unit:"%", inverted:true  }
      }
    },
    {
      name: "慈溪哲光", rank: 5, avgRank: 4.2,
      highlights: ["工单闭环第1","感知风控第2"],
      weaknesses: ["MEM续约第6","满编率第6","BML第3"],
      metrics: {
        gtv:          { label:"GTV",       value:81.3,  rank:5, unit:"%", inverted:false },
        cpc_new:      { label:"CPC新签",   value:106.2, rank:3, unit:"%", inverted:false },
        cpc_consume:  { label:"CPC消耗",   value:78.7,  rank:5, unit:"%", inverted:false },
        mem:          { label:"MEM续约",   value:46.9,  rank:6, unit:"%", inverted:false },
        loss_rate:    { label:"剔除率",    value:4.9,   rank:5, unit:"%", inverted:true  },
        fengkong:     { label:"感知风控",  value:6.98,  rank:2, unit:"%", inverted:true  },
        work_rate:    { label:"工单闭环",  value:96.8,  rank:1, unit:"%", inverted:false },
        staff_rate:   { label:"满编率",    value:88.9,  rank:6, unit:"%", inverted:false },
        score_rate:   { label:"经营评分",  value:29.4,  rank:5, unit:"%", inverted:false },
        dongxiao:     { label:"好店动销",  value:23.8,  rank:5, unit:"%", inverted:false },
        bml_lose:     { label:"BML Lose",  value:28.6,  rank:3, unit:"%", inverted:true  }
      }
    },
    {
      name: "惠州巨浪", rank: 6, avgRank: 4.3,
      highlights: ["MEM续约第1","BML最佳"],
      weaknesses: ["GTV第6","感知风控第6","工单闭环第6","动销第6"],
      metrics: {
        gtv:          { label:"GTV",       value:79.1,  rank:6, unit:"%", inverted:false },
        cpc_new:      { label:"CPC新签",   value:93.3,  rank:4, unit:"%", inverted:false },
        cpc_consume:  { label:"CPC消耗",   value:81.3,  rank:4, unit:"%", inverted:false },
        mem:          { label:"MEM续约",   value:69.1,  rank:1, unit:"%", inverted:false },
        loss_rate:    { label:"剔除率",    value:5.1,   rank:6, unit:"%", inverted:true  },
        fengkong:     { label:"感知风控",  value:9.57,  rank:6, unit:"%", inverted:true  },
        work_rate:    { label:"工单闭环",  value:73.9,  rank:6, unit:"%", inverted:false },
        staff_rate:   { label:"满编率",    value:122.2, rank:3, unit:"%", inverted:false },
        score_rate:   { label:"经营评分",  value:30.0,  rank:4, unit:"%", inverted:false },
        dongxiao:     { label:"好店动销",  value:21.2,  rank:6, unit:"%", inverted:false },
        bml_lose:     { label:"BML Lose",  value:0.0,   rank:1, unit:"%", inverted:true  }
      }
    }
  ]
};

const METRIC_ORDER = ['gtv','cpc_new','cpc_consume','mem','loss_rate','fengkong','work_rate','staff_rate','score_rate','dongxiao','bml_lose'];
