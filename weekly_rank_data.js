// Weekly Ranking Data - 2026-05-27 (含感知风控率，共11项，含积分)
const RANKING_DATA = {
  date: "2026-05-27",
  title: "粤闽浙代运营商周排名看板",
  weights: {
    gtv:10, cpc_new:10, cpc_consume:10, mem:10,
    loss:10, fengkong:10,
    work:8, staff:8, score:8, dongxiao:8, bml:8
  },
  thresholds: {
    gtv:         {base:0.75, full:1.00, invert:false},
    cpc_new:     {base:0.70, full:1.00, invert:false},
    cpc_consume: {base:0.75, full:1.00, invert:false},
    mem:         {base:0.60, full:0.85, invert:false},
    loss:        {bad:0.08, good:0.02, invert:true},
    fengkong:    {bad:0.10, good:0.04, invert:true},
    work:        {base:0.80, full:1.00, invert:false},
    staff:       {base:0.85, full:1.10, invert:false},
    score:       {base:0.20, full:0.40, invert:false},
    dongxiao:    {base:0.20, full:0.40, invert:false},
    bml:         {bad:0.40, good:0.10, invert:true}
  },
  operators: [
    { name:"惠州柏万", leader:"林启梁",
      raw:{gtv:0.8676,cpc_new:1.4167,cpc_consume:0.8166,mem:0.6000,loss:0.0316,fengkong:0.0861,work:0.9565,staff:1.286,score:0.3312,dongxiao:0.2838,bml:0.0769},
      cats:{core:{pts:31.0,max:40},health:{pts:10.4,max:20},process:{pts:36.3,max:40},total:77.7},
      metrics:{gtv:{score:79,pts:7.9,rank:1},cpc_new:{score:100,pts:10.0,rank:1},cpc_consume:{score:71,pts:7.1,rank:3},mem:{score:60,pts:6.0,rank:3},loss:{score:81,pts:8.1,rank:3},fengkong:{score:23,pts:2.3,rank:5},work:{score:91,pts:7.3,rank:2},staff:{score:100,pts:8.0,rank:2},score:{score:86,pts:6.9,rank:2},dongxiao:{score:77,pts:6.1,rank:2},bml:{score:100,pts:8.0,rank:2}}
    },
    { name:"惠安广通", leader:"陈昌平",
      raw:{gtv:0.8189,cpc_new:1.1111,cpc_consume:0.8420,mem:0.4750,loss:0.0321,fengkong:0.0387,work:0.9167,staff:1.200,score:0.3002,dongxiao:0.2522,bml:0.3077},
      cats:{core:{pts:29.4,max:40},health:{pts:18.0,max:20},process:{pts:29.2,max:40},total:76.6},
      metrics:{gtv:{score:71,pts:7.1,rank:4},cpc_new:{score:100,pts:10.0,rank:2},cpc_consume:{score:75,pts:7.5,rank:2},mem:{score:48,pts:4.8,rank:5},loss:{score:80,pts:8.0,rank:4},fengkong:{score:100,pts:10.0,rank:1},work:{score:83,pts:6.7,rank:3},staff:{score:100,pts:8.0,rank:4},score:{score:80,pts:6.4,rank:3},dongxiao:{score:70,pts:5.6,rank:4},bml:{score:31,pts:2.5,rank:4}}
    },
    { name:"义乌汐洋", leader:"汪强",
      raw:{gtv:0.8577,cpc_new:0.5625,cpc_consume:0.9048,mem:0.6667,loss:0.0156,fengkong:0.0841,work:0.8889,staff:1.000,score:0.3389,dongxiao:0.2992,bml:0.3333},
      cats:{core:{pts:28.1,max:40},health:{pts:12.7,max:20},process:{pts:28.1,max:40},total:68.9},
      metrics:{gtv:{score:77,pts:7.7,rank:2},cpc_new:{score:48,pts:4.8,rank:6},cpc_consume:{score:85,pts:8.5,rank:1},mem:{score:71,pts:7.1,rank:2},loss:{score:100,pts:10.0,rank:1},fengkong:{score:27,pts:2.7,rank:4},work:{score:78,pts:6.2,rank:4},staff:{score:84,pts:6.7,rank:5},score:{score:88,pts:7.0,rank:1},dongxiao:{score:80,pts:6.4,rank:1},bml:{score:22,pts:1.8,rank:5}}
    },
    { name:"惠州巨浪", leader:"陈少华",
      raw:{gtv:0.7914,cpc_new:0.9333,cpc_consume:0.8131,mem:0.6909,loss:0.0513,fengkong:0.0957,work:0.7391,staff:1.222,score:0.2998,dongxiao:0.2118,bml:0.000},
      cats:{core:{pts:30.3,max:40},health:{pts:5.5,max:20},process:{pts:31.8,max:40},total:67.6},
      metrics:{gtv:{score:67,pts:6.7,rank:6},cpc_new:{score:91,pts:9.1,rank:4},cpc_consume:{score:70,pts:7.0,rank:4},mem:{score:75,pts:7.5,rank:1},loss:{score:48,pts:4.8,rank:6},fengkong:{score:7,pts:0.7,rank:6},work:{score:55,pts:4.4,rank:6},staff:{score:100,pts:8.0,rank:3},score:{score:80,pts:6.4,rank:4},dongxiao:{score:62,pts:5.0,rank:6},bml:{score:100,pts:8.0,rank:1}}
    },
    { name:"慈溪哲光", leader:"陈文飞",
      raw:{gtv:0.8135,cpc_new:1.0625,cpc_consume:0.7874,mem:0.4694,loss:0.0486,fengkong:0.0698,work:0.9677,staff:0.889,score:0.2940,dongxiao:0.2381,bml:0.2857},
      cats:{core:{pts:28.3,max:40},health:{pts:10.2,max:20},process:{pts:27.5,max:40},total:66.0},
      metrics:{gtv:{score:70,pts:7.0,rank:5},cpc_new:{score:100,pts:10.0,rank:3},cpc_consume:{score:66,pts:6.6,rank:5},mem:{score:47,pts:4.7,rank:6},loss:{score:52,pts:5.2,rank:5},fengkong:{score:50,pts:5.0,rank:2},work:{score:94,pts:7.5,rank:1},staff:{score:66,pts:5.3,rank:6},score:{score:79,pts:6.3,rank:5},dongxiao:{score:68,pts:5.4,rank:5},bml:{score:38,pts:3.0,rank:3}}
    },
    { name:"泉州小花猫", leader:"张建华",
      raw:{gtv:0.8369,cpc_new:0.7500,cpc_consume:0.7482,mem:0.4878,loss:0.0271,fengkong:0.0828,work:0.8824,staff:1.714,score:0.2819,dongxiao:0.2652,bml:0.3571},
      cats:{core:{pts:25.0,max:40},health:{pts:11.7,max:20},process:{pts:27.1,max:40},total:63.8},
      metrics:{gtv:{score:74,pts:7.4,rank:3},cpc_new:{score:67,pts:6.7,rank:5},cpc_consume:{score:60,pts:6.0,rank:6},mem:{score:49,pts:4.9,rank:4},loss:{score:88,pts:8.8,rank:2},fengkong:{score:29,pts:2.9,rank:3},work:{score:76,pts:6.1,rank:5},staff:{score:100,pts:8.0,rank:1},score:{score:76,pts:6.1,rank:6},dongxiao:{score:73,pts:5.8,rank:3},bml:{score:14,pts:1.1,rank:6}}
    }
  ]
};
const METRIC_ORDER = ['gtv','cpc_new','cpc_consume','mem','loss','fengkong','work','staff','score','dongxiao','bml'];
