"""Subject categories and conservative, sense-based dictionary classification."""
import re

TOPICS = [
    ('people', 'People & relationships', '人', 'Family, friends, pronouns, social roles, emotions, and personality'),
    ('food', 'Food & drink', '茶', 'Ingredients, meals, and beverages'),
    ('home', 'Home & daily life', '家', 'Rooms, furniture, household items, and routines'),
    ('health', 'Body & health', '心', 'Body parts, physical sensations, illness, and care'),
    ('nature', 'Nature & weather', '山', 'Animals, plants, seasons, and weather'),
    ('travel', 'Travel & transport', '車', 'Vehicles, directions, tickets, and journeys'),
    ('shopping', 'Shopping & money', '錢', 'Prices, payments, stores, and quantities'),
    ('school', 'School & learning', '學', 'Subjects, books, classrooms, and study'),
    ('work', 'Work & occupations', '工', 'Jobs, workplaces, and work-related terms'),
    ('technology', 'Technology & media', '電', 'Devices, software, communication, and entertainment media'),
    ('clothing', 'Clothing & appearance', '衣', 'Garments, accessories, colors, and appearance'),
    ('time', 'Time & numbers', '時', 'Dates, days, clock time, duration, counting, and frequency'),
    ('actions', 'Actions & descriptions', '做', 'Common verbs, qualities, and words that connect ideas'),
    ('leisure', 'Leisure & culture', '樂', 'Hobbies, sports, games, music, arts, festivals, and traditions'),
]
COLLECTIONS = [('essentials', 'Everyday essentials', '日', 'A beginner collection across subjects')]
TAXONOMY_VERSION = 1

# Specific subjects precede general actions; ties keep this order. Match whole
# words so “tea” cannot match “teacher”, or “good” match “goods”.
TOPIC_KEYWORDS = {
    'technology': ['computer', 'keyboard', 'software', 'telephone', 'mobile phone', 'cell phone', 'internet', 'electric', 'electricity', 'network', 'printer', 'television', 'radio', 'media', 'email', 'website', 'message', 'video', 'newspaper'],
    'school': ['student', 'teacher', 'school', 'learn', 'teach', 'training', 'study', 'book', 'classroom', 'lesson', 'homework', 'exam', 'education', 'language', 'chinese', 'mathematics', 'university'],
    'work': ['job', 'workplace', 'occupation', 'office', 'employee', 'employer', 'salary', 'career', 'lawyer', 'chef', 'farmer', 'driver', 'police', 'worker', 'engineer', 'doctor', 'nurse', 'manager', 'business', 'meeting', 'work'],
    'clothing': ['clothes', 'clothing', 'shirt', 'sweater', 'sock', 'jacket', 'trousers', 'pants', 'shoe', 'garment', 'coat', 'skirt', 'dress', 'hat', 'scarf', 'accessory', 'color', 'colour', 'red', 'blue', 'green', 'yellow', 'black', 'white', 'beautiful', 'good-looking', 'appearance'],
    'food': ['food', 'drink', 'eat', 'coffee', 'tea', 'milk', 'rice', 'bread', 'fruit', 'apple', 'egg', 'vegetable', 'meat', 'water', 'meal', 'breakfast', 'lunch', 'dinner', 'noodle', 'soup', 'beverage', 'ingredient', 'restaurant'],
    'health': ['body', 'brain', 'hand', 'foot', 'feet', 'toe', 'finger', 'head', 'eye', 'ear', 'nose', 'mouth', 'tooth', 'teeth', 'heart', 'stomach', 'leg', 'arm', 'pain', 'illness', 'sick', 'health', 'hospital', 'medicine', 'fever', 'tired', 'hungry', 'thirsty', 'care'],
    'home': ['home', 'house', 'room', 'kitchen', 'bathroom', 'bedroom', 'furniture', 'chair', 'table', 'bed', 'door', 'window', 'household', 'wash', 'clean', 'sleep', 'routine'],
    'nature': ['animal', 'plant', 'tree', 'flower', 'dog', 'cat', 'bird', 'fish', 'ox', 'cow', 'moo', 'horse', 'pig', 'sheep', 'insect', 'mountain', 'river', 'sea', 'forest', 'season', 'spring', 'summer', 'autumn', 'winter', 'weather', 'rain', 'snow', 'wind', 'sun', 'cloud'],
    'travel': ['train', 'bus', 'metro', 'station', 'ticket', 'airport', 'flight', 'transport', 'vehicle', 'travel', 'journey', 'direction', 'road', 'street', 'bicycle', 'taxi', 'boat', 'exit', 'entrance', 'left', 'right', 'north', 'south', 'east', 'west', 'go', 'arrive'],
    'shopping': ['buy', 'sell', 'shop', 'store', 'price', 'payment', 'pay', 'money', 'cash', 'bank', 'cost', 'cheap', 'expensive', 'quantity', 'amount', 'discount', 'purchase', 'goods'],
    'people': ['person', 'people', 'family', 'friend', 'father', 'mother', 'parent', 'brother', 'sister', 'child', 'husband', 'wife', 'pronoun', 'hello', 'thank', 'thanks', 'emotion', 'feeling', 'happy', 'sad', 'angry', 'afraid', 'love', 'like', 'personality', 'kind', 'i', 'me', 'you', 'he', 'him', 'she', 'her', 'we', 'us', 'they', 'them'],
    'time': ['time', 'number', 'date', 'day', 'week', 'month', 'year', 'hour', 'minute', 'second', 'today', 'tomorrow', 'yesterday', 'morning', 'evening', 'duration', 'frequency', 'often', 'always', 'never', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'hundred', 'thousand', 'zero'],
    'leisure': ['hobby', 'sport', 'game', 'music', 'art', 'festival', 'tradition', 'culture', 'leisure', 'play', 'sing', 'dance', 'painting', 'football', 'basketball', 'baseball', 'volleyball', 'ball', 'swim'],
    'actions': ['be', 'is', 'am', 'are', 'have', 'has', 'want', 'make', 'do', 'use', 'look', 'watch', 'read', 'give', 'take', 'get', 'put', 'say', 'know', 'think', 'good', 'bad', 'big', 'large', 'small', 'little', 'easy', 'difficult', 'different', 'same', 'new', 'old', 'solid', 'real', 'substantial', 'also', 'too', 'and', 'with', 'not', 'very'],
}


PRONOUNS = {'i', 'me', 'you', 'he', 'him', 'she', 'her', 'we', 'us', 'they', 'them'}
TOPIC_PATTERNS = {
    topic: [re.compile(r'\b' + re.escape(word) +
                       (r'\b' if topic == 'actions' or word in PRONOUNS else r's?\b'))
            for word in words]
    for topic, words in TOPIC_KEYWORDS.items()
}


def infer_topic(meanings):
    """Classify the selected meaning, leaving unsupported meanings unclassified."""
    text = ' '.join(meanings).lower()
    # Distinguish training from the transport noun before keyword scoring.
    if re.match(r'^to train(?:[ ;,]|$)', text):
        return 'school'
    if text == 'good-looking':
        return 'clothing'
    scores = {topic: sum(bool(pattern.search(text)) for pattern in patterns)
              for topic, patterns in TOPIC_PATTERNS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else 'custom'
