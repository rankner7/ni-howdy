"""Curated Taiwan Mandarin starter catalog; explanations are cached once."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nihowdy.content import load_hanzi, construction, sources_for

# form | tone-marked pinyin | precise English answers | topic | composition note
ROWS = """
我|wǒ|I;me|people|A first-person pronoun. Modern usage is not a literal sum of its visual parts.
你|nǐ|you|people|The person component 亻 helps connect this pronoun with people.
他|tā|he;him|people|亻 is the person component. 他 and 她 sound alike; context distinguishes them.
是|shì|to be;is;am;are|actions|Used to identify or classify: 我是學生 means I am a student.
有|yǒu|to have;have;has|actions|Expresses possession or existence. 沒有 is the usual negative.
要|yào|to want;want|actions|Expresses wanting or intending to do something; context can also imply necessity.
也|yě|also;too|actions|An adverb placed before the verb: 我也要 means I also want.
喜歡|xǐ huān|to like;like|people|A common verb for liking something or enjoying an activity.
好|hǎo|good|actions|The visible components are 女 and 子. Treat this as construction, not a claim about modern gender roles.
人|rén|person;a person|people|A basic character used in words for people, such as 家人, family members.
一|yī|one|time|A single horizontal stroke represents one. Its spoken tone changes in some phrases.
二|èr|two|time|Two horizontal strokes represent two.
三|sān|three|time|Three horizontal strokes represent three.
大|dà|big;large|actions|A basic adjective. 大人 uses 大 with 人 to mean an adult.
小|xiǎo|small;little|actions|A basic adjective found in 小孩, child, and 小時, hour.
你好|nǐ hǎo|hello|people|你 means you and 好 means good; together they form a greeting.
謝謝|xiè xie|thank you;thanks|people|Repeating 謝 forms the everyday expression of thanks. The second syllable is often light.
喝|hē|to drink;drink|food|The mouth component 口 connects this verb with an action of the mouth.
吃|chī|to eat;eat|food|The mouth component 口 is a meaning clue, as it is in 喝.
水|shuǐ|water|food|A foundational character. Its component form 氵 appears in many words related to liquids.
茶|chá|tea|food|The grass/plant component 艹 connects tea with plants.
咖啡|kā fēi|coffee|food|A sound-based borrowing. The characters represent the sound of coffee, not a literal mouth-related definition.
牛奶|niú nǎi|milk;cow's milk|food|牛 means cow and 奶 means milk.
米飯|mǐ fàn|cooked rice;rice|food|米 means rice grain and 飯 refers to cooked rice or a meal.
麵包|miàn bāo|bread|food|麵 relates to flour or noodles; the compound means bread.
水果|shuǐ guǒ|fruit|food|水 means water and 果 means fruit. Learn 水果 as the everyday word for fruit.
蘋果|píng guǒ|apple;an apple|food|果 means fruit. The plant component 艹 occurs in 蘋.
蛋|dàn|egg;an egg|food|Also appears in 雞蛋, chicken egg, and 蛋糕, cake.
電腦|diàn nǎo|computer;a computer|technology|電 means electricity and 腦 means brain: a modern compound for computer. Compare 電話 and 電視.
電話|diàn huà|telephone;a telephone;phone;a phone|technology|電 means electricity and 話 means speech. Compare 電腦 and 電視.
電視|diàn shì|television;a television;TV|technology|電 means electricity and 視 relates to seeing.
手機|shǒu jī|mobile phone;a mobile phone;cell phone;a cell phone|technology|手 means hand and 機 means machine: a portable phone.
電|diàn|electricity|technology|This character forms a family of modern technology words: 電腦, 電話, and 電視.
腦|nǎo|brain;a brain|health|The left component is associated with flesh/body parts, not the moon in this usage.
手|shǒu|hand;a hand|health|Its component form 扌 appears in many hand-action characters.
網路|wǎng lù|internet;network|technology|網 means net and 路 means road/path. 網路 is common Taiwan usage; 網絡 is common elsewhere.
鍵盤|jiàn pán|keyboard;a keyboard|technology|鍵 means key and 盤 means tray/plate.
滑鼠|huá shǔ|computer mouse;a computer mouse|technology|滑 suggests sliding and 鼠 means mouse. 滑鼠 is Taiwan usage; 鼠標 is common in Mainland China.
襪子|wà zi|socks|clothing|襪 contains the clothing component 衤. 子 is a common noun suffix here.
衣服|yī fú|clothes;clothing|clothing|衣 means clothing. Its component form 衤 appears in many garment characters.
毛衣|máo yī|sweater;a sweater|clothing|毛 relates to hair/wool and 衣 means clothing.
上衣|shàng yī|top;a top|clothing|上 means upper and 衣 means clothing.
襯衫|chèn shān|shirt;a shirt|clothing|Both characters contain 衤, the clothing component.
褲子|kù zi|trousers;pants|clothing|褲 contains the clothing component 衤; 子 is a noun suffix.
鞋子|xié zi|shoes|clothing|鞋 contains 革, associated with leather; 子 is a noun suffix.
外套|wài tào|coat;a coat;jacket;a jacket|clothing|外 means outside. The word refers to an outer layer of clothing.
車|chē|vehicle;a vehicle|travel|A character shared by many vehicle words, including 火車 and 公車.
火車|huǒ chē|train;a train|travel|火 means fire and 車 means vehicle, reflecting early steam-powered trains.
公車|gōng chē|bus;a bus|travel|公 suggests public and 車 means vehicle. A common Taiwan word for bus.
捷運|jié yùn|metro;rapid transit|travel|捷 suggests speed and 運 transportation. Common in Taiwan for urban rapid transit.
車站|chē zhàn|station;a station|travel|車 means vehicle and 站 means station/stop.
去|qù|to go;go|travel|A basic motion verb. 去車站 means to go to the station.
買|mǎi|to buy;buy|shopping|The 貝 component connects with money and trade; compare 賣, to sell.
票|piào|ticket;a ticket|travel|Appears in 車票, a transport ticket, and 機票, a flight ticket.
家|jiā|home;family|home|宀 is the roof component. The modern character refers to home or family.
朋友|péng yǒu|friend;a friend|people|A common word for friend. 好朋友 means a good friend.
學生|xué shēng|student;a student|school|學 relates to learning; 生 is used in words for learners and people.
老師|lǎo shī|teacher;a teacher|school|A respectful everyday word for teacher.
中文|zhōng wén|Chinese;the Chinese language|school|中 refers to China here and 文 to writing/language.
學|xué|to learn;learn;to study;study|school|Appears in 學生, student, and 學校, school.
學校|xué xiào|school;a school|school|學 relates to learning; the compound means school.
書|shū|book;a book|school|Appears in 書店, bookstore, and 看書, to read.
看|kàn|to look;look;to watch;watch;to read;read|actions|Contains 手 and 目 (eye). In context it can mean looking, watching, or reading.
嗎|ma|question particle;question marker|actions|Place 嗎 at the end of a statement to form a yes-or-no question.
不|bù|not|actions|Place 不 before a verb or adjective to express negation; its tone changes before a fourth tone.
沒有|méi yǒu|do not have;don't have;not have;there is not;there are not|actions|沒有 negates possession or existence and can also negate a completed action.
什麼|shén me|what|actions|A question word used in the position of the thing being asked about.
哪裡|nǎ lǐ|where|travel|A common Taiwan Mandarin word for where.
誰|shéi|who|people|A question word referring to a person; shéi is a common spoken reading in Taiwan.
怎麼|zěn me|how|actions|Asks how something happens or how to do something; context can also convey why.
為什麼|wèi shén me|why|actions|Asks for a reason; often placed before the verb phrase.
多少|duō shǎo|how much;how many|actions|Asks about an amount or number.
幾|jǐ|how many;how much|actions|Asks about a number, usually before a classifier.
這|zhè|this|actions|A demonstrative meaning this; commonly appears before a classifier.
那|nà|that|actions|A demonstrative meaning that; commonly appears before a classifier.
這個|zhè ge|this;this one|actions|A common demonstrative meaning this one; 個 is a general classifier.
那個|nà ge|that;that one|actions|A common demonstrative meaning that one; 個 is a general classifier.
和|hé|and;with|actions|Joins nouns, as in 茶和水. Taiwan also uses the pronunciation hàn.
的|de|possessive particle|actions|A particle used for possession and to link many modifiers to nouns.
在|zài|at;in;to be at|actions|Marks a location or indicates that an action is in progress, depending on context.
很|hěn|very|actions|Often links a subject to an adjective and does not always mean very in a neutral statement.
可以|kě yǐ|can;may|actions|Expresses permission or possibility, depending on context.
想|xiǎng|to want;want;to think;think|actions|Can express wanting to do something or thinking, depending on context.
她|tā|she;her|people|The feminine third-person pronoun; it sounds like 他.
我們|wǒ men|we;us|people|The first-person plural pronoun: we or us.
你們|nǐ men|you (plural);you|people|The plural form of you; 們 marks the plural.
他們|tā men|they;them|people|A third-person plural pronoun for a group of people.
今天|jīn tiān|today|time|Refers to the current day; commonly appears after the subject in a sentence.
明天|míng tiān|tomorrow|time|Refers to the day after today.
再見|zài jiàn|goodbye;bye|people|A common farewell; literally the characters suggest seeing someone again.
對不起|duì bu qǐ|sorry;I am sorry|people|A common apology; 不 is often pronounced lightly in this phrase.
不客氣|bú kè qì|you are welcome;you're welcome;you’re welcome|people|A common response to thanks; 不 changes to bú before the fourth tone in 客.
請|qǐng|please|people|A polite word used in requests and invitations.
""".strip()

ESSENTIALS = set('我 你 他 是 有 要 也 喜歡 好 人 一 二 三 大 小 你好 謝謝 喝 水 茶 電腦 嗎 不 沒有 什麼 哪裡 誰 怎麼 為什麼 多少 幾 這 那 這個 那個 和 的 在 很 可以 想 她 我們 你們 他們 今天 明天 再見 對不起 不客氣 請'.split())

hanzi = load_hanzi()
items = []
for line in ROWS.splitlines():
    form, pinyin, english, topic, note = line.split("|")
    answers = english.split(";")
    items.append(dict(id=form, kind="word", text=form, pinyin=pinyin, english=answers[0],
                      answers=answers, chinese_answers=[form], topic=topic,
                      tokens=[],
                      region="TW", script="Hant", status="ready", explanation=note,
                      explanation_origin="Cached source-grounded editorial explanation",
                      characters=construction(form, hanzi), sources=sources_for(form)))
    if form in ESSENTIALS:
        items[-1]["collections"] = ["essentials"]

def phrase(tokens, english, grammar, topic):
    lookup = {i["id"]: i for i in items}
    text = "".join(tokens) + "。"
    items.append(dict(id="phrase:"+text, kind="phrase", text=text,
                      pinyin=" ".join(lookup[t]["pinyin"] for t in tokens) + ".",
                      english=english, answers=[english], chinese_answers=[text],
                      tokens=tokens, topic=topic, region="TW", script="Hant", status="ready",
                      explanation=grammar, explanation_origin="Validated grammar template",
                      characters=[], sources=sources_for(text)))

for subject, pronoun in [("我", "I"), ("你", "You")]:
    for obj, noun in [("水", "water"), ("茶", "tea"), ("咖啡", "coffee"), ("牛奶", "milk")]:
        phrase([subject, "也", "要", "喝", obj], f"{pronoun} also want to drink {noun}.",
               "Subject + 也 (also) + 要 (want) + 喝 (drink) + object. 也 goes before the verb phrase.", "food")
    for obj, noun in [("電腦", "a computer"), ("手機", "a mobile phone"), ("毛衣", "a sweater"), ("書", "a book")]:
        phrase([subject, "也", "要", "買", obj], f"{pronoun} also want to buy {noun}.",
               "Subject + 也 (also) + 要 (want) + 買 (buy) + object. Mandarin does not require an English-style indefinite article.", "technology" if obj in ["電腦", "手機"] else "clothing" if obj == "毛衣" else "school")
    for obj, noun in [("茶", "tea"), ("咖啡", "coffee")]:
        phrase([subject, "喜歡", "喝", obj], f"{pronoun} like drinking {noun}.",
               "Subject + 喜歡 (like) + activity. 喝茶 is the activity of drinking tea.", "food")
phrase(["我", "是", "學生"], "I am a student.", "是 connects a subject with a noun identifying it.", "people")
phrase(["我", "也", "學", "中文"], "I also study Chinese.", "也 goes before 學, the verb. 中文 is the object.", "people")
(Path(__file__).resolve().parent.parent / "data/starter.json").write_text(json.dumps(items, ensure_ascii=False, indent=2)+"\n")
print(f"Prepared {len(items)} starter entries.")
