"""Deterministic mock script generator.

Seeded by (provider_name, topic, style) so output is reproducible per
test run.  The generator produces realistic YouTube-style script prose
with full production metadata.
"""
from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass, field
from typing import Callable

from app.schemas.script import (
    EmphasisMarker,
    EmphasisType,
    NarrationTiming,
    PauseMarker,
    PauseType,
    PronunciationHint,
    ScriptProviderResult,
    ScriptRequest,
    ScriptSection,
    ScriptSectionType,
    VisualCue,
    VisualCueType,
)

# Average speaking rates (words per minute) by section type
_WPM: dict[str, float] = {
    "hook": 120.0,
    "introduction": 130.0,
    "main_point": 135.0,
    "transition": 110.0,
    "example": 140.0,
    "analogy": 125.0,
    "call_to_action": 130.0,
    "outro": 120.0,
}

# Target word counts by section type and video length (10-min base)
_WORD_COUNTS: dict[str, int] = {
    "hook": 80,
    "introduction": 160,
    "main_point": 220,
    "transition": 25,
    "example": 160,
    "analogy": 120,
    "call_to_action": 55,
    "outro": 100,
}


def _seed(provider_name: str, topic: str, style: str) -> int:
    raw = f"{provider_name}:{topic.lower().strip()}:{style}"
    return int(hashlib.sha256(raw.encode()).hexdigest()[:16], 16)


class SeededRandom:
    """Thin deterministic random wrapper."""

    def __init__(self, seed: int) -> None:
        self._r = random.Random(seed)

    def choice(self, seq: list) -> object:
        return self._r.choice(seq)

    def choices(self, seq: list, k: int) -> list:
        return self._r.choices(seq, k=k)

    def uniform(self, a: float, b: float) -> float:
        return self._r.uniform(a, b)

    def randint(self, a: int, b: int) -> int:
        return self._r.randint(a, b)

    def sample(self, seq: list, k: int) -> list:
        return self._r.sample(seq, k=min(k, len(seq)))


# ── Style-specific section plans ──────────────────────────────────────────────

@dataclass
class SectionSpec:
    stype: ScriptSectionType
    title_template: str
    content_fn: Callable[[str, str, SeededRandom], str]  # (topic, style, rng) -> text
    transition_in: str | None = None
    transition_out: str | None = None
    storytelling_notes: str | None = None
    visual_suggestion: str | None = None
    scale: float = 1.0   # multiplier on _WORD_COUNTS


_HOOKS: dict[str, list[str]] = {
    "educational": [
        "What if everything you thought you knew about {topic} was only half the story? Today, we're going to go deeper — far deeper — than most videos dare to venture. By the time we're done, you'll have a crystal-clear understanding of {topic} that will completely change how you see this subject.",
        "Here's a question that trips up even experts: what actually makes {topic} work? I'm talking about the real mechanics, not the surface-level explanation you see everywhere online. Stick with me for the next few minutes and you'll walk away with an understanding that most people spend years trying to piece together.",
        "In the next ten minutes, I'm going to explain {topic} so clearly that you could teach it to someone else. No jargon, no hand-waving — just the real thing. This is the video I wish existed when I first started trying to understand it.",
        "Thirty seconds. That's all I need to completely change how you think about {topic}. Ready? Here goes.",
        "Every week, thousands of people search for a clear explanation of {topic}. Most of what they find is confusing, incomplete, or just plain wrong. Today, we fix that.",
    ],
    "documentary": [
        "There is a moment — a precise, identifiable moment in history — when {topic} changed everything. Most people walk right past it without recognising it for what it is. This is the story of that moment, and what came after.",
        "The story of {topic} is not what you think it is. It's stranger, messier, and far more human than the textbook version. Tonight, we go inside that story.",
        "Before {topic} existed, the world worked in a fundamentally different way. This documentary traces the arc from that world to ours — and asks whether we truly understand what we've built.",
        "Somewhere in the world right now, {topic} is reshaping a life, an industry, and a future. This is the story of how we got here — and where we're headed.",
    ],
    "storytelling": [
        "I want to tell you a story about {topic}. It starts, as most good stories do, with a problem nobody knew how to solve — and ends with something none of us saw coming.",
        "Three years ago, I didn't know the first thing about {topic}. Today, it shapes how I think about nearly everything. This is the story of that journey — and why it matters to you.",
        "There's a moment in every great discovery when someone looks at {topic} and sees not what it is, but what it could be. This is that kind of story.",
    ],
    "tutorial": [
        "By the end of this video, you're going to be able to work with {topic} confidently — even if you've never touched it before. I'm going to walk you through every step, in order, with no assumptions about what you already know.",
        "You've probably been putting off learning {topic} because it looks complicated. I get it. But here's the truth: the hard parts aren't where you think they are, and the whole thing becomes intuitive once you see it the right way. Let's do that together.",
        "This is the {topic} tutorial I wish I had when I started. No fluff, no unnecessary complexity — just the exact sequence of steps that actually gets you results.",
    ],
    "news": [
        "Breaking developments in {topic} are forcing experts to reassess assumptions that have held for years. Here's what's happening, why it matters, and what comes next.",
        "The landscape around {topic} shifted dramatically this week. We're going to walk through exactly what changed, what it means in context, and the key perspectives shaping the conversation right now.",
        "Three separate developments involving {topic} converged this week into a story that's bigger than any of them individually. We're going to untangle it.",
    ],
    "long_form": [
        "What you're about to watch is the most comprehensive breakdown of {topic} we've ever produced. We're covering everything — the history, the mechanics, the controversies, the future — in a single sitting. Grab a coffee. This is worth your time.",
        "Over the next thirty minutes or so, we're going on a deep dive into {topic}. Real deep. We'll move from first principles all the way to cutting-edge applications. By the end, you'll understand not just what {topic} is, but why it exists and what it means for the future.",
    ],
    "shorts": [
        "Here's the one thing you need to know about {topic} right now — and most people get it completely wrong.",
        "Stop what you're doing. This will take 60 seconds and change how you think about {topic} forever.",
        "{topic} explained in under a minute. Let's go.",
    ],
}

_INTRODUCTIONS: dict[str, str] = {
    "educational": (
        "Before we get into the details, let me give you a quick map of where we're going. "
        "We'll start with the fundamentals — what {topic} actually is and why it exists. "
        "Then we'll go deeper into how it works at a mechanical level. "
        "After that, we'll look at why it matters in the real world, "
        "and finally, we'll cover the mistakes people most commonly make when working with it. "
        "If you've ever felt like you almost-but-not-quite understood {topic}, "
        "this video is designed specifically for you. Let's jump in."
    ),
    "documentary": (
        "To understand {topic} fully, you have to go back to the beginning. "
        "Not the beginning as it's usually told — with the headline discovery or the famous name — "
        "but the real beginning: the conditions that made {topic} necessary, "
        "the people who were quietly working on it long before anyone noticed, "
        "and the specific moment when everything crystallised. "
        "That's where this story starts."
    ),
    "storytelling": (
        "Every story about {topic} is really a story about people — "
        "their curiosity, their frustrations, and their unexpected breakthroughs. "
        "I want to share one of those stories with you today, "
        "because I think it illuminates something important about {topic} "
        "that no amount of technical explanation can capture. "
        "And at the end, I'll bring it back to what it means for you, right now."
    ),
    "tutorial": (
        "Before we start, here's what you'll need: an open mind and about fifteen minutes. "
        "No prior experience with {topic} is required — we're building from scratch. "
        "I'll explain each step before I show it, so you always know why we're doing what we're doing. "
        "If you get stuck at any point, there's a timestamp in the description for every section. "
        "Alright — let's get into it."
    ),
    "news": (
        "To put today's developments in context, let's quickly review where things stood before this week. "
        "{topic} has been an evolving area with significant activity over the past year. "
        "Several key players have been positioning themselves, "
        "and the signals have been pointing toward exactly this kind of inflection point. "
        "With that context in mind, here's what's happened, and what it means."
    ),
    "long_form": (
        "This video is structured in four major parts. "
        "In part one, we'll cover the foundational concepts behind {topic} — the first principles. "
        "In part two, we go into the mechanics: how it actually works under the hood. "
        "Part three is all about applications: where {topic} is being used, and to what effect. "
        "And in part four, we'll look at the controversies, limitations, and the future. "
        "Each part is timestamped in the description, so feel free to jump around if you'd like. "
        "But I'd recommend watching in order — the parts build on each other. Let's begin."
    ),
    "shorts": (
        "Quick context before the key point: {topic} is one of those things "
        "that seems simple until it isn't. Here's the one insight that unlocks everything."
    ),
}

_MAIN_POINT_TEMPLATES: list[str] = [
    (
        "Let's talk about {aspect} — this is where most explanations fall short, "
        "and it's the piece that makes everything else click. "
        "{topic} works through a mechanism that, once you see it, becomes obvious in retrospect. "
        "Think of it this way: {analogy_placeholder}. "
        "That mental model is the key to understanding everything we'll cover next. "
        "The practical implication is that when you encounter {topic} in the real world, "
        "you'll be able to recognise exactly what's happening and why it matters."
    ),
    (
        "Now let's get into {aspect}. "
        "This is the part that trips up most people, not because it's genuinely hard, "
        "but because it's usually explained in the wrong order. "
        "When we look at {topic} through this lens, several things that seemed complicated become straightforward. "
        "The critical insight here is that the process is consistent: "
        "the same principles apply whether you're looking at a simple case or a complex one. "
        "Once you internalise this, you'll start seeing {topic} patterns everywhere."
    ),
    (
        "Here's where {topic} gets really interesting: {aspect}. "
        "This dimension is what separates a surface-level understanding from a deep one. "
        "Researchers in this space have spent years mapping this territory, "
        "and the picture that's emerged is both more elegant and more complex than most people expect. "
        "The practical payoff is significant. Understanding {aspect} means you can "
        "make better decisions about {topic} and anticipate outcomes that others miss entirely."
    ),
    (
        "Let's zoom in on {aspect}. "
        "This is one of those concepts that sounds technical but is actually quite intuitive "
        "once you approach it the right way. "
        "The underlying structure of {topic} in this area follows a pattern "
        "that we see repeated across many different fields — "
        "which is actually a good sign, because it means our intuitions from those fields carry over. "
        "The key thing to remember is that {aspect} is not a special case — "
        "it's the general rule expressing itself in a specific context."
    ),
    (
        "We need to address {aspect} directly, because it's central to understanding {topic}. "
        "A lot of the confusion around {topic} stems from people skipping this part "
        "or treating it as an optional detail. It's not. "
        "When you understand {aspect} clearly, a lot of other puzzles about {topic} resolve themselves automatically. "
        "The way I like to think about it: {aspect} is the load-bearing wall in the house that is {topic}. "
        "Everything else is built around it."
    ),
]

_ASPECTS: list[str] = [
    "the core mechanism",
    "the fundamental structure",
    "the key principles at work",
    "the underlying dynamics",
    "the practical implications",
    "how this applies in real-world scenarios",
    "what this means for practitioners",
    "the relationship between inputs and outputs",
    "why this approach outperforms alternatives",
    "the critical design decisions involved",
    "how context shapes the outcome",
    "the role of feedback loops",
    "why edge cases matter",
    "the scalability question",
    "what the data actually shows",
]

_EXAMPLE_TEMPLATES: list[str] = [
    (
        "Let me make this concrete with a real example. "
        "Consider a scenario most people will recognise: you're dealing with {topic} "
        "and you encounter exactly the kind of situation we just described. "
        "What happens? The answer surprises people the first time they see it. "
        "Rather than the complicated outcome you might expect, "
        "the system behaves elegantly — exactly as the underlying principles predict. "
        "This is why practitioners who deeply understand {topic} move faster and make fewer mistakes: "
        "they're pattern-matching to a model that actually reflects reality."
    ),
    (
        "Here's a concrete illustration that I find really useful. "
        "Imagine you're approaching {topic} for the first time — no background knowledge, "
        "just the situation in front of you. What do you observe? "
        "At first it looks like a collection of unrelated pieces. "
        "But once you apply the framework we've been building, "
        "the connections become visible. This is not a coincidence. "
        "The structure of {topic} is designed — intentionally or by evolution — "
        "to make exactly these kinds of connections natural and inevitable."
    ),
    (
        "To make this tangible: think about how {topic} shows up in everyday life. "
        "It's everywhere once you start looking — in the tools we use, "
        "the systems we rely on, the decisions that get made all around us. "
        "The example I keep coming back to is this: "
        "when you see {topic} working well, it's almost invisible. "
        "It's only when something goes wrong that people start paying attention. "
        "That invisibility is, paradoxically, a sign of mastery."
    ),
]

_ANALOGY_TEMPLATES: list[str] = [
    (
        "Here's the analogy that finally made {topic} click for me. "
        "Think of it like a well-designed city road network. "
        "You've got main arteries for high-volume traffic and side streets for local access. "
        "Each route is optimised for its purpose. {topic} works on the same principle: "
        "there are high-level structures that handle the bulk of the work, "
        "and fine-grained mechanisms that handle the specific cases. "
        "The elegance is in how they interlock — "
        "and how the whole system degrades gracefully when one part is stressed."
    ),
    (
        "The best analogy I've found for {topic} is a recipe. "
        "Not a recipe with rigid measurements, but the kind of recipe a chef uses — "
        "a set of principles and a feel for what's right. "
        "You learn the ingredients and the basic techniques, "
        "and then you develop judgment about how to combine them. "
        "That judgment is what separates someone who understands {topic} "
        "from someone who just knows the rules."
    ),
    (
        "Think of {topic} the way you'd think about gravity: "
        "you don't need to understand the physics to benefit from it, "
        "but understanding the physics lets you do things that seem like magic to everyone else. "
        "Most people interact with {topic} at the gravity level — "
        "they know the rules of thumb and they work within them. "
        "What we're building here today is the physics-level understanding. "
        "And that's a completely different game."
    ),
]

_TRANSITIONS: list[str] = [
    "Now, with that foundation in place, let's move to the next layer.",
    "That brings us naturally to our next point.",
    "Building on what we just covered, there's another dimension worth exploring.",
    "Now here's where it gets really interesting.",
    "Keep that in mind as we move forward — it'll come back around.",
    "With that context established, let's shift our focus.",
    "This leads directly into something I think you'll find surprising.",
    "Now that the principle is clear, let's see it in action.",
]

_CTAS: dict[str, str] = {
    "educational": (
        "If this video helped you understand {topic} better, "
        "I'd genuinely appreciate a like — it tells me this kind of deep-dive content is worth making. "
        "Subscribe if you want more breakdowns like this: "
        "we go deep on topics that matter, and we never pad the runtime. "
        "Drop a comment below with your biggest question about {topic} — "
        "I read every one, and the best questions become future videos."
    ),
    "documentary": (
        "If you found this story as compelling as I did, "
        "hit subscribe — we have more documentary-style deep dives on the way. "
        "And leave a comment: what aspect of {topic} do you think deserves its own full episode? "
        "Your suggestions genuinely shape what we cover next."
    ),
    "storytelling": (
        "Stories like this one don't get told enough. "
        "If this resonated with you, share it with someone who you think would appreciate it. "
        "And subscribe — there are more stories like this coming, "
        "each one chosen because it changes how you see something important. "
        "What's your {topic} story? I'd love to hear it in the comments."
    ),
    "tutorial": (
        "You made it — you now know how to work with {topic}. "
        "In the description, I've linked to the resources mentioned in this video "
        "and a practice exercise that'll solidify what you just learned. "
        "If you hit any snags, post your question in the comments — "
        "I check them regularly and so does the community. "
        "Subscribe for more tutorials structured exactly like this one."
    ),
    "news": (
        "We'll be updating this story as developments continue. "
        "Subscribe and hit the bell so you don't miss the follow-up. "
        "And let me know in the comments: "
        "what do you think is the most significant implication of these developments for {topic}? "
        "I'll pin the most insightful responses."
    ),
    "long_form": (
        "Thank you for spending this time on {topic} with me. "
        "If you found value in this format — thorough, no shortcuts — "
        "subscribe, because this is what we do here. "
        "There's a full transcript and chapter guide in the description. "
        "And I'm curious: after watching this, what's the one question you still have about {topic}? "
        "Put it in the comments. The best questions become our next deep dive."
    ),
    "shorts": (
        "Follow for more {topic} insights like this — new one every day. "
        "And tell me in the comments: did this change how you think about it?"
    ),
}

_OUTROS: dict[str, str] = {
    "educational": (
        "So let's bring it all together. "
        "We started with the question of what {topic} actually is, moved through how it works, "
        "explored why it matters, and looked at how to avoid the most common pitfalls. "
        "If there's one thing I want you to take away from this video, it's this: "
        "{topic} is learnable. Completely, genuinely learnable — by anyone. "
        "The path just requires taking it one layer at a time, which is exactly what we did today. "
        "Thanks for watching, and I'll see you in the next one."
    ),
    "documentary": (
        "The story of {topic} is still being written. "
        "The decisions being made right now — by researchers, by institutions, by individuals — "
        "will determine how this chapter ends and what the next one looks like. "
        "The more people understand what's at stake, the better those decisions will be. "
        "That's why we make these films. Thanks for watching."
    ),
    "storytelling": (
        "Every story about {topic} is really a story about what it means to pursue understanding. "
        "To sit with a hard question long enough that it starts giving up its answers. "
        "I hope this one gave you something to think about — "
        "and maybe, something to go try for yourself. "
        "Until next time."
    ),
    "tutorial": (
        "You've got everything you need to start working with {topic}. "
        "The first time you apply this, it'll feel a little unfamiliar. "
        "The second time, easier. By the fifth time, it'll feel obvious. "
        "That's how it goes with any real skill. "
        "Be patient with yourself, and trust the process. "
        "I'll see you in the next tutorial."
    ),
    "news": (
        "This story will continue to evolve, and we'll be right here covering it. "
        "The underlying questions around {topic} aren't going away — "
        "if anything, they're becoming more central to the conversations that matter. "
        "Stay engaged, stay informed, and we'll see you next time."
    ),
    "long_form": (
        "We've covered an enormous amount of ground today. "
        "Take your time with it — revisit sections if you need to, "
        "use the chapter markers in the description. "
        "Understanding {topic} at this level of depth is genuinely rare, "
        "and it's worth taking the time to make it stick. "
        "Thank you, truly, for your time and attention. "
        "This is the kind of content I love making, "
        "and it only exists because of an audience that shows up for depth. "
        "See you in the next one."
    ),
    "shorts": (
        "That's it. Simple, right? "
        "The more you understand about {topic}, the more these patterns make sense. "
        "See you tomorrow."
    ),
}

_PRONUNCIATION_WORDS: dict[str, str] = {
    "algorithm": "AL-guh-rith-um",
    "heuristic": "hyoo-RIS-tik",
    "paradigm": "PAIR-uh-dime",
    "cache": "KASH",
    "schema": "SKEE-muh",
    "query": "KWEER-ee",
    "concatenate": "kon-KAT-en-ayt",
    "boolean": "BOO-lee-un",
    "asynchronous": "ay-SING-kruh-nus",
    "polymorphism": "pol-ee-MOR-fizm",
    "recursion": "reh-KUR-zhun",
    "abstraction": "ab-STRAK-shun",
    "entropy": "EN-truh-pee",
    "quantum": "KWON-tum",
    "hypothesis": "hy-POTH-eh-sis",
    "synthesis": "SIN-thuh-sis",
    "neural": "NOOR-ul",
    "lexical": "LEK-sih-kul",
    "semantic": "seh-MAN-tik",
    "syntax": "SIN-taks",
}


def _scale_text_to_wc(text: str, target_wc: int) -> str:
    """Return the text as-is; actual word count may differ from target."""
    return text


def _count_words(text: str) -> int:
    return len(re.sub(r"\s+", " ", text.strip()).split()) if text.strip() else 0


def _duration_seconds(word_count: int, wpm: float) -> float:
    return (word_count / wpm) * 60.0 if wpm > 0 else 0.0


# ── Style-specific section builders ───────────────────────────────────────────

def _build_educational_sections(topic: str, rng: SeededRandom, duration_minutes: int) -> list[SectionSpec | dict]:
    aspects = rng.sample(_ASPECTS, 5)
    main_templates = rng.sample(_MAIN_POINT_TEMPLATES, min(3, len(_MAIN_POINT_TEMPLATES)))
    ex_tpl = rng.choice(_EXAMPLE_TEMPLATES)
    an_tpl = rng.choice(_ANALOGY_TEMPLATES)
    tr = [rng.choice(_TRANSITIONS) for _ in range(6)]

    sections = []

    def mp(i: int, aspect: str, tpl: str) -> dict:
        content = tpl.format(topic=topic, aspect=aspect, analogy_placeholder=f"the mechanics of {topic}")
        return dict(
            stype=ScriptSectionType.MAIN_POINT,
            title=f"Understanding {aspect.title()}",
            content=content,
            transition_in=tr[i],
            transition_out=tr[i + 1] if i + 1 < len(tr) else None,
            storytelling_notes=f"Pause briefly after stating the key principle. Make eye contact with camera.",
            visual_suggestion=f"Animated diagram illustrating {aspect}",
        )

    sections.append(mp(0, aspects[0], main_templates[0]))
    sections.append(dict(
        stype=ScriptSectionType.EXAMPLE,
        title="Concrete Example",
        content=ex_tpl.format(topic=topic),
        transition_in=tr[1],
        transition_out=tr[2],
        visual_suggestion="B-roll of real-world scenario",
    ))
    sections.append(mp(2, aspects[1], main_templates[1 % len(main_templates)]))
    sections.append(dict(
        stype=ScriptSectionType.ANALOGY,
        title="The Key Analogy",
        content=an_tpl.format(topic=topic),
        transition_in=tr[3],
        transition_out=tr[4],
        storytelling_notes="Speak more slowly during the analogy. Let it land.",
        visual_suggestion="Split-screen comparing analogy and actual concept",
    ))
    if duration_minutes >= 10:
        sections.append(mp(4, aspects[2], main_templates[2 % len(main_templates)]))

    return sections


def _build_documentary_sections(topic: str, rng: SeededRandom, duration_minutes: int) -> list[dict]:
    aspects = rng.sample(_ASPECTS, 4)
    tr = [rng.choice(_TRANSITIONS) for _ in range(5)]

    def mp(title: str, aspect: str, i: int) -> dict:
        tpl = rng.choice(_MAIN_POINT_TEMPLATES)
        content = tpl.format(topic=topic, aspect=aspect, analogy_placeholder=f"the history of {topic}")
        return dict(
            stype=ScriptSectionType.MAIN_POINT,
            title=title,
            content=content,
            transition_in=tr[i],
            transition_out=tr[i + 1] if i + 1 < len(tr) else None,
            storytelling_notes="Atmospheric tone. Slow and deliberate.",
            visual_suggestion=f"Archival footage or period-appropriate visuals for {topic}",
        )

    sections = [
        mp("Origins", aspects[0], 0),
        mp("The Turning Point", aspects[1], 1),
        mp("Ripple Effects", aspects[2], 2),
    ]
    if duration_minutes >= 10:
        sections.append(mp("The Future", aspects[3], 3))
    return sections


def _build_tutorial_sections(topic: str, rng: SeededRandom, duration_minutes: int) -> list[dict]:
    tr = [rng.choice(_TRANSITIONS) for _ in range(6)]

    def step(n: int, title: str, aspect: str, i: int) -> dict:
        tpl = rng.choice(_MAIN_POINT_TEMPLATES)
        content = f"Step {n}: {title}\n\n" + tpl.format(
            topic=topic, aspect=aspect, analogy_placeholder=f"step {n} of working with {topic}"
        )
        return dict(
            stype=ScriptSectionType.MAIN_POINT,
            title=f"Step {n}: {title}",
            content=content,
            transition_in=tr[i],
            transition_out=tr[i + 1] if i + 1 < len(tr) else None,
            storytelling_notes=f"Pause at numbered step. Show on screen.",
            visual_suggestion=f"Screen recording or step diagram for step {n}",
        )

    aspects = rng.sample(_ASPECTS, 4)
    sections = [
        step(1, "Setup and Foundation", aspects[0], 0),
        step(2, "Core Implementation", aspects[1], 1),
        step(3, "Advanced Techniques", aspects[2], 2),
    ]
    if duration_minutes >= 10:
        sections.append(dict(
            stype=ScriptSectionType.EXAMPLE,
            title="Troubleshooting Common Issues",
            content=rng.choice(_EXAMPLE_TEMPLATES).format(topic=topic),
            transition_in=tr[3],
            visual_suggestion="Error screen + solution diagram",
        ))
    return sections


def _build_sections_for_style(topic: str, style: str, rng: SeededRandom, duration_minutes: int) -> list[dict]:
    if style == "educational":
        return _build_educational_sections(topic, rng, duration_minutes)
    elif style == "documentary":
        return _build_documentary_sections(topic, rng, duration_minutes)
    elif style == "tutorial":
        return _build_tutorial_sections(topic, rng, duration_minutes)
    elif style == "storytelling":
        # Storytelling uses same structure as documentary with different tone
        return _build_documentary_sections(topic, rng, duration_minutes)
    elif style == "news":
        aspects = rng.sample(_ASPECTS, 3)
        tr = [rng.choice(_TRANSITIONS) for _ in range(4)]
        sections = []
        for i, asp in enumerate(aspects):
            tpl = rng.choice(_MAIN_POINT_TEMPLATES)
            sections.append(dict(
                stype=ScriptSectionType.MAIN_POINT,
                title=["What Happened", "Key Context", "What It Means"][i],
                content=tpl.format(topic=topic, aspect=asp, analogy_placeholder=f"the latest developments in {topic}"),
                transition_in=tr[i],
                transition_out=tr[i + 1] if i + 1 < len(tr) else None,
                visual_suggestion="News graphics, data visualisation",
            ))
        return sections
    elif style == "long_form":
        # Extended educational
        sections = _build_educational_sections(topic, rng, duration_minutes)
        aspects = rng.sample(_ASPECTS, 2)
        for j, asp in enumerate(aspects):
            tpl = rng.choice(_MAIN_POINT_TEMPLATES)
            sections.append(dict(
                stype=ScriptSectionType.MAIN_POINT,
                title=f"Deep Dive: {asp.title()}",
                content=tpl.format(topic=topic, aspect=asp, analogy_placeholder=f"the deep mechanics of {topic}"),
                visual_suggestion=f"Expert interview B-roll or detailed diagram for {asp}",
            ))
        sections.append(dict(
            stype=ScriptSectionType.ANALOGY,
            title="Synthesis and Broader Context",
            content=rng.choice(_ANALOGY_TEMPLATES).format(topic=topic),
            visual_suggestion="Wide-angle visuals, reflective music cue",
        ))
        return sections
    else:  # shorts
        tpl = rng.choice(_MAIN_POINT_TEMPLATES)
        return [dict(
            stype=ScriptSectionType.MAIN_POINT,
            title="The Key Insight",
            content=tpl.format(topic=topic, aspect="the single most important thing to know", analogy_placeholder=topic),
            visual_suggestion="Text overlay on engaging B-roll",
        )]


# ── Narration timing calculator ───────────────────────────────────────────────

def _calculate_timing(sections: list[ScriptSection], hook: str, intro: str,
                       outro: str, cta: str) -> list[NarrationTiming]:
    timings: list[NarrationTiming] = []
    elapsed_ms = 0

    def _add(title: str, text: str, stype: str) -> None:
        nonlocal elapsed_ms
        wc = _count_words(text)
        wpm = _WPM.get(stype, 130.0)
        dur_s = _duration_seconds(wc, wpm)
        dur_ms = int(dur_s * 1000)
        timings.append(NarrationTiming(
            section_title=title,
            start_ms=elapsed_ms,
            end_ms=elapsed_ms + dur_ms,
            wpm=wpm,
            word_count=wc,
        ))
        elapsed_ms += dur_ms

    if hook:
        _add("Hook", hook, "hook")
    if intro:
        _add("Introduction", intro, "introduction")
    for s in sections:
        _add(s.title, s.content, s.section_type.value)
    if cta:
        _add("Call to Action", cta, "call_to_action")
    if outro:
        _add("Outro", outro, "outro")

    return timings


# ── Emphasis markers ──────────────────────────────────────────────────────────

def _extract_emphasis(full_text: str, topic: str, rng: SeededRandom) -> list[EmphasisMarker]:
    """Find key terms and mark them for emphasis."""
    markers: list[EmphasisMarker] = []
    topic_words = set(topic.lower().split())
    emphasis_candidates = list(topic_words) + ["critical", "important", "key", "crucial",
                                                "fundamental", "essential", "precisely",
                                                "specifically", "exactly", "absolutely"]

    seen_positions: set[int] = set()
    lower = full_text.lower()

    for word in emphasis_candidates:
        start = 0
        while True:
            pos = lower.find(word, start)
            if pos == -1:
                break
            if pos not in seen_positions:
                emphasis_type = rng.choice([
                    EmphasisType.STRONG,
                    EmphasisType.RAISE_PITCH,
                    EmphasisType.PAUSE_BEFORE,
                ])
                markers.append(EmphasisMarker(
                    text=full_text[pos:pos + len(word)],
                    position=pos,
                    emphasis_type=emphasis_type,
                ))
                seen_positions.add(pos)
            start = pos + len(word)
            if len(markers) >= 20:
                break
        if len(markers) >= 20:
            break

    return markers[:15]


# ── Pause markers ─────────────────────────────────────────────────────────────

def _generate_pauses(sections: list[ScriptSection], timings: list[NarrationTiming],
                     rng: SeededRandom) -> list[PauseMarker]:
    pauses: list[PauseMarker] = []
    offset = 0

    for i, (section, timing) in enumerate(zip(sections, timings[2:])):  # skip hook + intro
        # Pause at start of each section
        pauses.append(PauseMarker(
            position=offset,
            duration_ms=rng.randint(500, 1200),
            pause_type=PauseType.MEDIUM,
            context=section.content[:40] + "..." if len(section.content) > 40 else section.content,
        ))
        offset += len(section.content)

        # Occasional dramatic pause mid-section
        if i % 2 == 0 and len(section.content) > 100:
            mid = offset - len(section.content) // 2
            pauses.append(PauseMarker(
                position=mid,
                duration_ms=rng.randint(800, 2000),
                pause_type=PauseType.DRAMATIC,
                context="...[pause for effect]...",
            ))

    return pauses[:12]


# ── Pronunciation hints ────────────────────────────────────────────────────────

def _find_pronunciation_hints(full_text: str, topic: str) -> list[PronunciationHint]:
    hints: list[PronunciationHint] = []
    lower = full_text.lower()
    for word, phonetic in _PRONUNCIATION_WORDS.items():
        if word in lower:
            hints.append(PronunciationHint(word=word, phonetic=phonetic))
    # Add topic-based hint if topic is multi-syllable
    topic_clean = re.sub(r"[^\w\s]", "", topic).strip()
    if len(topic_clean.split()) == 1 and len(topic_clean) > 8:
        hints.append(PronunciationHint(
            word=topic_clean,
            phonetic=" ".join(topic_clean[:4].upper() + "-" + topic_clean[4:].upper()),
            note="Say clearly and confidently",
        ))
    return hints[:8]


# ── Visual cues ────────────────────────────────────────────────────────────────

def _generate_visual_cues(timings: list[NarrationTiming], topic: str,
                           rng: SeededRandom) -> list[VisualCue]:
    cues: list[VisualCue] = []
    cue_types = [
        VisualCueType.B_ROLL,
        VisualCueType.GRAPHIC,
        VisualCueType.TITLE_CARD,
        VisualCueType.ZOOM,
        VisualCueType.LOWER_THIRD,
    ]
    descriptions = [
        f"B-roll: Real-world applications of {topic}",
        f"Animated graphic: Core concept diagram for {topic}",
        f"Title card: Key term definition",
        f"Zoom: Emphasis on main point",
        f"Lower third: Expert source citation",
        f"B-roll: Abstract visuals representing {topic}",
        f"Graphic: Step-by-step breakdown",
        f"Cut: New section transition with audio sting",
    ]

    for i, timing in enumerate(timings):
        if i >= 8:
            break
        cue_type = rng.choice(cue_types)
        desc = descriptions[i % len(descriptions)]
        cues.append(VisualCue(
            time_ms=timing.start_ms,
            description=desc,
            cue_type=cue_type,
            duration_ms=rng.randint(2000, 6000),
        ))

    return cues


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_mock_script(request: ScriptRequest, provider_name: str) -> ScriptProviderResult:
    """Generate a fully-populated mock ScriptProviderResult deterministically."""
    seed = _seed(provider_name, request.topic, request.style.value)
    rng = SeededRandom(seed)
    topic = request.topic
    style = request.style.value
    duration = request.target_duration_minutes

    # Scale word counts by duration (base is 10 min = 130 WPM)
    scale = duration / 10.0

    # Pick text blocks
    hook_options = _HOOKS.get(style, _HOOKS["educational"])
    hook = rng.choice(hook_options).format(topic=topic)
    intro_template = _INTRODUCTIONS.get(style, _INTRODUCTIONS["educational"])
    introduction = intro_template.format(topic=topic)
    cta_template = _CTAS.get(style, _CTAS["educational"])
    cta = cta_template.format(topic=topic)
    outro_template = _OUTROS.get(style, _OUTROS["educational"])
    outro = outro_template.format(topic=topic)

    # Build sections
    raw_sections = _build_sections_for_style(topic, style, rng, duration)

    sections: list[ScriptSection] = []
    for i, spec in enumerate(raw_sections):
        content = spec["content"]
        wc = _count_words(content)
        stype = spec["stype"]
        wpm = _WPM.get(stype.value, 130.0)
        sections.append(ScriptSection(
            section_type=stype,
            title=spec["title"],
            content=content,
            word_count=wc,
            duration_seconds=_duration_seconds(wc, wpm),
            order=i,
            transition_in=spec.get("transition_in"),
            transition_out=spec.get("transition_out"),
            storytelling_notes=spec.get("storytelling_notes"),
            visual_suggestion=spec.get("visual_suggestion"),
        ))

    # Metrics
    total_words = (
        _count_words(hook)
        + _count_words(introduction)
        + sum(s.word_count for s in sections)
        + _count_words(cta)
        + _count_words(outro)
    )
    avg_wpm = 130.0
    est_duration_s = int(_duration_seconds(total_words, avg_wpm))
    reading_time_s = int(_duration_seconds(total_words, 200.0))  # silent reading speed
    scene_count = len(sections) + 3  # +hook, +intro, +outro

    # Title
    title_options = [
        f"The Complete Guide to {topic}",
        f"{topic}: Everything You Need to Know",
        f"Understanding {topic} — From Zero to Expert",
        f"Why {topic} Matters More Than You Think",
        f"{topic} Explained",
    ]
    title = rng.choice(title_options)

    # Production metadata
    timings = _calculate_timing(sections, hook, introduction, outro, cta)
    emphasis = _extract_emphasis(hook + introduction + " ".join(s.content for s in sections), topic, rng)
    all_text = hook + introduction + " ".join(s.content for s in sections) + cta + outro
    pronunciation_hints = _find_pronunciation_hints(all_text, topic)
    visual_cues = _generate_visual_cues(timings, topic, rng)
    pauses = _generate_pauses(sections, timings, rng)

    # Provider-specific confidence variance
    confidence_base = {"openai": 0.91, "gemini": 0.88, "claude": 0.93, "openrouter": 0.85}
    confidence = confidence_base.get(provider_name, 0.88) + rng.uniform(-0.03, 0.03)

    return ScriptProviderResult(
        provider_name=provider_name,
        topic=topic,
        title=title,
        hook=hook,
        introduction=introduction,
        outro=outro,
        call_to_action=cta,
        sections=sections,
        narration_timing=timings,
        emphasis_markers=emphasis,
        pauses=pauses,
        pronunciation_hints=pronunciation_hints,
        visual_cues=visual_cues,
        word_count=total_words,
        estimated_duration_seconds=est_duration_s,
        reading_time_seconds=reading_time_s,
        scene_count=scene_count,
        pacing_wpm=avg_wpm,
        confidence=round(min(0.98, max(0.60, confidence)), 3),
    )
