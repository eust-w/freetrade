import copy
import importlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def media_module():
    assert importlib.util.find_spec('media.build_bilingual') is not None, 'bilingual renderer is missing'
    return importlib.import_module('media.build_bilingual')


def test_subtitle_clock_carries_milliseconds():
    media = media_module()
    assert media.timecode(59.9996) == '00:01:00,000'
    assert media.timecode(3661.2) == '01:01:01,200'
    with pytest.raises(ValueError):
        media.timecode(-1)


def test_captions_follow_exact_video_frames():
    media = media_module()
    lines = [{'zh': '中文一', 'en': 'English one'}, {'zh': '中文二', 'en': 'English two'}]
    srt = media.make_srt(lines, [24, 36], 'en')
    assert '00:00:00,000 --> 00:00:01,000\nEnglish one' in srt
    assert '00:00:01,000 --> 00:00:02,500\nEnglish two' in srt
    both = media.make_srt(lines, [24, 36], 'bilingual')
    assert '中文一\nEnglish one' in both
    with pytest.raises(ValueError):
        media.make_srt(lines, [24], 'en')


def test_storyboard_requires_both_languages_and_distinct_scenes():
    media = media_module()
    scenes = json.loads((Path(__file__).resolve().parents[1] / 'media/storyboard.bilingual.json').read_text())
    media.validate_storyboard(scenes)
    assert len(scenes) == 7
    assert sum(len(scene['lines']) for scene in scenes) == 14
    broken = copy.deepcopy(scenes)
    broken[0]['lines'][0]['en'] = ''
    with pytest.raises(ValueError):
        media.validate_storyboard(broken)
    broken = copy.deepcopy(scenes)
    broken[1]['kind'] = broken[0]['kind']
    with pytest.raises(ValueError):
        media.validate_storyboard(broken)
