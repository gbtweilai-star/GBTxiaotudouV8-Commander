/* 由 tools/codex-scripts/rigify-skeleton.py 生成 —— Blender Rigify 标准人形骨架
   手改无效（重生成即覆盖）；来源：Blender rigify human metarig */
window.GBT_RIG = {
 "来源": "Blender Rigify human metarig（专业绑骨件，非手搓）",
 "_blender": "4.2.16 LTS",
 "全高": 1.9796,
 "视图全高": 491.4,
 "骨总数": 159,
 "比例": {
  "髋到足底占全高": 0.5415,
  "膝占全高": 0.72863,
  "踝占全高": 0.95696,
  "肩占全高": 0.19954
 },
 "骨": [
  {
   "n": "pelvis",
   "p": "root",
   "off": [
    0.0,
    0.0
   ],
   "len": -36.59,
   "w": 40,
   "rest": 0.0,
   "side": "C",
   "cn": "髋",
   "head2d": [
    0.0,
    240.71
   ],
   "rigify": "spine"
  },
  {
   "n": "spine",
   "p": "pelvis",
   "off": [
    0.0,
    -36.59
   ],
   "len": -33.66,
   "w": 34,
   "rest": 0.0,
   "side": "C",
   "cn": "脊",
   "head2d": [
    0.0,
    204.12
   ],
   "rigify": "spine.001"
  },
  {
   "n": "chest",
   "p": "spine",
   "off": [
    0.0,
    -33.66
   ],
   "len": -42.89,
   "w": 44,
   "rest": 0.0,
   "side": "C",
   "cn": "胸",
   "head2d": [
    0.0,
    170.46
   ],
   "rigify": "spine.002"
  },
  {
   "n": "neck",
   "p": "chest",
   "off": [
    0.0,
    -90.68
   ],
   "len": -15.27,
   "w": 16,
   "rest": 0.0,
   "side": "C",
   "cn": "颈",
   "head2d": [
    0.0,
    79.78
   ],
   "rigify": "spine.004"
  },
  {
   "n": "head",
   "p": "neck",
   "off": [
    0.0,
    -30.56
   ],
   "len": -49.22,
   "w": 44,
   "rest": 0.0,
   "side": "C",
   "cn": "头",
   "head2d": [
    0.0,
    49.22
   ],
   "rigify": "spine.006"
  },
  {
   "n": "clavicleL",
   "p": "chest",
   "off": [
    4.54,
    -77.5
   ],
   "len": 37.51,
   "w": 14,
   "rest": -89.96,
   "side": "L",
   "cn": "肩(锁骨)",
   "head2d": [
    4.54,
    92.96
   ],
   "rigify": "shoulder.L"
  },
  {
   "n": "upperArmL",
   "p": "clavicleL",
   "off": [
    -5.06,
    43.94
   ],
   "len": 69.95,
   "w": 13,
   "rest": 28.7,
   "side": "L",
   "cn": "上臂",
   "head2d": [
    48.48,
    98.05
   ],
   "rigify": "upper_arm.L"
  },
  {
   "n": "foreArmL",
   "p": "upperArmL",
   "off": [
    0.0,
    69.95
   ],
   "len": 64.51,
   "w": 11,
   "rest": 4.65,
   "side": "L",
   "cn": "前臂",
   "head2d": [
    109.82,
    131.69
   ],
   "rigify": "forearm.L"
  },
  {
   "n": "handL",
   "p": "foreArmL",
   "off": [
    -0.0,
    64.51
   ],
   "len": 19.8,
   "w": 10,
   "rest": 3.26,
   "side": "L",
   "cn": "手",
   "head2d": [
    163.69,
    167.18
   ],
   "rigify": "hand.L"
  },
  {
   "n": "clavicleR",
   "p": "chest",
   "off": [
    -4.54,
    -77.5
   ],
   "len": 37.51,
   "w": 14,
   "rest": 89.96,
   "side": "R",
   "cn": "肩(锁骨)",
   "head2d": [
    -4.54,
    92.96
   ],
   "rigify": "shoulder.R"
  },
  {
   "n": "upperArmR",
   "p": "clavicleR",
   "off": [
    5.06,
    43.94
   ],
   "len": 69.95,
   "w": 13,
   "rest": -28.7,
   "side": "R",
   "cn": "上臂",
   "head2d": [
    -48.48,
    98.05
   ],
   "rigify": "upper_arm.R"
  },
  {
   "n": "foreArmR",
   "p": "upperArmR",
   "off": [
    0.0,
    69.95
   ],
   "len": 64.51,
   "w": 11,
   "rest": -4.65,
   "side": "R",
   "cn": "前臂",
   "head2d": [
    -109.82,
    131.69
   ],
   "rigify": "forearm.R"
  },
  {
   "n": "handR",
   "p": "foreArmR",
   "off": [
    0.0,
    64.51
   ],
   "len": 19.8,
   "w": 10,
   "rest": -3.26,
   "side": "R",
   "cn": "手",
   "head2d": [
    -163.69,
    167.18
   ],
   "rigify": "hand.R"
  },
  {
   "n": "thighL",
   "p": "pelvis",
   "off": [
    24.32,
    -15.42
   ],
   "len": 132.75,
   "w": 22,
   "rest": -0.0,
   "side": "L",
   "cn": "大腿",
   "head2d": [
    24.32,
    225.3
   ],
   "rigify": "thigh.L"
  },
  {
   "n": "shinL",
   "p": "thighL",
   "off": [
    0.0,
    132.75
   ],
   "len": 112.2,
   "w": 18,
   "rest": -0.0,
   "side": "L",
   "cn": "小腿",
   "head2d": [
    24.32,
    358.05
   ],
   "rigify": "shin.L"
  },
  {
   "n": "footL",
   "p": "shinL",
   "off": [
    0.0,
    112.2
   ],
   "len": 17.0,
   "w": 14,
   "rest": -0.0,
   "side": "L",
   "cn": "脚",
   "head2d": [
    24.32,
    470.25
   ],
   "rigify": "foot.L"
  },
  {
   "n": "toeL",
   "p": "footL",
   "off": [
    0.0,
    17.0
   ],
   "len": 0.0,
   "w": 10,
   "rest": -0.0,
   "side": "L",
   "cn": "脚趾",
   "head2d": [
    24.32,
    487.25
   ],
   "rigify": "toe.L"
  },
  {
   "n": "thighR",
   "p": "pelvis",
   "off": [
    -24.32,
    -15.42
   ],
   "len": 132.75,
   "w": 22,
   "rest": -0.0,
   "side": "R",
   "cn": "大腿",
   "head2d": [
    -24.32,
    225.3
   ],
   "rigify": "thigh.R"
  },
  {
   "n": "shinR",
   "p": "thighR",
   "off": [
    0.0,
    132.75
   ],
   "len": 112.2,
   "w": 18,
   "rest": -0.0,
   "side": "R",
   "cn": "小腿",
   "head2d": [
    -24.32,
    358.05
   ],
   "rigify": "shin.R"
  },
  {
   "n": "footR",
   "p": "shinR",
   "off": [
    0.0,
    112.2
   ],
   "len": 17.0,
   "w": 14,
   "rest": -0.0,
   "side": "R",
   "cn": "脚",
   "head2d": [
    -24.32,
    470.25
   ],
   "rigify": "foot.R"
  },
  {
   "n": "toeR",
   "p": "footR",
   "off": [
    0.0,
    17.0
   ],
   "len": 0.0,
   "w": 10,
   "rest": -0.0,
   "side": "R",
   "cn": "脚趾",
   "head2d": [
    -24.32,
    487.25
   ],
   "rigify": "toe.R"
  }
 ]
};
