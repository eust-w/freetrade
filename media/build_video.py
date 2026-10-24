"""Build narrated landscape and portrait project films from repository evidence."""
from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "media/export"
SCENES = json.loads((ROOT / "media/storyboard.json").read_text())
BG = "#102c3b"
INK = "#f7f2e8"
MUTED = "#9bb8bd"
GREEN = "#87dbc3"
AMBER = "#f2bd6b"
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"
LATIN = "/System/Library/Fonts/Avenir Next.ttc"


def font(size, latin=False):
    return ImageFont.truetype(LATIN if latin else FONT, size)


def command(args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)


def duration(path):
    return float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)], text=True))


def wrap(draw, text, f, width):
    result = []
    for para in text.split("\n"):
        line = ""
        for char in para:
            if draw.textlength(line + char, font=f) > width and line:
                result.append(line)
                line = char
            else:
                line += char
        result.append(line)
    return result


def write(draw, xy, text, size, color=INK, width=None, latin=False, gap=1.3):
    f = font(size, latin)
    lines = wrap(draw, text, f, width) if width else text.split("\n")
    x, y = xy
    for line in lines:
        draw.text((x, y), line, fill=color, font=f)
        y += int(size * gap)
    return y


def panel(draw, box, fill="#1c3d4b", outline="#31535e", radius=24):
    draw.rounded_rectangle(box, radius, fill=fill, outline=outline, width=2)


def paste_fit(img, path, box):
    shot = Image.open(path).convert("RGB")
    x, y, w, h = box
    fit = ImageOps.contain(shot, (w, h))
    img.paste(fit, (x + (w-fit.width)//2, y+(h-fit.height)//2))


def frame(scene, idx, portrait=False):
    w, h = (1080, 1920) if portrait else (1920, 1080)
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    for x in range(0, w, 64):
        d.line((x, 0, x, h), fill="#163541", width=1)
    for y in range(0, h, 64):
        d.line((0, y, w, y), fill="#163541", width=1)
    pad = 76 if portrait else 100
    write(d, (pad, 80 if portrait else 65), scene["eyebrow"], 25, GREEN, latin=True)
    title_y = 180 if portrait else 145
    title_size = 74 if portrait else 82
    write(d, (pad, title_y), scene["title"], title_size, width=w-2*pad, gap=1.22)
    title_end = title_y + int(title_size * 2.55)
    write(d, (pad, title_end+25), scene["sub"], 29, MUTED, width=w-2*pad)
    top = title_end + 130
    bottom = h - (310 if portrait else 150)
    pw = w - 2*pad
    kind = scene["kind"]

    if kind == "demo":
        if portrait:
            paste_fit(img, ROOT/"docs/assets/demo-mobile.jpg", (pad, top, pw, bottom-top))
        else:
            paste_fit(img, ROOT/"docs/assets/demo-desktop.jpg", (pad, top-20, pw, bottom-top+30))
    elif kind == "factors":
        weights = [("动量",25),("成长",22),("资金",20),("质量",17),("估值",16)]
        row_h = 145 if portrait else 78
        for i,(name,value) in enumerate(weights):
            y=top+i*row_h
            write(d,(pad,y),name,38 if portrait else 30)
            bar_x=pad+130
            bar_w=(pw-240)*value/25
            d.rounded_rectangle((bar_x,y+5,bar_x+bar_w,y+40),10,fill=GREEN)
            write(d,(pad+pw-90,y),f"{value}%",32,GREEN,latin=True)
    elif kind == "flow":
        names=["行情 / 财报","五因子 + 风险规则","带日期的成功快照","HTML + 运行状态","发布后内容核验"]
        if portrait:
            for i,name in enumerate(names):
                y=top+i*155
                panel(d,(pad,y,w-pad,y+110))
                write(d,(pad+35,y+34),f"0{i+1}   {name}",35)
                if i<4:
                    write(d,(w//2-12,y+116),"↓",28,GREEN)
        else:
            boxw=(pw-4*26)//5
            for i,name in enumerate(names):
                x=pad+i*(boxw+26)
                panel(d,(x,top+60,x+boxw,top+285))
                write(d,(x+24,top+85),f"0{i+1}",48,GREEN,latin=True)
                write(d,(x+24,top+170),name,29,width=boxw-48)
    elif kind == "runs":
        values=[("5","live 标记",GREEN),("105","fallback 标记",AMBER),("17","成功结果未观察到",MUTED)]
        for i,(value,label,col) in enumerate(values):
            if portrait:
                box=(pad,top+i*240,w-pad,top+i*240+205)
                panel(d,box)
                write(d,(pad+38,box[1]+25),value,96,col,latin=True)
                write(d,(pad+280,box[1]+85),label,32,width=pw-320)
            else:
                bw=(pw-64)//3
                x=pad+i*(bw+32)
                panel(d,(x,top+35,x+bw,top+340))
                write(d,(x+42,top+55),value,140,col,latin=True)
                write(d,(x+42,top+240),label,30,width=bw-65)
        write(d,(pad,bottom+15),"2026.06.15 — 2026.09.01 · 仅统计保留日志",24,MUTED,width=pw)
    elif kind == "freshness":
        labels=[("generated_at","页面生成的时间"),("data_as_of","候选数据原始日期"),("mode","demo / live / cached / fallback")]
        for i,(key,val) in enumerate(labels):
            y=top+i*(240 if portrait else 122)
            panel(d,(pad,y,w-pad,y+(200 if portrait else 102)))
            write(d,(pad+32,y+22),key,35,GREEN,latin=True)
            write(d,(pad+32 if portrait else pad+440,y+(98 if portrait else 27)),val,32,width=pw-64)
    elif kind == "hook":
        write(d,(pad,top+30),"200",240 if portrait else 235,GREEN,latin=True)
        x=pad if portrait else pad+640
        y=top+370 if portrait else top+120
        write(d,(x,y),"服务可达\n数据日期仍需核对",56,INK,width=pw,gap=1.5)
    elif kind == "end":
        panel(d,(pad,top,w-pad,bottom-20))
        write(d,(pad+40,top+50),"FreeTrade",100 if portrait else 110,GREEN,latin=True)
        write(d,(pad+40,top+220),"MIT · Python · Offline demo",33,INK,latin=True,width=pw-80)
        write(d,(pad+40,top+320),"github.com/eust-w/freetrade",33,GREEN,latin=True,width=pw-80)
        write(d,(pad+40,top+440 if portrait else top+390),"研究交流 · 无自动下单 · 无收益承诺",30,MUTED,width=pw-80)
    # Keep a consistent footer and progress rail inside platform-safe margins.
    footer_y=h-(165 if portrait else 85)
    write(d,(pad,footer_y),"FREETRADE  /  合成演示 · 研究用途",24,MUTED)
    write(d,(w-pad-90,footer_y),f"0{idx+1}/07",24,GREEN,latin=True)
    for j in range(7):
        seg=(w-2*pad-6*12)/7
        x=pad+j*(seg+12)
        d.rounded_rectangle((x,h-60,x+seg,h-54),3,fill=GREEN if j<=idx else "#31535e")
    path=OUT/f"scene-{idx:02d}-{'portrait' if portrait else 'landscape'}.png"
    img.save(path)
    return path


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    timings=[]
    for i,scene in enumerate(SCENES):
        audio=OUT/f"voice-{i:02d}.aiff"
        command(["say","-v","Tingting","-r","175","-o",str(audio),scene["narration"]])
        timings.append(round(duration(audio)+0.65,2))
    for portrait in (False,True):
        name="portrait" if portrait else "landscape"
        w,h=(1080,1920) if portrait else (1920,1080)
        segments=[]
        for i,(scene,seconds) in enumerate(zip(SCENES,timings)):
            still=frame(scene,i,portrait)
            clip=OUT/f"clip-{name}-{i:02d}.mp4"
            # Subtle continuous camera drift; fades make scene boundaries deliberate.
            vf=(f"zoompan=z='min(zoom+0.00002,1.02)':x='iw/2-iw/zoom/2':"
                f"y='ih/2-ih/zoom/2':d=1:s={w}x{h}:fps=24,"
                f"fade=t=in:st=0:d=0.3,fade=t=out:st={seconds-0.3}:d=0.3")
            command(["ffmpeg","-hide_banner","-loglevel","error","-y","-loop","1","-framerate","24",
                     "-i",str(still),"-i",str(OUT/f"voice-{i:02d}.aiff"),"-vf",vf,
                     "-af","apad,loudnorm=I=-16:TP=-1.5:LRA=11","-t",str(seconds),
                     "-c:v","libx264","-preset","fast","-crf","20","-pix_fmt","yuv420p",
                     "-c:a","aac","-b:a","160k","-ar","48000","-movflags","+faststart",str(clip)])
            segments.append(clip)
        listing=OUT/f"concat-{name}.txt"
        listing.write_text("".join(f"file '{p.name}'\n" for p in segments))
        command(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0",
                 "-i",str(listing),"-c","copy","-movflags","+faststart",str(OUT/f"freetrade-{name}.mp4")])
    # Original cover composition, not a third-party image.
    cover=Image.open(OUT/"scene-00-landscape.png")
    cover.resize((1280,720),Image.Resampling.LANCZOS).save(OUT/"cover.jpg",quality=94)
    manifest={"scene_seconds":timings,"duration_seconds":sum(timings),
              "narration":"macOS Tingting synthetic voice","music":None,
              "visuals":"original diagrams and repository demo screenshots",
              "files":["freetrade-landscape.mp4","freetrade-portrait.mp4","cover.jpg"]}
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
