"""A spectrum corpus for oracle correlation, NOT a human/AI-labeled set.

Six topics, five stylistic levels each (1 = maximally AI/corporate, 5 = fully
casual/natural), authored inline so running the harness costs no rewrite-API
spend. The point is to span the detectability range so we can ask whether each
local backend ranks these texts the same way GPTZero does — labels are
irrelevant here; the spread is what matters.
"""

CORPUS = [
    # --- A: AI / business ---
    {"id": "biz-1", "topic": "biz", "level": 1, "text": "In today's rapidly evolving digital landscape, organizations must leverage cutting-edge artificial intelligence to unlock unprecedented value and drive transformative outcomes. By embracing innovative, data-driven strategies, forward-thinking enterprises can foster sustainable growth and maintain a competitive edge across diverse market ecosystems."},
    {"id": "biz-2", "topic": "biz", "level": 2, "text": "Companies today increasingly rely on artificial intelligence to improve efficiency and stay competitive. By adopting data-driven strategies and modern tools, businesses can streamline operations, reduce costs, and position themselves for long-term growth in a fast-changing market."},
    {"id": "biz-3", "topic": "biz", "level": 3, "text": "A lot of companies are turning to AI to work more efficiently. With the right data and tools, a business can cut costs and keep up with competitors, though it takes some planning to actually do it well."},
    {"id": "biz-4", "topic": "biz", "level": 4, "text": "Most companies I've seen jump on AI hoping it'll fix everything overnight. It won't. But if you actually have decent data and pick tools that solve a real problem, it can genuinely save time and money."},
    {"id": "biz-5", "topic": "biz", "level": 5, "text": "honestly half the AI stuff at work is hype. the one thing that actually helped was a dumb little script that sorted our support tickets. no data lake, no platform. just fixed the one annoying thing everyone hated."},

    # --- B: personal / outdoors ---
    {"id": "out-1", "topic": "out", "level": 1, "text": "Spending time in nature provides numerous well-documented benefits for mental health and overall well-being. Studies consistently demonstrate that regular exposure to natural environments can significantly reduce stress, enhance mood, and promote a greater sense of personal fulfillment and balance."},
    {"id": "out-2", "topic": "out", "level": 2, "text": "Getting outdoors is good for your mental health. Research shows that spending time in nature can lower stress and improve your mood, which is why many people make a point of taking regular walks outside."},
    {"id": "out-3", "topic": "out", "level": 3, "text": "I try to get outside most days because it helps clear my head. Even a short walk by the water makes the stress feel smaller, and I usually come back in a better mood than when I left."},
    {"id": "out-4", "topic": "out", "level": 4, "text": "Went down to the creek after work again. Didn't do much, just sat there. The heron was back. Something about the water moving makes whatever I was stressed about feel kind of dumb."},
    {"id": "out-5", "topic": "out", "level": 5, "text": "knee's been bad so i just sat on the bank for an hour. didn't fish. the heron came back like it owns the place. mom called twice, same thing both times, i'll call her tomorrow probably"},

    # --- C: science explainer ---
    {"id": "sci-1", "topic": "sci", "level": 1, "text": "Photosynthesis represents a fundamental biological process whereby plants, algae, and certain bacteria convert light energy into chemical energy. This remarkable mechanism, essential to sustaining life on Earth, enables these organisms to synthesize glucose while releasing oxygen as a critical byproduct."},
    {"id": "sci-2", "topic": "sci", "level": 2, "text": "Photosynthesis is the process plants use to turn sunlight into energy. Using light, water, and carbon dioxide, plants produce glucose for fuel and release oxygen, which is essential for most life on Earth."},
    {"id": "sci-3", "topic": "sci", "level": 3, "text": "Plants make their own food through photosynthesis. They take in sunlight, water, and carbon dioxide, turn it into sugar for energy, and give off oxygen in the process. It's basically how most life gets its air."},
    {"id": "sci-4", "topic": "sci", "level": 4, "text": "So plants basically eat sunlight. They grab light, water, and CO2 and turn it into sugar, and the oxygen we breathe is kind of just their leftover waste. Wild when you think about it."},
    {"id": "sci-5", "topic": "sci", "level": 5, "text": "ok so plants literally eat light. they mix sun + water + the carbon dioxide we breathe out and make sugar, and the oxygen is just their trash that happens to keep us alive lol"},

    # --- D: product description ---
    {"id": "prod-1", "topic": "prod", "level": 1, "text": "Introducing a revolutionary solution meticulously engineered to elevate your everyday experience. Combining premium materials with state-of-the-art design, this exceptional product delivers unparalleled performance, ensuring complete satisfaction for even the most discerning of customers."},
    {"id": "prod-2", "topic": "prod", "level": 2, "text": "This product is designed to make your daily routine easier. Built with high-quality materials and a modern design, it offers reliable performance and great value, making it a smart choice for everyday use."},
    {"id": "prod-3", "topic": "prod", "level": 3, "text": "It's a solid, well-made product that does what it promises. The materials feel good, it works reliably, and the price is fair for what you get. A reasonable pick if you need one."},
    {"id": "prod-4", "topic": "prod", "level": 4, "text": "Bought this last month and it's held up better than I expected. Feels well made, does the job, nothing fancy. For the price I'm honestly pretty happy with it."},
    {"id": "prod-5", "topic": "prod", "level": 5, "text": "ok this thing is actually good?? expected it to break in a week. it hasn't. does exactly what it says, feels solid, didn't cost a fortune. no notes"},

    # --- E: opinion / news ---
    {"id": "op-1", "topic": "op", "level": 1, "text": "The recent policy developments underscore the critical importance of fostering collaborative dialogue among diverse stakeholders. As communities navigate an increasingly complex landscape, it remains imperative that leaders prioritize transparency, accountability, and inclusive decision-making to ensure equitable outcomes for all."},
    {"id": "op-2", "topic": "op", "level": 2, "text": "The new policy has raised important questions about how decisions get made. Many people argue that leaders need to be more transparent and include a wider range of voices to make sure the outcomes are fair for everyone."},
    {"id": "op-3", "topic": "op", "level": 3, "text": "The new rule has a lot of people talking. The main complaint seems to be that nobody asked the people it actually affects, and folks want more openness about how these calls get made."},
    {"id": "op-4", "topic": "op", "level": 4, "text": "Classic move, honestly. They roll out the new rule, act surprised when everyone's mad, and it turns out nobody actually asked the people who have to live with it. Same story every time."},
    {"id": "op-5", "topic": "op", "level": 5, "text": "lol of course they passed it without asking anyone. then they're shocked when the whole town shows up angry. maybe ask first next time? just a thought"},

    # --- F: how-to ---
    {"id": "how-1", "topic": "how", "level": 1, "text": "To achieve optimal results, it is essential to follow a systematic, methodical approach. Begin by carefully assembling all of the necessary materials, then proceed to execute each step with precision and attention to detail, ensuring consistency throughout the entire process."},
    {"id": "how-2", "topic": "how", "level": 2, "text": "For the best results, follow these steps carefully. Start by gathering everything you'll need, then work through each step in order, paying attention to the details so the final result comes out consistent."},
    {"id": "how-3", "topic": "how", "level": 3, "text": "It's pretty easy if you take it step by step. Get all your stuff together first, then just go through it in order. Don't rush the details and it'll turn out fine."},
    {"id": "how-4", "topic": "how", "level": 4, "text": "Honestly just get everything out before you start, that's the part everyone skips. Then go slow on the first couple steps and the rest kind of takes care of itself."},
    {"id": "how-5", "topic": "how", "level": 5, "text": "real talk: lay it all out FIRST. every time i wing it i'm halfway through missing something. go slow at the start, rush the boring middle, you're good"},
]
