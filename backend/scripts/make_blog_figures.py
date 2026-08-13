"""博客配图生成：三张数据图（体检乱象 / 三层防线架构 / 防线成绩单）。

输出到 docs/blog_assets/（docs 在 gitignore，本地发布用）。
运行：backend/.venv/Scripts/python.exe scripts/make_blog_figures.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

OUT = Path(__file__).resolve().parents[2] / "docs" / "blog_assets"
OUT.mkdir(parents=True, exist_ok=True)

INK = "#1f2937"      # 主文字
RED = "#dc2626"      # error
AMBER = "#d97706"    # warning
GREEN = "#059669"    # pass
BLUE = "#2563eb"     # 强调
GRAY = "#9ca3af"


# ── 图 1：体检报告（第一节配图）──────────────────────────────────────
def fig1():
    items = [
        ("无追溯编号", 268, AMBER),
        ("缺 case_type", 256, RED),
        ("旧 schema 字段", 225, AMBER),
        ("缺用例名称", 199, RED),
        ("步骤是无结构字符串", 152, AMBER),
        ("仅 1 步（疑似没断言过程）", 143, AMBER),
        ("真无步骤", 4, RED),
    ]
    fig, ax = plt.subplots(figsize=(8.6, 4.2), dpi=160)
    labels = [i[0] for i in items][::-1]
    values = [i[1] for i in items][::-1]
    colors = [i[2] for i in items][::-1]
    bars = ax.barh(labels, values, color=colors, height=0.62)
    for b, v in zip(bars, values):
        ax.text(v + 4, b.get_y() + b.get_height() / 2, str(v),
                va="center", fontsize=10, color=INK)
    ax.set_title("1828 条 AI 生成用例的体检结果（首份 lint 基线：459 error / 826 warning）",
                 fontsize=12, color=INK, pad=12, loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_xlim(0, 300)
    ax.tick_params(labelsize=10, colors=INK)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=RED, label="error（结构硬伤）"),
                       Patch(color=AMBER, label="warning（规范问题）")],
              loc="lower right", frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "fig1_lint_baseline.png")
    plt.close(fig)


# ── 图 2：三层防线架构（第二节配图）──────────────────────────────────
def fig2():
    fig, ax = plt.subplots(figsize=(8.6, 4.9), dpi=160)
    ax.axis("off")
    ax.set_ylim(-0.02, 1.12)
    layers = [
        ("第三层  语义防线", "LLM 裁判（G-Eval）：预期结果可断言性 / 幻觉用例",
         "——裁判须先通过盲标校准（Kappa ≥ 0.6）才允许拦人", "#eff6ff", BLUE),
        ("第二层  覆盖防线", "功能矩阵 FP × 用例引用直接匹配：漏测清单 / 薄弱覆盖预警",
         "——半代码：编号匹配零 token，语义部分留给人", "#fffbeb", AMBER),
        ("第一层  规范防线", "用例 lint：字段 / 编号 / 步骤结构 / 追溯编号",
         "——纯代码，零 token，直接接 CI", "#ecfdf5", GREEN),
    ]
    y = 0.06
    for title, desc, note, bg, edge in layers:
        ax.add_patch(plt.Rectangle((0.04, y), 0.92, 0.25, facecolor=bg,
                                   edgecolor=edge, linewidth=1.6, zorder=1,
                                   transform=ax.transAxes))
        ax.text(0.075, y + 0.185, title, fontsize=13, fontweight="bold",
                color=edge, transform=ax.transAxes)
        ax.text(0.075, y + 0.105, desc, fontsize=10.5, color=INK, transform=ax.transAxes)
        ax.text(0.075, y + 0.038, note, fontsize=9.5, color=GRAY, transform=ax.transAxes)
        y += 0.33
    ax.text(0.5, 1.08, "越往下：确定性越高、token 成本越低", ha="center",
            fontsize=10, color=GRAY, transform=ax.transAxes)
    fig.tight_layout()
    fig.savefig(OUT / "fig2_three_layers.png")
    plt.close(fig)


# ── 图 3：防线成绩单（第六节配图）────────────────────────────────────
def fig3():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.6, 3.8), dpi=160)

    # 左：自检拦截率环图
    ax1.pie([40, 20], labels=["通过 40 次", "拦截 20 次"], colors=[GREEN, RED],
            startangle=90, counterclock=False,
            wedgeprops=dict(width=0.42, edgecolor="white"),
            textprops=dict(fontsize=10.5, color=INK))
    ax1.text(0, 0.08, "33.3%", ha="center", fontsize=20, fontweight="bold", color=RED)
    ax1.text(0, -0.22, "批量自检拦截率", ha="center", fontsize=10, color=GRAY)
    ax1.set_title("创建门禁（60 次自检调用）", fontsize=11.5, color=INK)

    # 右：对抗评审发现
    cats = ["严重缺陷", "可改进项"]
    vals = [41, 83]
    bars = ax2.bar(cats, vals, color=[RED, AMBER], width=0.5)
    for b, v in zip(bars, vals):
        ax2.text(b.get_x() + b.get_width() / 2, v + 2, str(v),
                 ha="center", fontsize=12, fontweight="bold", color=INK)
    ax2.set_title("对抗评审发现（3 批次）", fontsize=11.5, color=INK)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.set_ylim(0, 95)
    ax2.tick_params(labelsize=10.5, colors=INK)
    ax2.text(0.5, -0.16, "信任度评估：低 ×2、中 ×1", transform=ax2.transAxes,
             ha="center", fontsize=9.5, color=GRAY)

    fig.tight_layout()
    fig.savefig(OUT / "fig3_defense_score.png")
    plt.close(fig)


fig1(); fig2(); fig3()
print("生成完成：")
for p in sorted(OUT.glob("fig*.png")):
    print(f"  {p}  {p.stat().st_size // 1024}KB")
