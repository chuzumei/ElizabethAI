import re
from phonemizer import phonemize
from phonemizer.backend.espeak.wrapper import EspeakWrapper
from phonemizer.separator import Separator

EspeakWrapper.set_library(r"C:\Program Files\eSpeak NG\libespeak-ng.dll")

VOWELS = {
    "\u0250\u0303\u028a\u0303": "\u30ca\u30a6\u30f3",
    "e\u028a": "\u30a8\u30a6",
    "y": "\u30a4",

    "ũ": "ウン",
    "õ": "オン",
    "ĩ": "イン",
    "ẽ": "エン",
    "ʊ̃": "ウン",
    "a": "ア", "æ": "ア", "ɐ": "ア", "ɐ̃": "アン",
    "ɛ": "エ", "e": "エ", "i": "イ",
    "o": "オ", "ɔ": "オ", "u": "ウ", "ʊ": "ウ",
    "ɪ": "イ", "ə": "ア", "ɨ": "イ",
}

CONSONANTS = {
    "b": ("バ", "ビ", "ブ", "ベ", "ボ"),
    "d": ("ダ", "ディ", "ドゥ", "デ", "ド"),
    "f": ("ファ", "フィ", "フ", "フェ", "フォ"),
    "g": ("ガ", "ギ", "グ", "ゲ", "ゴ"),
    "k": ("カ", "キ", "ク", "ケ", "コ"),
    "m": ("マ", "ミ", "ム", "メ", "モ"),
    "n": ("ナ", "ニ", "ヌ", "ネ", "ノ"),
    "p": ("パ", "ピ", "プ", "ペ", "ポ"),
    "r": ("ラ", "リ", "ル", "レ", "ロ"),
    "ɾ": ("ラ", "リ", "ル", "レ", "ロ"),
    "s": ("サ", "シ", "ス", "セ", "ソ"),
    "t": ("タ", "ティ", "トゥ", "テ", "ト"),
    "v": ("ヴァ", "ヴィ", "ヴ", "ヴェ", "ヴォ"),
    "z": ("ザ", "ジ", "ズ", "ゼ", "ゾ"),
    "ʒ": ("ジャ", "ジ", "ジュ", "ジェ", "ジョ"),
    "ʃ": ("シャ", "シ", "シュ", "シェ", "ショ"),
    "tʃ": ("チャ", "チ", "チュ", "チェ", "チョ"),
    "dʒ": ("ジャ", "ジ", "ジュ", "ジェ", "ジョ"),
    "ɲ": ("ニャ", "ニ", "ニュ", "ニェ", "ニョ"),
    "l": ("ラ", "リ", "ル", "レ", "ロ"),
    "ʎ": ("リャ", "リ", "リュ", "リェ", "リョ"),
}

VOWEL_INDEX = {
    "y": 1,

    "ũ": 2,
    "õ": 4,
    "ĩ": 1,
    "ẽ": 3,
    "ʊ̃": 2,
    "a": 0, "æ": 0, "ɐ": 0, "ɐ̃": 0,
    "i": 1, "ɪ": 1, "ɨ": 1,
    "u": 2, "ʊ": 2,
    "e": 3, "ɛ": 3,
    "o": 4, "ɔ": 4,
}

def phones_to_kana(phones):
    result = []
    i = 0
    while i < len(phones):
        phone = phones[i]

        if phone in CONSONANTS:
            if i + 1 < len(phones) and phones[i + 1] in VOWEL_INDEX:
                vowel = phones[i + 1]
                result.append(CONSONANTS[phone][VOWEL_INDEX[vowel]])
                if vowel in ("ɐ̃", "ʊ̃", "ẽ", "ĩ", "õ", "ũ"):
                    result.append("ン")
                i += 2
                continue
            result.append(CONSONANTS[phone][2])
        elif phone in VOWELS:
            result.append(VOWELS[phone])
        elif phone in ("ŋ", "ɲ"):
            result.append("ン")
        elif phone == "w":
            result.append("ウ")
        elif phone == "j":
            result.append("イ")
        i += 1
    return "".join(result)

def convert_auto(text):
    phonetic = phonemize(
        text,
        language="pt-br",
        backend="espeak",
        separator=Separator(phone=" ", word=" | "),
        strip=True,
        preserve_punctuation=True,
    )
    words = phonetic.split(" | ")
    output = []
    for word in words:
        punctuation = ""
        match = re.search(r"[.,!?]+$", word)
        if match:
            punctuation = match.group()
            word = word[:match.start()]
        phones = word.strip().split()
        kana = phones_to_kana(phones)
        for mark in punctuation:
            kana += {".": "。", ",": "、", "!": "！", "?": "？"}.get(mark, "")
        output.append(kana)
    return "".join(output)
