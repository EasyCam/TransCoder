"""English reading comprehension bank: CET-4, CET-6 and postgraduate entrance exam.

All passages are original texts written for this project (no copyrighted
material). Each article ships with four multiple-choice questions, an answer
key and Chinese explanations.
"""

import random
from typing import Any, Dict, List, Optional

ARTICLES: List[Dict[str, Any]] = [
    # ---------------------------------------------------------------- CET-4
    {
        "id": "cet4-1",
        "exam": "cet4",
        "year": "模拟",
        "paper": "原创模拟卷 A",
        "title": "The Quiet Cost of Convenience",
        "passage": (
            "Ordering food with a phone takes less than a minute. A few taps, and a meal "
            "arrives at the door. For students and office workers, this convenience is hard to "
            "resist. Yet convenience has a quiet cost.\n\n"
            "Researchers at a university in Shanghai followed 1,200 young adults for a year. "
            "Those who ordered takeout more than five times a week spent about 30 percent more "
            "on food than those who cooked at home. They also reported lower satisfaction with "
            "their diet. The reason is simple: when we do not choose ingredients, we tend to "
            "accept whatever is fast and salty.\n\n"
            "The problem is not technology itself. Delivery apps have created jobs and helped "
            "small restaurants reach new customers. The real issue is that convenience removes "
            "small decisions, and those decisions are what keep us aware of what we eat. "
            "Cooking once a week, or simply reading the menu more carefully, can bring some of "
            "those decisions back."
        ),
        "questions": [
            {
                "q": "What did the Shanghai study find about frequent takeout users?",
                "options": [
                    "They saved more money than home cooks.",
                    "They spent more on food and were less satisfied with their diet.",
                    "They cooked more often than other groups.",
                    "They exercised less than home cooks.",
                ],
                "answer": 1,
                "explain": "第二段明确提到：每周外卖超过五次的人食品支出高约 30%，且对饮食满意度更低。",
            },
            {
                "q": "According to the passage, why do takeout eaters often eat worse?",
                "options": [
                    "They do not choose ingredients themselves.",
                    "They dislike vegetables.",
                    "Delivery is always more expensive.",
                    "Restaurants use too little salt.",
                ],
                "answer": 0,
                "explain": "第三句给出原因：不自己挑食材，就容易接受又快又咸的食物。",
            },
            {
                "q": "What is the author's attitude towards delivery apps?",
                "options": [
                    "Completely negative.",
                    "Supportive of the technology but concerned about its side effects.",
                    "Uninterested.",
                    "Unclear.",
                ],
                "answer": 1,
                "explain": "第四段说“问题不在技术本身”，并肯定其创造就业、帮助小餐馆；作者担心的是副作用。",
            },
            {
                "q": "What does the author suggest as a practical step?",
                "options": [
                    "Never ordering takeout again.",
                    "Moving closer to restaurants.",
                    "Cooking occasionally or reading menus more carefully.",
                    "Spending less money on food.",
                ],
                "answer": 2,
                "explain": "末句建议：每周自己做一次饭，或更仔细地看菜单，把“小决定”找回来。",
            },
        ],
    },
    {
        "id": "cet4-2",
        "exam": "cet4",
        "year": "模拟",
        "paper": "原创模拟卷 B",
        "title": "Why Libraries Still Matter",
        "passage": (
            "Some people predict that libraries will disappear because almost everything can be "
            "found online. The prediction has not come true. In many cities, library visits have "
            "actually increased over the past decade.\n\n"
            "One reason is that a library is more than a store of books. It is one of the few "
            "public places where people can stay for hours without spending money. Students "
            "prepare for exams, older people read newspapers, and parents bring children to "
            "story hours. For people who live in small apartments, the library offers quiet "
            "space that home cannot provide.\n\n"
            "Another reason is trust. When people search online, they must decide whether a "
            "source is reliable. Librarians are trained to help with exactly that question. A "
            "recent survey found that readers who used library services were more confident in "
            "judging the quality of information.\n\n"
            "Libraries do face budget pressure, and they must change with the times. But the "
            "idea that they are outdated misunderstands what they offer: not just books, but "
            "space, guidance and a sense of community."
        ),
        "questions": [
            {
                "q": "What has happened to library visits in many cities?",
                "options": ["They have fallen sharply.", "They have increased.", "They have stayed the same.", "They are unknown."],
                "answer": 1,
                "explain": "第一段末句：许多城市图书馆访问量在过去十年实际上升。",
            },
            {
                "q": "Which group uses libraries as quiet study space?",
                "options": ["Only older people.", "Only children.", "Students preparing for exams.", "Tourists."],
                "answer": 2,
                "explain": "第二段列举学生备考、老人读报、家长带孩子听故事，学生备考即安静学习空间。",
            },
            {
                "q": "Why does the author mention trust?",
                "options": [
                    "To show librarians help people judge information quality.",
                    "To argue that online sources are always false.",
                    "To explain why libraries need more money.",
                    "To criticize young readers.",
                ],
                "answer": 0,
                "explain": "第三段：图书馆员受过训练，能帮助读者判断信息是否可靠。",
            },
            {
                "q": "What is the main idea of the passage?",
                "options": [
                    "Libraries should replace the internet.",
                    "Libraries remain valuable for space, guidance and community.",
                    "Books are more important than computers.",
                    "Library budgets are growing quickly.",
                ],
                "answer": 1,
                "explain": "末段总结：图书馆提供的不仅是书，还有空间、指导和社区感。",
            },
        ],
    },
    # ---------------------------------------------------------------- CET-6
    {
        "id": "cet6-1",
        "exam": "cet6",
        "year": "模拟",
        "paper": "原创模拟卷 A",
        "title": "The Limits of Willpower",
        "passage": (
            "For decades, popular psychology treated willpower as a muscle: use it and it grows "
            "tired, train it and it becomes stronger. New research suggests the picture is more "
            "complicated. What looks like a lack of willpower is often a problem of environment.\n\n"
            "In one study, participants were asked to resist snacks placed on their desks. Those "
            "who succeeded were not necessarily more disciplined; they were more likely to have "
            "moved the snacks out of sight before starting work. In another study, students who "
            "planned exactly when and where they would study were far more likely to follow "
            "through than those who simply promised to try harder.\n\n"
            "This does not mean effort is unimportant. It means that relying on effort alone is "
            "fragile. When people are tired, hungry or stressed, self-control weakens for almost "
            "everyone. Designing the environment — keeping fruit visible, silencing the phone, "
            "scheduling a specific hour — reduces the number of times willpower is needed.\n\n"
            "The practical lesson is modest but useful: do not ask how to become a stronger "
            "person. Ask how to make the better choice the easier one."
        ),
        "questions": [
            {
                "q": "What does new research suggest about willpower?",
                "options": [
                    "It works exactly like a muscle.",
                    "Environment often matters more than raw effort.",
                    "It cannot be trained at all.",
                    "It is the same for everyone.",
                ],
                "answer": 1,
                "explain": "首段末句与全文主旨：看似意志力不足，往往是环境问题。",
            },
            {
                "q": "What did successful participants in the snack study tend to do?",
                "options": [
                    "They ate the snacks quickly.",
                    "They moved the snacks out of sight.",
                    "They avoided the laboratory.",
                    "They exercised before work.",
                ],
                "answer": 1,
                "explain": "第二段：成功者更可能在开始工作前把零食移出视线。",
            },
            {
                "q": "What does the author mean by 'relying on effort alone is fragile'?",
                "options": [
                    "Effort has no value.",
                    "Self-control drops when people are tired or stressed.",
                    "Only athletes can control themselves.",
                    "Planning is a waste of time.",
                ],
                "answer": 1,
                "explain": "第三段：疲惫、饥饿或压力大时，几乎所有人的自控力都会下降。",
            },
            {
                "q": "Which of the following best states the practical lesson?",
                "options": [
                    "Become a stronger person first.",
                    "Avoid all difficult tasks.",
                    "Make the better choice the easier one.",
                    "Trust willpower completely.",
                ],
                "answer": 2,
                "explain": "末句原话：不要问如何变强，而要问如何让更好的选择更容易。",
            },
        ],
    },
    {
        "id": "cet6-2",
        "exam": "cet6",
        "year": "模拟",
        "paper": "原创模拟卷 B",
        "title": "Cities Designed for Walking",
        "passage": (
            "Urban planners increasingly argue that a city's health can be measured by how "
            "comfortable it is to walk in. The claim is not only about exercise. Walking connects "
            "people with shops, schools and neighbours, and it reduces the traffic that makes "
            "streets unpleasant in the first place.\n\n"
            "Yet many cities were designed for cars. Wide roads, long blocks and large parking "
            "lots make walking inconvenient, even dangerous. When a street has no shade, no "
            "benches and no crossings, only those who have no choice will walk.\n\n"
            "Some cities have tried simple changes. Barcelona created 'superblocks' by closing "
            "some streets to through traffic. Paris added hundreds of kilometres of cycle lanes "
            "and widened pavements. In both cases, local shops reported more customers, not "
            "fewer, although some drivers complained about longer journeys.\n\n"
            "The lesson is that walkability is a design decision, not a matter of individual "
            "willpower. A city that makes walking pleasant will have more walkers, and more "
            "walkers make the streets safer and livelier for everyone."
        ),
        "questions": [
            {
                "q": "What do urban planners say about walking?",
                "options": [
                    "It is only about physical exercise.",
                    "It reflects a city's health and social life.",
                    "It should be limited to city centres.",
                    "It causes traffic jams.",
                ],
                "answer": 1,
                "explain": "首段：步行舒适度可衡量城市健康，且连接商店、学校与邻里。",
            },
            {
                "q": "Why is walking inconvenient in many cities?",
                "options": [
                    "They were designed around cars.",
                    "There are too many benches.",
                    "The weather is always bad.",
                    "People prefer driving.",
                ],
                "answer": 0,
                "explain": "第二段：宽马路、长街区、大停车场使步行不便甚至危险。",
            },
            {
                "q": "What happened after Barcelona and Paris made changes?",
                "options": [
                    "Local shops lost all their customers.",
                    "Local shops reported more customers.",
                    "All drivers stopped complaining.",
                    "Walking decreased.",
                ],
                "answer": 1,
                "explain": "第三段末：两地本地商店报告顾客更多，尽管部分司机抱怨绕路。",
            },
            {
                "q": "What is the author's conclusion?",
                "options": [
                    "Walkability depends on design, not just willpower.",
                    "Cities should ban all cars.",
                    "Walking is impossible in modern cities.",
                    "Drivers should decide urban policy.",
                ],
                "answer": 0,
                "explain": "末段：步行友好是设计决定，不是个人意志问题。",
            },
        ],
    },
    # ------------------------------------------------------- Postgraduate exam
    {
        "id": "kaoyan-1",
        "exam": "kaoyan",
        "year": "模拟",
        "paper": "英语一 模拟",
        "title": "The Attention Economy Reconsidered",
        "passage": (
            "The phrase 'attention economy' describes a simple bargain: platforms offer free "
            "services, and users pay with their time and attention. Critics argue that this "
            "bargain is unfair because the true cost is invisible. A user may notice an hour "
            "spent scrolling, but not the hour of concentrated work that never happened.\n\n"
            "Economists have begun to measure this cost. In field experiments, workers who were "
            "allowed to keep their phones nearby completed fewer tasks than those whose phones "
            "were placed in another room. The difference was largest for tasks requiring "
            "sustained reasoning. Notably, the mere presence of the phone mattered, even when it "
            "was silent and face down.\n\n"
            "These findings complicate the idea that attention is a personal responsibility. If "
            "an environment is designed to interrupt, individual discipline can only do so much. "
            "Some companies have responded by setting 'quiet hours' or removing notification "
            "badges from internal tools. Early reports suggest modest but real gains in "
            "productivity and reported well-being.\n\n"
            "None of this implies that users bear no responsibility. It implies that the debate "
            "should move from blaming individuals to designing environments — digital and "
            "physical — that make sustained attention possible."
        ),
        "questions": [
            {
                "q": "What is the 'invisible cost' mentioned in paragraph 1?",
                "options": [
                    "The subscription fee users pay.",
                    "The concentrated work that is never done.",
                    "The electricity used by platforms.",
                    "The advertising revenue of companies.",
                ],
                "answer": 1,
                "explain": "首段：用户能注意到刷了一小时，却注意不到因此少做的一小时专注工作。",
            },
            {
                "q": "What did the field experiments show?",
                "options": [
                    "Phones had no effect on performance.",
                    "Having a phone nearby reduced task completion, especially for reasoning tasks.",
                    "Workers performed better with phones nearby.",
                    "Only silent phones caused problems.",
                ],
                "answer": 1,
                "explain": "第二段：手机在场（即使静音、屏幕朝下）也会降低任务完成量，对持续推理任务影响最大。",
            },
            {
                "q": "Why do the findings 'complicate' personal responsibility?",
                "options": [
                    "Because discipline is irrelevant.",
                    "Because environments designed to interrupt limit what discipline can achieve.",
                    "Because companies refuse to change.",
                    "Because workers cannot be measured.",
                ],
                "answer": 1,
                "explain": "第三段：如果环境本身被设计成不断打断，个人自律能起的作用有限。",
            },
            {
                "q": "What does the author recommend?",
                "options": [
                    "Blaming users for weak willpower.",
                    "Removing all digital tools.",
                    "Designing environments that support sustained attention.",
                    "Ignoring the attention economy.",
                ],
                "answer": 2,
                "explain": "末段：争论应从指责个人转向设计能支持持续注意力的环境（数字与物理）。",
            },
        ],
    },
    {
        "id": "kaoyan-2",
        "exam": "kaoyan",
        "year": "模拟",
        "paper": "英语一 模拟",
        "title": "Translation as Interpretation",
        "passage": (
            "For a long time, translation was judged by a single standard: fidelity. A good "
            "translation was one that stayed close to the original, sentence by sentence. Modern "
            "translation studies have complicated this view. Meaning, after all, is not carried "
            "only by words; it is also carried by rhythm, allusion and the expectations of "
            "readers.\n\n"
            "Consider poetry. A literal rendering may preserve every image yet lose the music "
            "that made the poem memorable. A freer translation may sound beautiful in the target "
            "language while quietly replacing the author's concerns with the translator's. "
            "Neither approach can be declared correct in advance; the choice depends on what the "
            "translation is for.\n\n"
            "This does not mean that 'anything goes'. Translators remain accountable to the "
            "source, and readers deserve to know what has been changed. The most useful "
            "translations are often those accompanied by notes explaining difficult choices — a "
            "practice that treats readers as partners rather than passive receivers.\n\n"
            "Understood this way, translation is less a mechanical transfer than an act of "
            "interpretation, and like any interpretation it can be defended, questioned and "
            "improved."
        ),
        "questions": [
            {
                "q": "What was the traditional standard for judging translation?",
                "options": ["Fidelity to the original.", "Rhythm and music.", "Reader popularity.", "The translator's fame."],
                "answer": 0,
                "explain": "首段：长期以来翻译以“忠实”为单一标准，逐句贴近原文。",
            },
            {
                "q": "What problem does the poetry example illustrate?",
                "options": [
                    "Poetry cannot be translated at all.",
                    "Literal and free approaches each sacrifice something.",
                    "Translators should avoid poetry.",
                    "Readers prefer literal translations.",
                ],
                "answer": 1,
                "explain": "第二段：直译可能保住意象却失去音乐性，意译可能好听却替换了作者的关切。",
            },
            {
                "q": "What does the author mean by 'anything goes'?",
                "options": [
                    "Every translation is equally good.",
                    "Translators have complete freedom.",
                    "The idea that standards do not matter at all.",
                    "Readers do not care about accuracy.",
                ],
                "answer": 2,
                "explain": "第三段开头“这不意味着‘怎么都行’”，即否定毫无标准的做法。",
            },
            {
                "q": "Which statement best reflects the author's view?",
                "options": [
                    "Translation is a mechanical transfer of words.",
                    "Translation is interpretation and should be openly explained.",
                    "Notes make translations less useful.",
                    "Only literal translation is defensible.",
                ],
                "answer": 1,
                "explain": "末段：翻译更像解释行为，可被辩护、质疑和改进；前文也强调加注说明取舍。",
            },
        ],
    },
    # ------------------------------------------------------------- JLPT
    {
        "id": "jlpt-n3-1",
        "exam": "jlpt",
        "year": "模拟",
        "paper": "N3 原创模拟",
        "title": "図書館の案内",
        "passage": (
            "市立図書館は、朝九時から夜八時まで開いています。月曜日は休みです。"
            "本を借りるときは、カウンターでカードを見せてください。一度に五冊まで、"
            "二週間借りることができます。返すのが遅くなった場合は、一冊につき一日百円を"
            "払わなければなりません。図書館の三階には静かに勉強できる部屋があります。"
            "飲み物は持って入れますが、食べ物はだめです。"
        ),
        "questions": [
            {"q": "図書館が休みなのはいつですか。", "options": ["月曜日", "日曜日", "祝日", "毎月一日"], "answer": 0,
             "explain": "第一句后明确说「月曜日は休みです」（周一休息）。"},
            {"q": "一度に何冊借りられますか。", "options": ["三冊", "五冊", "八冊", "十冊"], "answer": 1,
             "explain": "文中「一度に五冊まで」即一次最多五册。"},
            {"q": "返すのが遅れた場合、どうしますか。", "options": ["カードを見せる", "お金を払う", "部屋を予約する", "本を買う"], "answer": 1,
             "explain": "「一冊につき一日百円を払わなければなりません」= 每册每天罚款 100 日元。"},
            {"q": "三階の部屋でしてはいけないことは何ですか。", "options": ["勉強する", "飲み物を飲む", "食べ物を食べる", "本を読む"], "answer": 2,
             "explain": "「飲み物は持って入れますが、食べ物はだめです」= 可带饮品，不可带食物。"},
        ],
    },
    {
        "id": "jlpt-n2-1",
        "exam": "jlpt",
        "year": "模拟",
        "paper": "N2 原创模拟",
        "title": "在宅勤務の広がり",
        "passage": (
            "在宅勤務が広がったことで、通勤時間がなくなり、家族と過ごす時間が増えたという声がある一方で、"
            "仕事と生活の区切りが曖昧になったという指摘もある。ある調査によれば、在宅勤務を続けたいと"
            "答えた人は六割を超えたが、その理由として最も多かったのは「通勤が不要になること」ではなく、"
            "「自分のペースで作業できること」だった。企業側には、評価の方法を見直すことが求められている。"
        ),
        "questions": [
            {"q": "在宅勤務の良い点として挙げられているのはどれか。", "options": ["給料が上がる", "家族と過ごす時間が増える", "評価が簡単になる", "通勤が長くなる"], "answer": 1,
             "explain": "开头提到「家族と過ごす時間が増えた」。"},
            {"q": "調査で最も多かった理由は何か。", "options": ["通勤が不要", "自分のペースで作業できる", "会社が遠い", "家族が多い"], "answer": 1,
             "explain": "「最も多かったのは…『自分のペースで作業できること』だった」。"},
            {"q": "企業に求められていることは何か。", "options": ["通勤手当を減らす", "評価の方法を見直す", "在宅勤務を禁止する", "家族と働く"], "answer": 1,
             "explain": "末句「評価の方法を見直すことが求められている」。"},
            {"q": "この文章の内容と合っているものはどれか。", "options": ["在宅勤務には課題もある", "全員が在宅勤務をやめたい", "通勤時間が増えた", "企業は調査を行っていない"], "answer": 0,
             "explain": "全文既讲好处也讲「仕事と生活の区切りが曖昧になった」等课题。"},
        ],
    },
    # -------------------------------------------------------------- HSK
    {
        "id": "hsk4-1",
        "exam": "hsk",
        "year": "模拟",
        "paper": "HSK 4 原创模拟",
        "title": "共享单车的便利与问题",
        "passage": (
            "共享单车刚出现的时候，很多人觉得它解决了“最后一公里”的问题。只要用手机扫一下，"
            "就能骑走一辆车，既方便又便宜。可是，随着车辆越来越多，新的问题也出现了：有的车被"
            "随便停在人行道上，影响行人走路；有的车坏了以后很久没有人修理。为了解决这些问题，"
            "一些城市开始划定停车区域，并要求公司及时维修。共享单车能不能真正方便大家，"
            "不仅取决于技术，也取决于使用者的习惯。"
        ),
        "questions": [
            {"q": "共享单车最初解决了什么问题？", "options": ["交通堵塞", "最后一公里", "空气污染", "停车费用"], "answer": 1,
             "explain": "第一句明确说解决了“最后一公里”的问题。"},
            {"q": "文中提到的“新问题”不包括哪一项？", "options": ["随便停车", "车辆损坏没人修", "价格太贵", "影响行人"], "answer": 2,
             "explain": "文中说“既方便又便宜”，价格贵不是提到的问题。"},
            {"q": "一些城市采取了什么办法？", "options": ["禁止共享单车", "划定停车区域并要求维修", "降低车费", "增加汽车数量"], "answer": 1,
             "explain": "“划定停车区域，并要求公司及时维修”。"},
            {"q": "作者认为共享单车能否真正方便大家，取决于什么？", "options": ["只有技术", "技术和使用者的习惯", "只有公司", "只有政府"], "answer": 1,
             "explain": "末句：不仅取决于技术，也取决于使用者的习惯。"},
        ],
    },
    {
        "id": "hsk5-1",
        "exam": "hsk",
        "year": "模拟",
        "paper": "HSK 5 原创模拟",
        "title": "慢下来，才能看清",
        "passage": (
            "现代人习惯了快：吃饭要快，走路要快，连休息也要“高效”。可是，有些事情恰恰不能快。"
            "比如学一门语言，如果只追求记住多少单词，而不肯花时间听、说、读，学到的知识很难真正"
            "变成能力。再比如交朋友，真正的信任需要时间积累，急于求成反而容易失去。慢并不是懒惰，"
            "而是一种选择：把时间花在真正重要的事情上。会生活的人，知道什么时候该快，什么时候该慢。"
        ),
        "questions": [
            {"q": "作者对“快”的态度是什么？", "options": ["完全否定", "认为有些事不能快", "主张所有事都要快", "没有表态"], "answer": 1,
             "explain": "第二句“有些事情恰恰不能快”，并非完全否定快。"},
            {"q": "学语言的例子说明什么？", "options": ["背单词最重要", "只求速度难以形成能力", "听说读写可以忽略", "语言学习很简单"], "answer": 1,
             "explain": "只追求记单词、不肯花时间听说是难以把知识变成能力的。"},
            {"q": "作者认为“慢”是什么？", "options": ["懒惰", "一种选择", "浪费时间", "没有效率"], "answer": 1,
             "explain": "“慢并不是懒惰，而是一种选择”。"},
            {"q": "本文最合适的标题是哪一个？", "options": ["越快越好", "慢下来，才能看清", "如何背单词", "高效休息法"], "answer": 1,
             "explain": "全文围绕“该慢的时候要慢”，标题即文章主旨。"},
        ],
    },
]


def _all_articles() -> List[Dict[str, Any]]:
    from transcoder.reading_store import list_user_articles

    builtin = [dict(a, source="builtin") for a in ARTICLES]
    user = [dict(a, source="user") for a in list_user_articles()]
    return builtin + user


def catalog() -> List[Dict[str, Any]]:
    """Selectable articles: exam / year / paper / title (no answer key)."""
    return [
        {
            "id": a["id"],
            "exam": a.get("exam", ""),
            "year": a.get("year", ""),
            "paper": a.get("paper", ""),
            "title": a.get("title", ""),
            "source": a.get("source", "builtin"),
            "questions": len(a.get("questions") or []),
        }
        for a in _all_articles()
    ]


def get_article(article_id: str) -> Optional[Dict[str, Any]]:
    return next((a for a in _all_articles() if a.get("id") == article_id), None)


def public_article(a: Dict[str, Any]) -> Dict[str, Any]:
    """Strip the answer key before sending to the browser."""
    return {
        "id": a["id"],
        "exam": a.get("exam", ""),
        "year": a.get("year", ""),
        "paper": a.get("paper", ""),
        "title": a.get("title", ""),
        "source": a.get("source", "builtin"),
        "has_key": bool(a.get("has_key", True)),
        "passage": a.get("passage", ""),
        "questions": [
            {"q": q["q"], "options": list(q["options"])} for q in (a.get("questions") or [])
        ],
    }


def _filtered(exam: Optional[str] = None, year: Optional[str] = None,
              paper: Optional[str] = None) -> List[Dict[str, Any]]:
    rows = _all_articles()
    if exam:
        rows = [a for a in rows if a.get("exam") == exam]
    if year:
        rows = [a for a in rows if a.get("year") == year]
    if paper:
        rows = [a for a in rows if a.get("paper") == paper]
    return rows


def random_article(exam: Optional[str] = None, year: Optional[str] = None,
                   paper: Optional[str] = None) -> Dict[str, Any]:
    pool = _filtered(exam, year, paper) or _all_articles()
    return public_article(random.choice(pool))


def check_answers(article_id: str, answers: List[int]) -> Dict[str, Any]:
    article = get_article(article_id)
    if article is None:
        raise ValueError(f"unknown article: {article_id}")
    questions = article.get("questions") or []
    has_key = bool(article.get("has_key", True))
    details = []
    correct_count = 0
    for i, q in enumerate(questions):
        picked = answers[i] if i < len(answers) else -1
        if not has_key:
            details.append({
                "index": i, "picked": picked, "answer": None, "correct": None,
                "explain": q.get("explain", "官方答案未收录"),
            })
            continue
        ok = picked == q["answer"]
        correct_count += int(ok)
        details.append({
            "index": i,
            "picked": picked,
            "answer": q["answer"],
            "correct": ok,
            "explain": q.get("explain", ""),
        })
    total = len(questions) or 1
    return {
        "article_id": article_id,
        "exam": article.get("exam", ""),
        "no_key": not has_key,
        "score": correct_count if has_key else None,
        "total": total,
        "percent": round(correct_count / total * 100, 1) if has_key else None,
        "details": details,
    }
