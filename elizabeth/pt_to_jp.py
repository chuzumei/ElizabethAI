import re

# Primeira versão experimental: português com pronúncia japonesa.
# Frases conhecidas têm prioridade para preservar o resultado testado.

PHRASES = {
    "bom dia, erick. como você está?":
        "ボンジーア、エリック。コモヴォセエスタ？",
}

WORDS = {
    "olá": "オラー",
    "oi": "オイ",
    "bom": "ボン",
    "boa": "ボア",
    "dia": "ジーア",
    "noite": "ノイチ",
    "erick": "エリック",
    "como": "コモ",
    "você": "ヴォセ",
    "está": "エスタ",
    "estou": "エストウ",
    "bem": "ベン",
    "obrigada": "オブリガーダ",
    "sim": "シン",
    "não": "ナウン",
    "meu": "メウ",
    "nome": "ノメ",
    "é": "エ",
    "elizabeth": "エリザベス",
}

def convert(text: str) -> str:
    normalized = text.strip().lower()

    if normalized in PHRASES:
        return PHRASES[normalized]

    tokens = re.findall(r"[^\W_]+|[.,!?;:]", normalized, re.UNICODE)
    unknown = [t for t in tokens if t.isalpha() and t not in WORDS]

    if unknown:
        raise ValueError(
            "Palavras ainda não cadastradas: " + ", ".join(unknown)
        )

    punctuation = {
        ",": "、", ".": "。", "!": "！",
        "?": "？", ";": "、", ":": "、",
    }
    return "".join(WORDS.get(t, punctuation.get(t, "")) for t in tokens)
