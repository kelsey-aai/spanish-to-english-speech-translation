"""Spanish -> English translation prompt for llm_gateway.

{{turn}} and {{history_3}} are template variables the server fills in for each
final turn. Keep them exactly as written.
"""

ES_TO_EN_PROMPT = """Translate the current turn from Spanish into natural American English.
Reply with only the English translation, no notes or quotation marks.

Rules:
- Speakers may be from Mexico, Spain, the Caribbean, Central or South America. Translate regional words by meaning (for example "ahorita", "vale", "guagua", "chévere"), not word for word.
- If the speaker switches into English mid-sentence, keep their English as spoken.
- Keep names of people, places, companies and products as spoken.
- Write numbers, dates and money the US way: "1.500,00 €" becomes "€1,500.00", "el 3 de mayo" becomes "May 3", "las 19:30" becomes "7:30 PM".
- Use the earlier turns only for context. Do not translate them again.

Earlier turns: {{history_3}}

Current turn: {{turn}}"""
