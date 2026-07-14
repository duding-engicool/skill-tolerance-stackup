# -*- coding: utf-8 -*-
"""
公差叠加 / 尺寸链 —— 计算报告生成器（纯文字版 .txt + Markdown .md）

功能：将 Agent 从用户处抽取并结构化的尺寸链数据，
      用极值法（WC）与统计平方和方法（RSS）计算封闭环累积公差，
      对比装配间隙/干涉要求，渲染为纯文字版 + Markdown 版报告。

输入：JSON 文件（由 Agent 产出，字段见下方 SCHEMA）；不传参时自动使用内置小样本。
输出：纯文字版（.txt）与 Markdown（.md），默认写入当前工作目录（可用 --out-dir 指定）。

设计原则：
- 仅用 Python 标准库（json / sys / os / argparse / math / datetime），无外部依赖
- 所有字段均可缺省，缺失时给合理占位，不崩溃

JSON SCHEMA：
{
  "title": str,                       # 计算主题
  "date": str,                        # 编制日期 YYYY-MM-DD
  "closed_loop": str,                 # 封闭环名称（如 装配间隙 G）
  "requirement": {                    # 装配要求（缺失标待补充）
    "type": "间隙"|"干涉"|"其他",
    "min": float, "max": float
  },
  "chains": [                         # 组成环（tol 为 ± 半幅公差）
    {"name": str, "nominal": float, "tol": float, "dir": "增环"|"减环"}
  ],
  "gaps": [str]                       # 待企业补充
}

注：tol 表示各环的 ± 半幅公差（如 50±0.20 则 tol=0.20）。
    WC 半幅 = Σ|tol_i|；RSS 半幅 = √(Σ tol_i²)；封闭环 = Σ增环 − Σ减环。

运行：
  python build_report.py                        # 用内置小样本，产出 公差叠加尺寸链报告_YYYYMMDD.txt/.md
  python build_report.py input.json --out-dir ./out   # 用 input.json，写入 ./out
"""

import json
import sys
import os
import math
import argparse
from datetime import datetime


# ---------- 计算函数 ----------
def closed_nominal(chains):
    """封闭环基本尺寸 = Σ增环 nominal − Σ减环 nominal"""
    n = 0.0
    for c in chains:
        nominal = float(c.get("nominal", 0) or 0)
        direction = str(c.get("dir", "")).strip()
        if direction == "减环":
            n -= nominal
        else:
            n += nominal  # 增环（默认）
    return n


def worst_case_half(chains):
    """WC 半幅 = Σ|tol_i|（各环同时取最不利极限）"""
    return sum(abs(float(c.get("tol", 0) or 0)) for c in chains)


def rss_half(chains):
    """RSS 半幅 = √(Σ tol_i²)（假设各环独立、近似正态）"""
    return math.sqrt(sum((float(c.get("tol", 0) or 0)) ** 2 for c in chains))


def gap_range(nominal, half):
    """对称假设下间隙范围 [nominal-half, nominal+half]"""
    return nominal - half, nominal + half


def check_requirement(lo, hi, req):
    """判断 [lo,hi] 是否满足要求 [min,max]；req 缺失返回 None（待补充）"""
    if not isinstance(req, dict):
        return None
    rmin = req.get("min")
    rmax = req.get("max")
    if rmin is None or rmax is None:
        return None
    ok = (lo >= float(rmin)) and (hi <= float(rmax))
    return ok


# ---------- 内置小样本 ----------
SAMPLE = {
    "title": "盖板与壳体装配间隙",
    "date": "2026-07-13",
    "closed_loop": "装配间隙 G",
    "requirement": {"type": "间隙", "min": 0.10, "max": 0.60},
    "chains": [
        {"name": "壳体高度 H1", "nominal": 50.0, "tol": 0.20, "dir": "增环"},
        {"name": "垫片厚 T", "nominal": 2.0, "tol": 0.05, "dir": "增环"},
        {"name": "盖板高 H2", "nominal": 51.5, "tol": 0.15, "dir": "减环"}
    ],
    "gaps": [
        "各环实际分布是否近似正态（RSS 假设成立性以过程能力 Cpk 验证，待企业补充）"
    ]
}


# ---------- 工具函数 ----------
def get(d, key, default=None):
    return d.get(key, default) if isinstance(d, dict) else default


def get_list(d, key):
    v = get(d, key, [])
    return v if isinstance(v, list) else []


def esc(v):
    return "" if v is None else str(v)


def fmt(x):
    try:
        return f"{float(x):.3f}"
    except Exception:
        return esc(x)


def date_tag_of(data):
    raw = esc(get(data, "date")) or datetime.now().strftime("%Y-%m-%d")
    return raw.replace("-", "")


# ---------- Markdown 渲染 ----------
def render_md(data):
    title = esc(get(data, "title")) or "（未填写）"
    date = esc(get(data, "date")) or datetime.now().strftime("%Y-%m-%d")
    closed = esc(get(data, "closed_loop")) or "封闭环"
    req = get(data, "requirement")
    chains = get_list(data, "chains")

    N = closed_nominal(chains)
    wc = worst_case_half(chains)
    rs = rss_half(chains)
    wc_lo, wc_hi = gap_range(N, wc)
    rs_lo, rs_hi = gap_range(N, rs)

    wc_ok = check_requirement(wc_lo, wc_hi, req)
    rs_ok = check_requirement(rs_lo, rs_hi, req)

    req_str = "（待补充）"
    if isinstance(req, dict):
        rmin = req.get("min")
        rmax = req.get("max")
        rtype = esc(req.get("type")) or "间隙"
        if rmin is not None and rmax is not None:
            req_str = f"{rtype}要求：[{fmt(rmin)}, {fmt(rmax)}]"

    L = []
    L.append("# 公差叠加 / 尺寸链计算报告")
    L.append("")
    L.append(f"**主题**：{title}")
    L.append(f"**编制日期**：{date}")
    L.append(f"**封闭环**：{closed}")
    L.append(f"**装配要求**：{req_str}")
    L.append("> 本报告为计算建议稿，最终公差定版由设计/工艺责任人确认。")
    L.append("")

    L.append("## 一、尺寸链（组成环）")
    L.append("")
    L.append("| 环 | 名称 | 基本尺寸 | ±公差(半幅) | 方向 |")
    L.append("|----|------|----------|-------------|------|")
    if chains:
        for i, c in enumerate(chains, 1):
            L.append(
                f"| {i} | {esc(get(c, 'name'))} | {fmt(get(c, 'nominal'))} | "
                f"{fmt(get(c, 'tol'))} | {esc(get(c, 'dir')) or '增环'} |"
            )
    else:
        L.append("| - | 暂无组成环（待补充） | - | - | - |")
    L.append("")

    L.append("## 二、计算过程")
    L.append("")
    L.append(f"- 封闭环基本尺寸 `N = Σ增环 − Σ减环 = {fmt(N)}`")
    L.append(f"- 极值法（WC）半幅 `T_wc = Σ|tol_i| = {fmt(wc)}`")
    L.append(f"- 统计法（RSS）半幅 `T_rss = √(Σ tol_i²) = {fmt(rs)}`")
    L.append("")

    L.append("## 三、结果对比")
    L.append("")
    L.append("| 方法 | 间隙下限 | 间隙上限 | 是否满足要求 |")
    L.append("|------|----------|----------|--------------|")
    wc_mark = "满足" if wc_ok else ("不满足" if wc_ok is False else "待补充要求")
    rs_mark = "满足" if rs_ok else ("不满足" if rs_ok is False else "待补充要求")
    L.append(f"| 极值法 WC | {fmt(wc_lo)} | {fmt(wc_hi)} | {wc_mark} |")
    L.append(f"| 统计法 RSS | {fmt(rs_lo)} | {fmt(rs_hi)} | {rs_mark} |")
    L.append("")

    L.append("## 四、超差提示与建议")
    L.append("")
    if wc_ok is False or rs_ok is False:
        L.append("- 当前链在某方法下超出装配要求，建议：")
        contrib = sorted(chains, key=lambda c: abs(float(c.get("tol", 0) or 0)), reverse=True)
        if contrib:
            top = contrib[0]
            L.append(
                f"  - 贡献最大的环：**{esc(get(top, 'name'))}**（±{fmt(get(top, 'tol'))}），"
                f"优先评估是否可收紧或提升工艺能力。"
            )
        L.append("  - 若批量大且过程受控，可采信 RSS 放宽要求；安全/法规件须按 WC 控制。")
        L.append("  - 必要时做公差分配：按等公差法或工艺能力加权重新分配各环公差。")
    else:
        L.append("- 当前两种方法的间隙均在要求范围内，装配可行。仍建议结合 Cpk 验证 RSS 假设。")
    L.append("")

    gaps = get_list(data, "gaps")
    if gaps:
        L.append("## 五、待企业补充 / 待确认")
        L.append("")
        for i, g in enumerate(gaps, 1):
            L.append(f"{i}. {esc(g)}")
        L.append("")

    L.append("## 六、联动提示")
    L.append("")
    L.append("- 标注核对可先经 `gdt-checker`；位置度等几何公差按 MMC/± 线性近似纳入叠加（规则待企业补充）。")
    L.append("- 结合 `process-capability` 用 Cpk 验证 RSS 正态假设是否成立。")
    L.append("- 超差高风险环纳入 `fmea-assistant` 重点控制。")
    L.append("")
    return "\n".join(L)


# ---------- 纯文字版渲染 ----------
def render_txt(data):
    title = esc(get(data, "title")) or "（未填写）"
    date = esc(get(data, "date")) or datetime.now().strftime("%Y-%m-%d")
    closed = esc(get(data, "closed_loop")) or "封闭环"
    req = get(data, "requirement")
    chains = get_list(data, "chains")

    N = closed_nominal(chains)
    wc = worst_case_half(chains)
    rs = rss_half(chains)
    wc_lo, wc_hi = gap_range(N, wc)
    rs_lo, rs_hi = gap_range(N, rs)
    wc_ok = check_requirement(wc_lo, wc_hi, req)
    rs_ok = check_requirement(rs_lo, rs_hi, req)

    req_str = "（待补充）"
    if isinstance(req, dict):
        rmin = req.get("min")
        rmax = req.get("max")
        rtype = esc(req.get("type")) or "间隙"
        if rmin is not None and rmax is not None:
            req_str = f"{rtype}要求：[{fmt(rmin)}, {fmt(rmax)}]"

    SEP = "=" * 56
    SUB = "-" * 56
    L = []
    L.append(SEP)
    L.append("公差叠加 / 尺寸链计算报告")
    L.append(SEP)
    L.append(f"主题：{title}")
    L.append(f"编制日期：{date}")
    L.append(f"封闭环：{closed}")
    L.append(f"装配要求：{req_str}")
    L.append("（本报告为计算建议稿，最终公差定版由设计/工艺责任人确认）")
    L.append("")

    L.append(SUB)
    L.append("一、尺寸链（组成环）")
    L.append(SUB)
    if chains:
        for i, c in enumerate(chains, 1):
            L.append(f"{i}. {esc(get(c, 'name'))}：基本尺寸 {fmt(get(c, 'nominal'))}"
                     f" ｜ ±公差(半幅) {fmt(get(c, 'tol'))} ｜ 方向 {esc(get(c, 'dir')) or '增环'}")
    else:
        L.append("暂无组成环（待补充）")
    L.append("")

    L.append(SUB)
    L.append("二、计算过程")
    L.append(SUB)
    L.append(f"封闭环基本尺寸 N = Σ增环 − Σ减环 = {fmt(N)}")
    L.append(f"极值法（WC）半幅 T_wc = Σ|tol_i| = {fmt(wc)}")
    L.append(f"统计法（RSS）半幅 T_rss = √(Σ tol_i²) = {fmt(rs)}")
    L.append("")

    L.append(SUB)
    L.append("三、结果对比")
    L.append(SUB)
    wc_mark = "满足" if wc_ok else ("不满足" if wc_ok is False else "待补充要求")
    rs_mark = "满足" if rs_ok else ("不满足" if rs_ok is False else "待补充要求")
    L.append(f"极值法 WC：间隙下限 {fmt(wc_lo)} ｜ 上限 {fmt(wc_hi)} ｜ {wc_mark}")
    L.append(f"统计法 RSS：间隙下限 {fmt(rs_lo)} ｜ 上限 {fmt(rs_hi)} ｜ {rs_mark}")
    L.append("")

    L.append(SUB)
    L.append("四、超差提示与建议")
    L.append(SUB)
    if wc_ok is False or rs_ok is False:
        L.append("- 当前链在某方法下超出装配要求，建议：")
        contrib = sorted(chains, key=lambda c: abs(float(c.get("tol", 0) or 0)), reverse=True)
        if contrib:
            top = contrib[0]
            L.append(f"  - 贡献最大的环：{esc(get(top, 'name'))}（±{fmt(get(top, 'tol'))}），"
                     f"优先评估是否可收紧或提升工艺能力。")
        L.append("  - 若批量大且过程受控，可采信 RSS 放宽要求；安全/法规件须按 WC 控制。")
        L.append("  - 必要时做公差分配：按等公差法或工艺能力加权重新分配各环公差。")
    else:
        L.append("- 当前两种方法的间隙均在要求范围内，装配可行。仍建议结合 Cpk 验证 RSS 假设。")
    L.append("")

    gaps = get_list(data, "gaps")
    if gaps:
        L.append(SUB)
        L.append("五、待企业补充 / 待确认")
        L.append(SUB)
        for i, g in enumerate(gaps, 1):
            L.append(f"{i}. {esc(g)}")
        L.append("")

    L.append(SUB)
    L.append("六、联动提示")
    L.append(SUB)
    L.append("- 标注核对可先经 gdt-checker；位置度等几何公差按 MMC/± 线性近似纳入叠加（规则待企业补充）。")
    L.append("- 结合 process-capability 用 Cpk 验证 RSS 正态假设是否成立。")
    L.append("- 超差高风险环纳入 fmea-assistant 重点控制。")
    L.append("")
    return "\n".join(L)


# ---------- 主流程 ----------
def main():
    ap = argparse.ArgumentParser(description="公差叠加 / 尺寸链计算报告生成器（txt+md）")
    ap.add_argument("input", nargs="?", help="输入 JSON 路径；省略则使用内置小样本")
    ap.add_argument("--out-dir", default=os.getcwd(), help="输出目录，默认当前工作目录")
    ap.add_argument("--format", choices=["txt", "md", "all"], default="all",
                    help="输出格式，默认 all（txt+md）")
    ap.add_argument("--base", default=None, help="输出文件基名（不含扩展名）；默认按主题与日期生成")
    args = ap.parse_args()

    if args.input:
        if not os.path.isfile(args.input):
            sys.stderr.write(f"错误：找不到输入文件 {args.input}\n")
            sys.exit(1)
        try:
            with open(args.input, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            sys.stderr.write(f"错误：解析 JSON 失败 - {e}\n")
            sys.exit(1)
        if not isinstance(data, dict):
            sys.stderr.write("错误：JSON 根节点必须是对象\n")
            sys.exit(1)
    else:
        data = SAMPLE
        sys.stderr.write("未提供输入，使用内置小样本数据。\n")

    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)
    base = args.base or f"公差叠加尺寸链报告_{date_tag_of(data)}"

    if args.format in ("md", "all"):
        md_path = os.path.join(out_dir, base + ".md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(render_md(data))
        sys.stderr.write(f"已生成：{md_path}\n")

    if args.format in ("txt", "all"):
        txt_path = os.path.join(out_dir, base + ".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(render_txt(data))
        sys.stderr.write(f"已生成：{txt_path}\n")


if __name__ == "__main__":
    main()
