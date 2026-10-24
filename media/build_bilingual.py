"""Build two narration languages, two aspect ratios, and frame-aligned subtitles.

Run from the repository root with: python -m media.build_bilingual
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'media/export/bilingual'
FPS = 24
BG, INK, MUTED, MINT, AMBER = '#102c3b', '#f7f2e8', '#9bb8bd', '#87dbc3', '#f2bd6b'
KINDS = {'hook', 'demo', 'factors', 'flow', 'runs', 'freshness', 'end'}
FONTS = {'zh': '/System/Library/Fonts/STHeiti Medium.ttc', 'en': '/System/Library/Fonts/Avenir Next.ttc'}
VOICES = {'zh': ('Tingting', 200), 'en': ('Samantha', 190)}


def timecode(seconds):
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError('subtitle time must be finite and non-negative')
    millis = round(seconds * 1000)
    minutes, millis = divmod(millis, 60_000)
    hours, minutes = divmod(minutes, 60)
    seconds, millis = divmod(millis, 1000)
    return f'{hours:02}:{minutes:02}:{seconds:02},{millis:03}'


def make_srt(lines, frames, language):
    if len(lines) != len(frames) or language not in ('zh', 'en', 'bilingual'):
        raise ValueError('subtitle input mismatch')
    result, cursor = [], 0
    for i, (line, count) in enumerate(zip(lines, frames), 1):
        if not isinstance(count, int) or count <= 0:
            raise ValueError('each subtitle needs a positive frame count')
        text = '\n'.join((line['zh'], line['en'])) if language == 'bilingual' else line[language]
        result.append(f'{i}\n{timecode(cursor / FPS)} --> {timecode((cursor + count) / FPS)}\n{text}\n')
        cursor += count
    return '\n'.join(result)


def validate_storyboard(scenes):
    if len(scenes) != 7 or {scene['kind'] for scene in scenes} != KINDS:
        raise ValueError('expected seven distinct scenes')
    for scene in scenes:
        if not scene['lines']:
            raise ValueError('scene must contain narration')
        for text in [scene['title'], *scene['lines']]:
            for lang in ('zh', 'en'):
                if not isinstance(text.get(lang), str) or not text[lang].strip():
                    raise ValueError(f'missing {lang} translation')


def font(size, language='en'):
    return ImageFont.truetype(FONTS[language], size)


def wrapped(draw, text, face, width, language):
    tokens = list(text) if language == 'zh' else re.findall(r'\S+\s*', text)
    lines, current = [], ''
    for token in tokens:
        if current and draw.textlength(current + token, font=face) > width:
            lines.append(current.rstrip())
            current = token.lstrip()
        else:
            current += token
    if current:
        lines.append(current.rstrip())
    return lines


def text(draw, xy, content, size, width, language='en', color=INK):
    face = font(size, language)
    x, y = xy
    for line in wrapped(draw, content, face, width, language):
        if draw.textlength(line, font=face) > width + 1:
            raise ValueError(f'text exceeds layout width: {line}')
        draw.text((x, y), line, font=face, fill=color)
        y += math.ceil(size * 1.35)
    return y


def panel(draw, box):
    draw.rounded_rectangle(box, 22, fill='#1c3d4b', outline='#31535e', width=2)


def base_frame(scene, index, narration, portrait):
    w, h = (1080, 1920) if portrait else (1920, 1080)
    pad = 72 if portrait else 88
    img = Image.new('RGB', (w, h), BG)
    d = ImageDraw.Draw(img)
    for x in range(0, w, 64):
        d.line((x, 0, x, h), fill='#163541')
    for y in range(0, h, 64):
        d.line((0, y, w, y), fill='#163541')
    label = 'CHINESE VOICE / ZH + EN' if narration == 'zh' else 'ENGLISH VOICE / EN + ZH'
    text(d, (pad, 48), f'FREETRADE   /   {label}', 23, w-2*pad, color=MINT)
    other = 'en' if narration == 'zh' else 'zh'
    y = text(d, (pad, 116), scene['title'][narration], 55 if portrait else 68, w-2*pad, narration)
    y = text(d, (pad, y+12), scene['title'][other], 34 if portrait else 35, w-2*pad, other, MUTED)
    top, bottom = y+35, h-(500 if portrait else 330)
    pw = w-2*pad
    kind = scene['kind']
    if kind == 'demo':
        path = ROOT / ('docs/assets/demo-mobile.jpg' if portrait else 'docs/assets/demo-desktop.jpg')
        shot = ImageOps.contain(Image.open(path).convert('RGB'), (pw, bottom-top-40))
        img.paste(shot, (pad+(pw-shot.width)//2, top))
        text(d, (pad, bottom-32), 'Actual UI / Synthetic data   真实界面 / 合成数据', 24, pw, 'zh', MINT)
    elif kind == 'hook':
        text(d, (pad, top+12), '200', 220 if portrait else 190, pw, color=MINT)
        x = pad if portrait else pad+600
        y = top+310 if portrait else top+50
        y = text(d, (x, y), 'Page reachable.', 52, pw if portrait else pw-600)
        y = text(d, (x, y+18), 'Data date still matters.', 42, pw if portrait else pw-600, color=AMBER)
        text(d, (x, y+20), '页面可达，仍需核对数据日期。', 32, pw if portrait else pw-600, 'zh', MUTED)
    elif kind == 'factors':
        weights = [('Momentum / 动量', 25), ('Growth / 成长', 22), ('Fund flow / 资金', 20), ('Quality / 质量', 17), ('Value / 估值', 16)]
        step = (bottom-top)/5
        for i, (name, weight) in enumerate(weights):
            yy = top+i*step
            text(d, (pad, yy), name, 31 if portrait else 28, pw, 'zh')
            bx, by = (pad, yy+62) if portrait else (pad+390, yy+7)
            bw = (pw-120 if portrait else pw-550)*weight/25
            d.rounded_rectangle((bx, by, bx+bw, by+24), 8, fill=MINT)
            text(d, (w-pad-95, yy), f'{weight}%', 31, 95, color=MINT)
    elif kind in ('flow', 'freshness'):
        labels = [('Collect / 采集', 'Quotes + financials / 行情与财报'), ('Score / 评分', 'Factors + risk rules / 因子与风险'), ('Snapshot / 快照', 'Preserve data date / 保留数据日期'), ('Render / 渲染', 'HTML + run.json'), ('Verify / 核验', 'Published bytes / 线上内容比对')]
        if kind == 'freshness':
            labels = [('generated_at', 'Page generation / 页面生成时间'), ('data_as_of', 'Original data date / 数据原始日期'), ('mode', 'demo / live / cached / fallback')]
        if portrait or kind == 'freshness':
            step = (bottom-top)/len(labels)
            for i, (key, value) in enumerate(labels):
                yy = top+i*step
                panel(d, (pad, yy, w-pad, yy+step-18))
                end = text(d, (pad+24, yy+15), key, 34 if portrait else 30, pw-48, 'zh', MINT)
                text(d, (pad+24 if portrait else pad+550, end+8 if portrait else yy+17), value, 27, pw-48 if portrait else pw-580, 'zh')
        else:
            bw = (pw-4*20)/5
            for i, (key, value) in enumerate(labels):
                xx = pad+i*(bw+20)
                panel(d, (xx, top+20, xx+bw, bottom-20))
                yy = text(d, (xx+18, top+42), f'0{i+1}', 44, bw-36, color=MINT)
                yy = text(d, (xx+18, yy+12), key, 28, bw-36, 'zh')
                text(d, (xx+18, yy+20), value, 24, bw-36, 'zh', MUTED)
    elif kind == 'runs':
        items = [('5', 'live / 实时标记', MINT), ('105', 'fallback / 降级标记', AMBER), ('17', 'incomplete / 未见完整成功', MUTED)]
        for i, (number, label, color) in enumerate(items):
            if portrait:
                step = (bottom-top-65)/3
                xx, yy, bw, bh = pad, top+i*step, pw, step-18
            else:
                bw, bh = (pw-40)/3, bottom-top-70
                xx, yy = pad+i*(bw+20), top
            panel(d, (xx, yy, xx+bw, yy+bh))
            end = text(d, (xx+26, yy+12), number, 104, bw-52, color=color)
            text(d, (xx+26, end+8), label, 25, bw-52, 'zh')
        text(d, (pad, bottom-42), '2026-06-15 to 2026-09-01 / Retained logs only', 23, pw, color=MUTED)
    elif kind == 'end':
        panel(d, (pad, top, w-pad, bottom))
        yy = text(d, (pad+28, top+24), 'FreeTrade', 85 if portrait else 95, pw-56, color=MINT)
        yy = text(d, (pad+28, yy+12), 'github.com/eust-w/freetrade', 35 if portrait else 43, pw-56, color=INK)
        yy = text(d, (pad+28, yy+25), 'MIT / Python / Offline demo', 30, pw-56, color=MUTED)
        yy = text(d, (pad+28, yy+20), 'Research only. No return claims.', 28, pw-56, color=AMBER)
        text(d, (pad+28, yy+10), '研究用途，不构成投资建议。', 28, pw-56, 'zh', MUTED)
    text(d, (pad, h-(115 if portrait else 58)), f'0{index+1}/07   SYNTHETIC DEMO / 合成演示', 21, pw, 'zh', MUTED)
    return img


def captioned(base, line, narration, portrait):
    img = base.copy()
    d = ImageDraw.Draw(img)
    w, h = img.size
    pad = 72 if portrait else 88
    top, bottom = h-(460 if portrait else 290), h-(145 if portrait else 80)
    d.rounded_rectangle((pad-20, top, w-pad+20, bottom), 18, fill='#081e28')
    order = [narration, 'en' if narration == 'zh' else 'zh']
    y = top+18
    for lang in order:
        size = (36 if lang == 'zh' else 32) if portrait else (35 if lang == 'zh' else 33)
        y = text(d, (pad, y), line[lang], size, w-2*pad, lang, INK if lang == narration else MINT)+10
    if y > bottom:
        raise ValueError(f'caption exceeds safe area: {line}')
    return img


def run(args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)


def probe(path):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(path)], text=True))


def concat(paths, output, audio=False):
    listing = output.with_suffix('.txt')
    listing.write_text(''.join(f"file '{path.name}'\n" for path in paths))
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(listing), '-c', 'pcm_s16le' if audio else 'copy', str(output)])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--language', choices=('zh', 'en', 'all'), default='all')
    parser.add_argument('--frames-only', action='store_true')
    args = parser.parse_args()
    scenes = json.loads((ROOT/'media/storyboard.bilingual.json').read_text())
    validate_storyboard(scenes)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {'fps': FPS, 'subtitles': 'burned-in Chinese + English; separate SRT files', 'synthetic_voice': True, 'music': None, 'versions': []}
    for lang in (('zh', 'en') if args.language == 'all' else (args.language,)):
        work = OUT/lang
        work.mkdir(exist_ok=True)
        lines = [line for scene in scenes for line in scene['lines']]
        frames, audio_paths = [], []
        if not args.frames_only:
            for i, line in enumerate(lines):
                aiff, wav = work/f'voice-{i:02}.aiff', work/f'voice-{i:02}.wav'
                voice, rate = VOICES[lang]
                run(['say', '-v', voice, '-r', str(rate), '-o', str(aiff), line[lang]])
                count = math.ceil((probe(aiff)+0.25)*FPS)
                frames.append(count)
                run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(aiff), '-af', 'apad', '-t', str(count/FPS), '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', str(wav)])
                audio_paths.append(wav)
            concat(audio_paths, work/'narration.wav', audio=True)
            for subtitle in ('zh', 'en', 'bilingual'):
                (OUT/f'freetrade-{lang}-voice.{subtitle}.srt').write_text(make_srt(lines, frames, subtitle))
        for portrait in (False, True):
            aspect = 'portrait' if portrait else 'landscape'
            clips, index = [], 0
            for scene_index, scene in enumerate(scenes):
                base = base_frame(scene, scene_index, lang, portrait)
                base.save(work/f'scene-{scene_index:02}-{aspect}.png')
                if scene_index == 0:
                    cover_size = (900, 1200) if portrait else (1280, 720)
                    ImageOps.fit(base, cover_size, centering=(0.5, 0)).save(OUT/f'cover-{lang}-{aspect}.jpg', quality=94)
                for line_index, line in enumerate(scene['lines']):
                    still = work/f'caption-{index:02}-{aspect}.png'
                    captioned(base, line, lang, portrait).save(still)
                    if not args.frames_only:
                        clip = work/f'clip-{index:02}-{aspect}.mp4'
                        filters = 'fade=t=in:st=0:d=0.18' if line_index == 0 else 'null'
                        run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-loop', '1', '-framerate', str(FPS), '-i', str(still), '-vf', filters, '-frames:v', str(frames[index]), '-an', '-c:v', 'libx264', '-threads', '4', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', str(clip)])
                        clips.append(clip)
                    index += 1
            if args.frames_only:
                continue
            picture = work/f'picture-{aspect}.mp4'
            concat(clips, picture)
            output = OUT/f'freetrade-{lang}-bilingual-{aspect}.mp4'
            run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(picture), '-i', str(work/'narration.wav'), '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-metadata:s:a:0', f'language={"zho" if lang == "zh" else "eng"}', '-movflags', '+faststart', str(output)])
            manifest['versions'].append({'file': output.name, 'narration': lang, 'voice': VOICES[lang][0], 'frames': sum(frames), 'duration_seconds': probe(output), 'width': 1080 if portrait else 1920, 'height': 1920 if portrait else 1080})
            print(f'Exported {output.name}: {probe(output):.2f}s', flush=True)
    if not args.frames_only:
        (OUT/'manifest.json').write_text(json.dumps(manifest, indent=2))
        assets = sorted(path for path in OUT.iterdir() if path.suffix in ('.mp4', '.srt', '.jpg', '.json'))
        (OUT/'SHA256SUMS.txt').write_text(''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n' for path in assets))


if __name__ == '__main__':
    main()
