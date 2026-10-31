"""Classic excerpts with established English renderings, used as the UI's
default warm-start example (random on every page load).

Translations follow widely used public renderings (Legge for the Four Books /
Dao De Jing where noted); they are illustrative, not experimental data.
"""

import random
from typing import Dict, List

SAMPLES: List[Dict[str, str]] = [
    {
        "title": "《论语·学而》",
        "source": "学而时习之，不亦说乎？有朋自远方来，不亦乐乎？人不知而不愠，不亦君子乎？",
        "en": "Is it not pleasant to learn with a constant perseverance and application? "
              "Is it not delightful to have friends coming from distant quarters? "
              "Is he not a man of complete virtue, who feels no discomposure though men may take no note of him?",
    },
    {
        "title": "《论语·为政》",
        "source": "学而不思则罔，思而不学则殆。",
        "en": "Learning without thought is labour lost; thought without learning is perilous.",
    },
    {
        "title": "《论语·述而》",
        "source": "三人行，必有我师焉。择其善者而从之，其不善者而改之。",
        "en": "When I walk along with two others, they may serve me as my teachers. "
              "I will select their good qualities and follow them, their bad qualities and avoid them.",
    },
    {
        "title": "《道德经·第一章》",
        "source": "道可道，非常道；名可名，非常名。",
        "en": "The Tao that can be trodden is not the enduring and unchanging Tao. "
              "The name that can be named is not the enduring and unchanging name.",
    },
    {
        "title": "《道德经·第六十四章》",
        "source": "合抱之木，生于毫末；九层之台，起于累土；千里之行，始于足下。",
        "en": "The tree which fills the arms grew from the tiniest sprout; "
              "the tower of nine storeys rose from a small heap of earth; "
              "the journey of a thousand li commenced with a single step.",
    },
    {
        "title": "《孟子·告子下》",
        "source": "天将降大任于是人也，必先苦其心志，劳其筋骨，饿其体肤，空乏其身。",
        "en": "When Heaven is about to confer a great office on any man, it first exercises his mind with suffering, "
              "and his sinews and bones with toil. It exposes his body to hunger, and subjects him to extreme poverty.",
    },
    {
        "title": "《荀子·劝学》",
        "source": "不积跬步，无以至千里；不积小流，无以成江海。",
        "en": "Without accumulating single steps, one cannot reach a thousand li; "
              "without accumulating small streams, one cannot form rivers and seas.",
    },
    {
        "title": "《庄子·养生主》",
        "source": "吾生也有涯，而知也无涯。",
        "en": "My life has a limit, but my knowledge has none.",
    },
    {
        "title": "《岳阳楼记》",
        "source": "先天下之忧而忧，后天下之乐而乐。",
        "en": "To be the first to bear the world's worries, and the last to enjoy its pleasures.",
    },
    {
        "title": "《滕王阁序》",
        "source": "落霞与孤鹜齐飞，秋水共长天一色。",
        "en": "The setting clouds and the solitary wild duck fly together; "
              "the autumn river and the vast sky merge in one colour.",
    },
    {
        "title": "《水调歌头》",
        "source": "但愿人长久，千里共婵娟。",
        "en": "May we all be blessed with long life, and though a thousand li apart, share the beauty of the moon.",
    },
    {
        "title": "《横渠语录》",
        "source": "为天地立心，为生民立命，为往圣继绝学，为万世开太平。",
        "en": "To establish the heart of Heaven and Earth, to establish the mission of the people, "
              "to continue the lost learning of the sages, and to open peace for all generations.",
    },
]


def random_sample() -> Dict[str, str]:
    """One classic excerpt per page load."""
    return dict(random.choice(SAMPLES))
