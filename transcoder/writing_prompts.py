"""Writing prompts for teaching Chinese as a foreign language (TCFL).

Each prompt carries a level hint and a length target so grading can be read in
context. Random selection mirrors the translation warm-start behaviour.
"""

import random
from typing import Dict, List

PROMPTS: List[Dict[str, str]] = [
    {
        "id": "hometown",
        "level": "HSK 3",
        "title": "我的家乡",
        "prompt": "请以《我的家乡》为题，写一篇 150 字左右的短文。介绍你家乡的位置、气候、有名的食物，以及你对家乡的感情。",
    },
    {
        "id": "trip",
        "level": "HSK 4",
        "title": "一次难忘的旅行",
        "prompt": "请以《一次难忘的旅行》为题，写一篇 200 字左右的短文。写清楚你去了哪里、和谁一起、发生了什么难忘的事，以及你的感受。",
    },
    {
        "id": "learning-chinese",
        "level": "HSK 4",
        "title": "学习汉语的经历",
        "prompt": "请以《学习汉语的经历》为题，写一篇 200 字左右的短文。谈谈你学习汉语的原因、遇到的困难，以及你的学习方法。",
    },
    {
        "id": "friend",
        "level": "HSK 4",
        "title": "介绍一位朋友",
        "prompt": "请以《我的一位好朋友》为题，写一篇 200 字左右的短文。介绍他/她的外貌、性格、爱好，并说明你们为什么成为朋友。",
    },
    {
        "id": "phone",
        "level": "HSK 5",
        "title": "手机与我们的生活",
        "prompt": "请以《手机与我们的生活》为题，写一篇 250 字左右的议论文。谈谈手机给生活带来的方便和问题，并说说你的看法。",
    },
    {
        "id": "environment",
        "level": "HSK 5",
        "title": "保护环境，从我做起",
        "prompt": "请以《保护环境，从我做起》为题，写一篇 250 字左右的短文。说明目前的环境问题，并提出两三条你可以做到的具体行动。",
    },
    {
        "id": "city-country",
        "level": "HSK 5",
        "title": "城市生活与乡村生活",
        "prompt": "请以《城市生活与乡村生活》为题，写一篇 250 字左右的文章。比较两种生活方式的优点和缺点，并说明你更喜欢哪一种，为什么。",
    },
    {
        "id": "dream-job",
        "level": "HSK 5",
        "title": "我的理想职业",
        "prompt": "请以《我的理想职业》为题，写一篇 250 字左右的短文。说明你想做什么工作、为什么选择它，以及你为此做了哪些准备。",
    },
    {
        "id": "festival",
        "level": "HSK 5",
        "title": "一个中国的节日",
        "prompt": "请以《我最喜欢的中国节日》为题，写一篇 250 字左右的短文。介绍这个节日的时间、习俗和意义，并说明你喜欢它的原因。",
    },
    {
        "id": "letter-teacher",
        "level": "HSK 4",
        "title": "给老师的一封信",
        "prompt": "请给你的汉语老师写一封信（约 200 字）。感谢他/她的帮助，谈谈你这学期的进步，并提出一个希望。注意书信格式。",
    },
    {
        "id": "misunderstanding",
        "level": "HSK 6",
        "title": "一次误会",
        "prompt": "请以《一次误会》为题，写一篇 300 字左右的记叙文。交代误会的起因、经过和结果，并写出你从中学到了什么。",
    },
    {
        "id": "ai-life",
        "level": "HSK 6",
        "title": "人工智能与未来生活",
        "prompt": "请以《人工智能与未来生活》为题，写一篇 300 字左右的议论文。谈谈人工智能可能带来的变化、风险和你的态度。",
    },
]


PROMPTS_EN: List[Dict[str, str]] = [
    {
        "id": "en-cet4-1", "level": "CET-4", "title": "On-campus Mobile Phone Use",
        "prompt": "Write a short essay (120-180 words) on the use of mobile phones on campus. "
                  "State your view, give two reasons, and suggest one practical rule students could follow.",
    },
    {
        "id": "en-cet6-1", "level": "CET-6", "title": "The Value of Failure",
        "prompt": "Write an essay (150-200 words) about the value of failure in learning. "
                  "Use a concrete example and explain what failure teaches that success does not.",
    },
    {
        "id": "en-kaoyan-1", "level": "考研英语", "title": "AI and the Future of Work",
        "prompt": "Write an essay (160-200 words) discussing how artificial intelligence may change "
                  "the job market. Present both opportunities and risks, and state your own position.",
    },
    {
        "id": "en-kaoyan-2", "level": "考研英语", "title": "Reading in a Digital Age",
        "prompt": "Write an essay (160-200 words) on whether deep reading is losing ground to short-form "
                  "content. Give reasons and suggest how students can protect sustained reading habits.",
    },
]

PROMPTS_JA: List[Dict[str, str]] = [
    {
        "id": "ja-n3-1", "level": "JLPT N3", "title": "私の日本語の勉強法",
        "prompt": "「私の日本語の勉強法」というテーマで、200字程度の作文を書いてください。"
                  "毎日していること、難しいと感じること、これからの目標を含めてください。",
    },
    {
        "id": "ja-n3-2", "level": "JLPT N3", "title": "ふるさとの思い出",
        "prompt": "「ふるさとの思い出」というテーマで、200字程度の作文を書いてください。"
                  "場所、人、印象に残っている出来事について書いてください。",
    },
    {
        "id": "ja-n2-1", "level": "JLPT N2", "title": "スマートフォンと私",
        "prompt": "「スマートフォンと私」というテーマで、250字程度の作文を書いてください。"
                  "便利な点と問題点を挙げ、自分なりの付き合い方を述べてください。",
    },
]

PROMPTS_BY_LANG = {"zh": PROMPTS, "en": PROMPTS_EN, "ja": PROMPTS_JA}


def random_prompt(lang: str = "zh") -> Dict[str, str]:
    """One writing prompt for the requested language (built-in + imported)."""
    bank = list(PROMPTS_BY_LANG.get(lang) or PROMPTS)
    try:
        from transcoder.content_store import user_writing_prompts

        bank += [p for p in user_writing_prompts() if (p.get("lang") or "zh") == lang]
    except Exception:
        pass
    return dict(random.choice(bank))
