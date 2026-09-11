"""统一中文论文作图风格；不调用任何求解器。"""
import argparse
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from common.logging_io import read_json,write_json

COLORS = dict(coverage="#477C99",localization="#D49348",clear="#46856A",fallback="#B46A70")

def setup():
    available={f.name for f in font_manager.fontManager.ttflist}
    font=next((f for f in ["Microsoft YaHei","SimHei","Noto Sans CJK SC","SimSun"] if f in available),None)
    if font is None:
        raise RuntimeError("请安装中文字体 Microsoft YaHei 或 Noto Sans CJK SC")
    plt.rcParams.update({"font.family":font,"font.size":9,"axes.unicode_minus":False,
                         "pdf.fonttype":42,"svg.fonttype":"none","axes.spines.top":False,
                         "axes.spines.right":False,"legend.frameon":False,"figure.dpi":120})
    return plt.subplots(figsize=(7.2,5.4),layout="constrained")

def geometry_axes(ax):
    ax.set_aspect("equal",adjustable="box")
    ax.set_xlabel("东西坐标 x / 米")
    ax.set_ylabel("南北坐标 y / 米")

def save(fig,output,source,claim):
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    fig.canvas.draw()
    renderer=fig.canvas.get_renderer()
    bounds=fig.bbox
    ignored=set()
    for ax in fig.axes:
        for axis in (ax.xaxis,ax.yaxis):
            lo,hi=sorted(axis.get_view_interval())
            for tick in [*axis.get_major_ticks(),*axis.get_minor_ticks()]:
                if not lo <= tick.get_loc() <= hi:
                    ignored.update([tick.label1,tick.label2])
    outside=[]
    for text in fig.findobj(matplotlib.text.Text):
        if text not in ignored and text.get_visible() and text.get_text():
            box=text.get_window_extent(renderer)
            if box.width and box.height and (box.x0<bounds.x0-1 or box.y0<bounds.y0-1 or box.x1>bounds.x1+1 or box.y1>bounds.y1+1):
                outside.append(text.get_text())
    if outside:
        raise ValueError(f"裁切文字: {outside}")
    for extension in ("pdf","svg","png"):
        fig.savefig(output.with_suffix("."+extension),dpi=300)
    write_json(output.with_suffix(".metadata.json"),dict(source=source,claim=claim,backend="matplotlib",
                text_clipping="passed",panel_alignment="not_applicable_single_axes",
                width_inches=7.2,height_inches=5.4))
    plt.close(fig)

def cli(plot,default_input,default_output):
    p=argparse.ArgumentParser()
    p.add_argument("--input",default=default_input)
    p.add_argument("--output",default=default_output)
    args=p.parse_args()
    plot(read_json(args.input),args.output)

def source_label(data):
    return {"constructed":"构造示例","offline":"离线实验","official_practice":"官方演练",
            "official_formal":"正式测试"}.get(data.get("source"),"输入数据")
