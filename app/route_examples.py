"""Example questions for the semantic router: what each route sounds like.

Why examples and not a trained classifier: the list is short, anyone can read it, and adding a
phrasing the router missed is one line here. Only routes that are safe to pick by similarity are
listed. `enroll` (it writes) and `followup` (it needs the saved recommendation) are never chosen
here; the keyword rules decide those.
"""

EXAMPLES: dict[str, list[str]] = {
    "profile": [
        "list my skills",
        "what skills do I have on file",
        "show me my profile",
        "what courses have I completed",
        "which courses am I enrolled in",
        "what am I currently signed up for",
        "tell me what I already know",
        "what is on my record",
        "what training have I done so far",
        "show my completed courses",
        "remind me which courses I took",
        "which classes am I registered for",
    ],
    "gaps": [
        "which skills am I missing",
        "what skills do I lack for my goal",
        "what am I missing for my dream job",
        "show my skill gaps",
        "how far am I from the role I want",
        "what do I still need for my target role",
        "compare my skills with the roles I am aiming for",
        "what stands between me and my next role",
    ],
    "advise": [
        "what skills should I develop for my next career opportunity",
        "recommend some courses for me",
        "what should I learn next",
        "how can I grow in my career",
        "suggest a role I could move into",
        "I want a promotion, what do you suggest",
        "which course should I take to improve",
        "help me plan my next career step",
        "what roles fit me",
        "how do I get better at my job",
    ],
    "out_of_scope": [
        "what is the weather in Paris",
        "tell me a joke",
        "who won the football game last night",
        "give me a recipe for pasta",
        "what is the capital of France",
        "translate this sentence into Spanish",
        "what time is it in Tokyo",
        "write me a poem",
        "how do I fix my car",
        "what is the stock price of Apple",
        "what is in the news today",
        "what is 12 times 15",
    ],
}
