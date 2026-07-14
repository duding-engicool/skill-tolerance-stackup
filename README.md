# 公差叠加与尺寸链（tolerance-stackup）

尺寸链 / 公差叠加计算助手。面向**尺寸 / 工艺工程师**，支持极值法（Worst Case）与统计平方和方法（RSS）计算累积公差，验证装配间隙 / 干涉，定位超差风险并给分配建议。

## 适用场景

- 装配可行性验证（间隙 / 干涉）
- 公差分配（总公差分解到各组成环）
- 超差根因定位（哪一环贡献大）
- 工艺尺寸链评估
- 与 GD&T 标注核对衔接后的叠加验证

## 核心产出

1. **尺寸链计算报告**：封闭环基本尺寸、WC 与 RSS 公差、间隙分布、是否满足要求、超差提示（纯文字版 .txt + Markdown .md）。
2. 计算逻辑内嵌于 `scripts/build_report.py` 的数值计算函数，结果可复核。

## 目录结构

```
tolerance-stackup/
├── SKILL.md            # 技能定义（十大章节 + TRACE 自评）
├── README.md           # 本文件
└── scripts/
    └── build_report.py # 纯文字版 .txt + Markdown .md 计算报告生成器（含 WC/RSS 计算函数 + 内置小样本）
```

## 快速使用

提供尺寸链即可，例如：

> 盖板与壳体装配间隙：壳体高 50±0.20（增环）、垫片 2±0.05（增环）、盖板高 51.5±0.15（减环），要求间隙 0.10~0.60，帮我算 WC 和 RSS。

技能将算出封闭环与两种公差并判断是否满足。

## 生成报告（脚本）

```bash
# 用内置小样本直接跑通，产出示例 纯文字版 .txt + Markdown .md（写入当前工作目录）
python scripts/build_report.py

# 用自定义 JSON 数据生成（写入指定目录）
python scripts/build_report.py input.json --out-dir ./output
```

脚本仅依赖 Python 标准库，内含 `worst_case()` 与 `rss()` 计算函数。JSON 字段说明见 `SKILL.md` 第七节与脚本内 `SCHEMA` 注释。

## 计算方法速览

- 封闭环基本尺寸 `N = Σ(增环) − Σ(减环)`
- 极值法 `T_wc = Σ|Ti|`（最保守，适合安全/法规件）
- 统计法 `T_rss = √(Σ Ti²)`（假设独立近似正态，适合大批量）

## 联动技能

- `gdt-checker`：标注核对后承接几何公差线性叠加
- `process-capability`：结合 Cpk 判断 RSS 假设是否成立
- `fmea-assistant`：超差高风险环纳入 PFMEA
- `special-characteristic-manager`：涉及 CC/SC 的尺寸链重点算

## 边界说明

- 做一维线性尺寸链解析计算，不替代三维公差分析软件（VisVSA 等）与有限元。
- 分布假设非正态时标「待企业补充」；不替代设计/工艺对公差的最终拍板。
