"""CivicPulse chat protocol: complaint analysis handler and local fallback logic."""

from datetime import datetime
from uuid import uuid4

from uagents import Context, Protocol
from uagents.experimental.chat_agent.protocol import build_llm_message_history
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

from http_client import ask_asi1

protocol = Protocol(spec=chat_protocol_spec)

DEPARTMENTS = {
    "Pothole": "Roads & Public Works Department",
    "Garbage": "Sanitation & Waste Management Department",
    "Streetlight": "Electrical & Street Lighting Department",
    "Water Leakage": "Water Supply & Sewerage Board",
    "Blocked Drain": "Storm Water & Drainage Department",
    "Electrical Hazard": "Electricity Distribution & Emergency Services",
    "Power Outage": "Electricity Distribution Company",
    "Other": "Municipal General Services (via the city helpline)",
}

NEXT_ACTIONS = {
    "Pothole": (
        "Report the exact street location to the Roads & Public Works Department with photos. "
        "If the pothole is large or on a busy road, also ask for a temporary warning sign or barrier."
    ),
    "Garbage": (
        "Log a pickup request with the Sanitation & Waste Management Department including photos "
        "and the exact spot. If collection keeps being missed, ask for a revised schedule."
    ),
    "Streetlight": (
        "Report the pole number (if visible) and street name to the Electrical & Street Lighting "
        "Department. Mention that the area is dark at night so it can be treated as a safety issue."
    ),
    "Water Leakage": (
        "Call the Water Supply & Sewerage Board emergency line with the landmark and photos. "
        "If the leak is near electrical equipment, keep people away and say so when you report it."
    ),
    "Blocked Drain": (
        "Request desilting from the Storm Water & Drainage Department with the exact location. "
        "If wastewater is overflowing onto the road, flag it as a health and traffic hazard."
    ),
        "Electrical Hazard": (
        "Keep people away from the exposed, hanging, or sparking wire. "
        "Contact the local electricity emergency service immediately and provide the exact location. "
        "Do not touch the wire."
    ),
    "Power Outage": (
    "Report the outage to your local electricity distribution company, "
    "including your area, the duration of the outage, and any affected landmarks. "
    "If you notice a fallen wire or another immediate electrical danger, "
    "keep away and contact emergency services."
),
    "Other": (
        "Contact the municipal helpline with a clear description, photos, and the exact location "
        "so the complaint can be routed to the right team."
    ),
}


CATEGORY_KEYWORDS = {
    "Pothole": (
        "pothole", "pot hole", "road crack", "crater",
        "broken road", "road damage",
    ),
    "Garbage": (
        "garbage", "trash", "waste", "litter", "rubbish",
        "not collected", "dumping", "uncollected",
    ),
    "Streetlight": (
        "streetlight", "street light", "lamp post", "lamppost",
        "light pole", "dark street", "broken streetlight",
    ),
    "Water Leakage": (
        "water leak", "leakage", "leaking", "leak",
        "pipe burst", "burst pipe", "water pipe",
    ),
    "Blocked Drain": (
        "drain", "drainage", "sewer", "sewage", "gutter",
        "manhole", "clogged", "overflow",
    ),
   
    "Electrical Hazard": (
        "live wire", "exposed wire", "electric wire",
        "electrical hazard", "electric shock", "power line",
        "fallen wire", "hanging wire", "sparking wire",
        "electric pole", "electrical short circuit",
        "electrical wire", "electrical wires",
        "exposed electrical wire", "sparking",
    ),
    "Power Outage": (
        "power outage", "power cut", "no electricity",
        "electricity outage", "electricity cut",
        "no power", "power failure", "blackout",
    ),

}


HIGH_RISK_WORDS = (
    "accident", "injur", "hurt", "danger", "hazard", "child", "children", "school",
    "hospital", "live wire", "electric shock", "sewage", "flood", "overflow",
    "emergency", "urgent", "deep", "sinkhole",
)
DELAY_WORDS = (
    "week", "weeks", "month", "months", "repeated", "again", "still", "nobody",
    "no action", "ignored",
)
LOW_RISK_WORDS = ("small", "minor", "slight", "tiny", "cosmetic")

GREETINGS = {
    "hi", "hello", "hey", "hi there", "hello there", "hey there",
    "help", "start", "menu", "who are you", "what can you do",
    "what can you help me with",
}

HELP_TEXT = (
    "Hi, I'm CivicPulse! Describe a civic issue - a pothole, garbage that has not been "
    "collected, a broken streetlight, a water leak, or a blocked drain - and I will identify "
    "the category, recommend the responsible department, assign a priority score from 0 to 100, "
    "explain the score, and suggest your next action.\n\n"
    'Example: "There is a deep pothole on Main Street near the school and scooters keep skidding."'
)


SYSTEM_PROMPT = (
    "You are CivicPulse, an assistant that analyzes civic complaints before they are filed. "
    "Supported categories are Pothole, Garbage, Streetlight, Water Leakage, Blocked Drain, "
    "Electrical Hazard, and Other.\n\n"
    "Reply in exactly this format:\n\n"
    "Category: <Pothole | Garbage | Streetlight | Water Leakage | Blocked Drain | Electrical Hazard | Other>\n"
    "Department: <responsible municipal department or electricity utility>\n"
    "Priority Score: <integer from 0 to 100>/100\n"
    "Why this priority: <brief explanation based only on the message>\n"
    "Suggested next action: <appropriate action, or state that no civic action is needed>\n\n"
    "Rules:\n"
    "- First determine whether the message reports an actual, current civic problem.\n"
    "- Explicit denials such as 'there is no pothole' must not be classified as active complaints, "
    "unless the message separately describes a real active issue.\n"
    "- Ordinary personal messages unrelated to civic issues must be Other, score 0, and require "
    "no municipal complaint.\n"
    "- Exposed, live, hanging, or sparking electrical wires must be Electrical Hazard. "
    "Treat an active electrical danger as urgent, generally 85-100.\n"
    "- Do not let a mention of a hospital or school alone establish that a hazard exists.\n"
    "- Prioritize actual injuries, accidents, immediate danger, severity, duration, and repeated "
    "ignored reports. Do not invent details.\n"
    "- Scores 80-100: immediate safety hazard; 50-79: significant disruption; "
    "20-49: moderate inconvenience; 1-19: minor issue; 0: no active civic issue.\n"
    "- Use a concise explanation and do not use markdown headers."
)


def is_greeting(text: str) -> bool:
    """Return True when the message is just a greeting or a help request."""
    return text.strip().lower().rstrip("!?., ") in GREETINGS


def classify_complaint(text: str) -> str:
    """Classify a civic complaint while handling explicit denials."""
    lowered = " ".join(text.lower().split())

    # These phrases deny the issue itself, not just its consequences.
    non_issue_phrases = (
        "there is no garbage problem",
        "there is no garbage issue",
        "garbage collection is regular",
        "no garbage problem",
        "no garbage issue",
        "there are no live wires",
        "there are no electrical hazards",
        "there is no electrical hazard",
        "there is no electrical issue",
        "no electrical hazard",
        "no live wires",
        "there is no power outage",
        "there is no pothole",
        "there are no potholes",
        "there is no water leak",
        "there is no leakage",
        "there is no blocked drain",
        "there are no blocked drains",
    )

    active_issue_phrases = (
        "wire is sparking",
        "wire is hanging",
        "wire is exposed",
        "is sparking",
        "is hanging",
        "is exposed",
        "has burst",
        "is flooding",
        "causing accidents",
        "causing an accident",
        "is overflowing",
        "is leaking",
        "has not been collected",
        "not collected for",
        "no electricity for",
    )

    if any(phrase in lowered for phrase in non_issue_phrases):
        if not any(phrase in lowered for phrase in active_issue_phrases):
            return "Other"

    best_category = "Other"
    best_score = (0, 0)

    for category, keywords in CATEGORY_KEYWORDS.items():
        matched = [
            keyword
            for keyword in keywords
            if keyword in lowered
        ]

        score = (
            len(matched),
            sum(len(keyword) for keyword in matched),
        )

        if score > best_score:
            best_category = category
            best_score = score

    return best_category
def estimate_priority(text: str) -> int:
    """Estimate complaint priority from 0 to 100."""
    import re

    lowered = text.lower().strip()
    score = 35

    category = classify_complaint(text)

    if category == "Other":
        return 0

    direct_harm_words = (
        "accident", "accidents", "injury", "injured", "hurt",
        "live wire", "exposed wire", "electric shock",
        "sinkhole", "flood", "sewage overflow",
        "causing accidents", "people are falling",
        "hanging wire", "sparking wire",
        "overflow onto the road",
        "water overflowing",
        "drain overflow",
        "blocked drain",
        "sewage overflow",
    )

    context_risk_words = (
        "school", "children", "child", "hospital",
        "busy road", "heavy traffic",
    )

    delay_words = (
        "days", "weeks", "months", "repeated", "again",
        "still", "no action", "ignored", "uncollected",
    )

    low_risk_words = ("minor", "small", "slight", "tiny", "cosmetic")

    def is_negated(phrase: str) -> bool:
        # Check for simple negation immediately before a matched phrase.
        pattern = (
            r"\b(?:no|not|never|without|isn't|aren't|wasn't|weren't|"
            r"hasn't|haven't|reported no|no reported)\b"
            r"(?:\W+\w+){0,3}\W+"
            + re.escape(phrase)
        )
        return re.search(pattern, lowered) is not None

    has_direct_harm = any(
        word in lowered and not is_negated(word)
        for word in direct_harm_words
    )
    has_context_risk = any(word in lowered for word in context_risk_words)
    has_delay = any(word in lowered for word in delay_words)
    has_low_risk = any(word in lowered for word in low_risk_words)

    if has_low_risk:
        score = 15

    if has_delay:
        score = max(score, 55)

    if has_context_risk:
        score = max(score, 60)

    if has_direct_harm:
        score = 85

    if "sparking" in lowered and "hospital" in lowered:
        score = 95

    return max(5, min(score, 95))



def build_fallback_analysis(text: str) -> str:
    """Local keyword-based analysis, used when the ASI:One call fails."""
    category = classify_complaint(text)
    score = estimate_priority(text)
    reason = (
        "This is a quick keyword-based estimate: it reflects the type of issue, any safety or "
        "delay signals in your description, and the general impact on daily life."
    )
    return (
        f"Category: {category}\n"
        f"Department: {DEPARTMENTS[category]}\n"
        f"Priority Score: {score}/100\n"
        f"Why this priority: {reason}\n"
        f"Suggested next action: {NEXT_ACTIONS[category]}"
    )


@protocol.on_message(ChatMessage)

async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
        ctx.logger.info("CivicPulse: handle_message started")
        await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

        text = msg.text()
        ctx.logger.info(f"CivicPulse: received message, length={len(text or '')}")
        if not text:
            return

        if is_greeting(text):
            reply_text = HELP_TEXT
        else:
            category = classify_complaint(text)

        # Explicitly reject unrelated or denied issues before calling the LLM.
        lowered = " ".join(text.lower().split())
        non_issue_phrases = (
            "there is no pothole",
            "there are no potholes",
            "there is no garbage problem",
            "there is no garbage issue",
            "garbage collection is regular",
            "there are no live wires",
            "there are no electrical hazards",
            "there is no electrical hazard",
            "there is no water leak",
            "there is no leakage",
            "there is no blocked drain",
            "there are no blocked drains",
        )

        active_issue_phrases = (
            "wire is sparking",
            "wire is hanging",
            "wire is exposed",
            "is sparking",
            "is hanging",
            "is exposed",
            "has burst",
            "is flooding",
            "causing accidents",
            "causing an accident",
            "is overflowing",
            "is leaking",
            "has not been collected",
            "not collected for",
            "no electricity for",
        )

        is_denial = (
            any(phrase in lowered for phrase in non_issue_phrases)
            and not any(phrase in lowered for phrase in active_issue_phrases)
        )

        if is_denial or category == "Other":
            reply_text = build_fallback_analysis(text)
        else:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *build_llm_message_history(ctx),
            ]
            reply_text = ask_asi1(messages)

            
            if reply_text is None:
                ctx.logger.warning(
                    "ASI:One call failed; using the local keyword fallback. "
                    "Check the ASI:One request diagnostics."
                )
                reply_text = build_fallback_analysis(text)
        content = [TextContent(type="text", text=reply_text)]

        await ctx.send(
        sender, 
        ChatMessage(
            timestamp=datetime.utcnow(),
            msg_id=uuid4(),
            content=content,
        ),
    )

@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass
