"""独立输出核验：PDF 字号、页面裁切、可编辑 SVG、300 dpi PNG。
更细的图形交叠仍需要目视审核；本工具不声称证明无碰撞。
"""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image
import pymupdf as fitz
from legacy_solution.common.logging_io import write_json

def audit(directory="outputs/figures",output="outputs/qa/artifacts.json"):
    records=[]
    for pdf in sorted(Path(directory).glob("fig*.pdf")):
        doc=fitz.open(pdf)
        sizes=[]
        clipped=[]
        for page in doc:
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines",[]):
                    for span in line["spans"]:
                        sizes.append(span["size"])
                        if not (page.rect+(-.5,-.5,.5,.5)).contains(fitz.Rect(span["bbox"])):
                            clipped.append(span["text"])
        svg=ET.parse(pdf.with_suffix(".svg"))
        text_count=sum(1 for e in svg.getroot().iter() if e.tag.endswith("}text"))
        with Image.open(pdf.with_suffix(".png")) as im:
            dpi=im.info.get("dpi",(0,0))
            pixels=im.size
        row=dict(figure=pdf.stem,minimum_font_pt=min(sizes) if sizes else None,
                 pdf_clipped_text=clipped,svg_text_elements=text_count,png_dpi=dpi,png_pixels=pixels)
        row["passed"]=bool(sizes) and min(sizes)>=5 and not clipped and text_count>0 and min(dpi)>=299
        records.append(row)
    write_json(output,records)
    if len(records)!=9 or not all(r["passed"] for r in records):
        raise RuntimeError("图表核验未全部通过，详见输出 JSON")
    return records

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",default="outputs/figures")
    parser.add_argument("--output",default="outputs/qa/artifacts.json")
    args=parser.parse_args()
    audit(args.input,args.output)
    print("9 figures passed output checks")

if __name__=="__main__":
    main()
