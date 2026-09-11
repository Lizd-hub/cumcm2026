"""Generate exact scientific diagrams and plots from the saved local results."""
import json
import math
from pathlib import Path
import pymupdf as fitz
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle, Polygon
import numpy as np
from ..core.geometry import minimum_circle, safe_second_point, unit
from ..core.solver import coverage_sites
from ..cli.preprocess_logs import audit

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
TMP = PROJECT_ROOT / 'outputs' / '.cache' / 'b_report_assets'
FIG = PACKAGE_ROOT / 'figures'
BLUE, TEAL, ORANGE, GREY = '#21618C', '#117864', '#AF601A', '#7B7D7D'


def prepare_environment():
    """Create output paths and configure fonts only when figure generation runs."""
    TMP.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(exist_ok=True)
    font_path = TMP / 'DroidSansFallback.ttf'
    if not font_path.exists():
        font_path.write_bytes(fitz.Font('cjk').buffer)
    font_manager.fontManager.addfont(str(font_path))
    font_name = font_manager.FontProperties(fname=font_path).get_name()
    plt.rcParams.update({'font.family': font_name, 'font.size': 10.5, 'axes.unicode_minus': False,
                         'axes.spines.top': False, 'axes.spines.right': False, 'figure.dpi': 150,
                         'savefig.dpi': 200, 'axes.labelcolor': '#222222', 'text.color': '#111111'})


def save(fig, name):
    fig.savefig(FIG / name, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def main():
    prepare_environment()
    p = np.array([[0, 0], [40, 0], [20, 20 * math.sqrt(3)]])
    c, r = minimum_circle(p)
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    ax.add_patch(Polygon(p, color=BLUE, alpha=.15))
    ax.plot(*np.vstack([p, p[0]]).T, color=BLUE, lw=2, label='定位区域 直径 40 m')
    ax.add_patch(Circle((20, 0), 20, fill=False, color=ORANGE, ls='--', lw=1.8, label='最长边作直径的圆 半径 20 m'))
    ax.add_patch(Circle(c, r, fill=False, color=TEAL, lw=1.6, label='最小包围圆 半径 23.094 m'))
    ax.scatter(*c, color=TEAL, s=30)
    ax.annotate('第三个顶点在橙色圆外', p[2], xytext=(36, 38), ha='center', fontsize=10,
                arrowprops={'arrowstyle': '->', 'color': ORANGE})
    ax.set(xlim=(-8, 56), ylim=(-24, 43), xlabel='x 坐标  m', ylabel='y 坐标  m', aspect='equal')
    ax.legend(loc='upper center', bbox_to_anchor=(.5, -.20), frameon=False, fontsize=10)
    save(fig, 'q1_enclosing_circle.png')

    x, y = np.meshgrid(np.linspace(-100, 1600, 400), np.linspace(-1100, 1100, 400))
    centers = np.array([[0, 0], 1000 * unit(-1.005), 1000 * unit(1.005)])
    mask = np.ones(x.shape, bool)
    for center in centers:
        mask &= (x - center[0]) ** 2 + (y - center[1]) ** 2 <= 1000 ** 2
    fig, ax = plt.subplots(figsize=(6.7, 4.5))
    ax.contourf(x, y, mask.astype(int), levels=[.5, 1.5], colors=['#D4EFDF'])
    for center in centers:
        ax.add_patch(Circle(center, 1000, fill=False, lw=.9, ls='--', color=GREY))
    for angle in (-1.005, 1.005):
        end = 1500 * unit(angle)
        ax.plot([0, end[0]], [0, end[1]], color=BLUE, lw=1.1)
    ax.scatter([0], [0], color='black', s=25)
    ax.annotate('第一检测点', (0, 0), (-70, -160), fontsize=10)
    ax.scatter([750, 750], [500, 650], c=[BLUE, ORANGE], s=40)
    ax.annotate('基础示例 750  500', (750, 500), (910, 405), fontsize=10,
                arrowprops={'arrowstyle': '-', 'color': BLUE})
    ax.annotate('有限候选最优 750  650', (750, 650), (1020, 820), fontsize=10,
                arrowprops={'arrowstyle': '-', 'color': ORANGE})
    ax.text(265, -420, '绿色区域内的点\n具有全向源接收保证', color=TEAL, fontsize=11)
    ax.set(xlim=(-200, 1700), ylim=(-1100, 1100), xlabel='沿首次示向的距离  m', ylabel='横向距离  m', aspect='equal')
    save(fig, 'q2_candidate_region.png')

    pts = coverage_sites(False)
    fig, ax = plt.subplots(figsize=(6.5, 5.0))
    for q in pts:
        ax.add_patch(Circle(q, 900, color=BLUE, alpha=.055))
        ax.add_patch(Circle(q, 900, fill=False, color=BLUE, lw=.7, alpha=.65))
    ax.add_patch(Circle((0, 0), 1800, fill=False, color='black', lw=1.7, label='源所在圆域 半径 1800 m'))
    ax.scatter(*pts.T, color=BLUE, s=32, label='七个检测点')
    for i, q in enumerate(pts):
        ax.text(q[0] + 55, q[1] + 55, str(i), fontsize=11)
    ax.set(xlim=(-2600, 2600), ylim=(-2400, 2400), xlabel='x 坐标  m', ylabel='y 坐标  m', aspect='equal')
    ax.legend(loc='upper center', bbox_to_anchor=(.5, -.16), frameon=False, fontsize=10)
    save(fig, 'q3_seven_site_cover.png')

    pts = coverage_sites(True)
    fig, ax = plt.subplots(figsize=(6.6, 5.1))
    for i in range(len(pts)):
        for j in range(i):
            if abs(np.linalg.norm(pts[i]-pts[j])-950) < 1e-6:
                ax.plot([pts[i,0],pts[j,0]], [pts[i,1],pts[j,1]], color='#BFC9CA', lw=.7)
    outside = np.linalg.norm(pts, axis=1) > 1800
    ax.scatter(*pts[~outside].T, c=BLUE, s=28, label='圆域内检测点')
    ax.scatter(*pts[outside].T, c=ORANGE, s=28, label='圆域外检测点')
    ax.add_patch(Circle((0, 0), 1800, fill=False, color='black', lw=1.8, label='源所在圆域'))
    ax.scatter([1800], [0], c='#922B21', marker='*', s=110)
    ax.annotate('边界源朝外发射', (1800, 0), (500, -600), fontsize=10,
                arrowprops={'arrowstyle': '->', 'color': '#922B21'})
    ax.annotate('', (2350, 0), (1850, 0), arrowprops={'arrowstyle': '->', 'color': '#922B21', 'lw': 2})
    ax.set(xlim=(-2900, 2900), ylim=(-2850, 2850), xlabel='x 坐标  m', ylabel='y 坐标  m', aspect='equal')
    ax.legend(loc='upper center', bbox_to_anchor=(.5, -.16), ncol=3, frameon=False, fontsize=9.5)
    save(fig, 'q4_triangular_cover.png')

    a = 950
    p = np.array([[0, 0], [a, 0], [a / 2, a * math.sqrt(3) / 2]])
    g = p.T @ np.array([.25, .35, .4])
    direction = unit(25)
    fig, ax = plt.subplots(figsize=(6.3, 4.2))
    # An illustrative emitting half-plane, clipped only for the diagram.
    v = np.array([-direction[1], direction[0]])
    shade = np.array([g - 1500 * v, g + 1500 * v, g + 1500 * v + 1600 * direction,
                      g - 1500 * v + 1600 * direction])
    ax.add_patch(Polygon(shade, color='#FAD7A0', alpha=.4))
    ax.plot(*np.vstack([p, p[0]]).T, color=BLUE, lw=2)
    for k, q in enumerate(p):
        ax.plot([g[0], q[0]], [g[1], q[1]], '--', c=GREY, lw=.9)
        ax.text(q[0] + 18, q[1] + 20, f'检测点 {k+1}', fontsize=10)
    ax.scatter(*p.T, s=38, color=BLUE)
    ax.scatter(*g, s=60, color='#922B21', marker='*')
    ax.annotate('源 G', g, (g[0] - 115, g[1] + 45), fontsize=11)
    ax.annotate('', g + 340 * direction, g,
                arrowprops={'arrowstyle': '->', 'color': ORANGE, 'lw': 1.7})
    ax.text(g[0]+190,g[1]+170,'发射轴',fontsize=10,color=ORANGE)
    ax.text(70, -180, '三角形边长 950 m   三个顶点不会同时落在无信号半平面', fontsize=10)
    ax.set(xlim=(-80, 1100), ylim=(-230, 960), aspect='equal')
    ax.axis('off')
    save(fig, 'q4_cell_proof.png')

    rows = json.loads((PACKAGE_ROOT / 'results' / 'raw_results.json').read_text())
    fig, axes = plt.subplots(1, 2, figsize=(7, 3.7))
    for ax, q in zip(axes, (3, 4)):
        for k, model in enumerate(('baseline', 'improved')):
            values = [r['average_time_s'] for r in rows if r['question'] == q and r['scenario'] == 'random_smooth' and r['model'] == model]
            ax.bar(k, np.mean(values), color=[GREY, BLUE][k], width=.5, alpha=.75)
            ax.scatter(np.linspace(k - .14, k + .14, len(values)), values, s=14, color='#17202A', alpha=.6)
            ax.text(k, np.mean(values) + max(values) * .02, f'{np.mean(values):.2f}', ha='center', fontsize=11)
        ax.set_xticks([0, 1], ['基础策略', '改进策略'])
        ax.set_ylabel('每个场景的平均清除耗时  s')
        ax.set_title(f'第 {q} 问  12 个自建常规场景', fontsize=11)
        ax.grid(axis='y', alpha=.15)
    fig.tight_layout(w_pad=2.4)
    save(fig, 'local_comparison.png')

    examples = json.loads((PACKAGE_ROOT / 'results' / 'examples.json').read_text())
    ex = next(e for e in examples if e['question'] == 4 and e['scenario'] == 'random_smooth')
    path = np.array(ex['path'])
    fig, ax = plt.subplots(figsize=(6.6, 5.1))
    ax.plot(*path.T, color=BLUE, lw=.65, alpha=.65, label='实际执行路线')
    ax.add_patch(Circle((0, 0), 1800, fill=False, color='black', lw=1.3))
    sites = np.array(ex['sites'])
    ax.scatter(*sites.T, color=GREY, s=12, label='覆盖站')
    for source in ex['sources']:
        g = np.array(source['position'])
        if source['axis'] is None:
            ax.scatter(*g, s=35, facecolor='white', edgecolor=TEAL, linewidths=1.5)
        else:
            ax.scatter(*g, s=38, marker='^', color=ORANGE)
            v = 180 * np.array([math.cos(source['axis']), math.sin(source['axis'])])
            ax.annotate('', g + v, g, arrowprops={'arrowstyle': '->', 'lw': .8, 'color': ORANGE})
    ax.scatter([], [], s=35, facecolor='white', edgecolor=TEAL, label='全向源')
    ax.scatter([], [], s=38, marker='^', color=ORANGE, label='定向源及发射轴')
    ax.set(xlim=(-2900, 2900), ylim=(-2850, 2850), xlabel='x 坐标  m', ylabel='y 坐标  m', aspect='equal')
    ax.legend(loc='upper center', bbox_to_anchor=(.5, -.16), ncol=2, frameon=False, fontsize=9.5)
    save(fig, 'local_q4_path.png')
    audits = [{'question': e['question'], 'scenario': e['scenario'], **audit(e['records'])['counts']} for e in examples]
    (PACKAGE_ROOT / 'results' / 'data_audit.json').write_text(json.dumps(audits, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Figures and four example log audits generated.')


if __name__ == '__main__':
    main()
