"""Prompt templates for grounded RAG generation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RAGPrompt:
    """Chat messages passed to an LLM client."""

    system: str
    user: str

    @property
    def messages(self) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": self.system},
            {"role": "user", "content": self.user},
        ]


SYSTEM_ROLE = """You are a careful research knowledge-base assistant.
Answer primarily from the retrieved context. Do not use unsupported facts.
When the context is insufficient, clearly say that the knowledge base did not
find sufficient evidence instead of guessing.
"""

OUTPUT_FORMAT = """Output Format:
Return a concise answer in plain text. Add citations in the form [1], [2]
immediately after claims supported by the corresponding context item.
"""

CITATION_RULES = """Citation Rules:
- Use only citation numbers that appear in Retrieved Context.
- Never invent document names, page numbers, or citation numbers.
- If a source has no page number, do not infer or fabricate one.
"""

INSUFFICIENT_EVIDENCE_RULES = """Insufficient Evidence Rules:
If Retrieved Context is empty or does not support the answer, explicitly state:
“当前知识库中未找到充分依据。” Do not present an unsupported answer as fact.
"""


def build_prompt(
    question: str,
    context: str,
    low_relevance: bool = False,
) -> RAGPrompt:
    """Build a stable grounded prompt from a question and bounded context."""

    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string")
    if not isinstance(context, str):
        raise TypeError("context must be a string")

    system = "\n\n".join(
        [
            SYSTEM_ROLE.strip(),
            OUTPUT_FORMAT.strip(),
            CITATION_RULES.strip(),
            INSUFFICIENT_EVIDENCE_RULES.strip(),
        ]
    )
    user = "\n\n".join(
        [
            "Retrieved Context:\n" + (context or "(No retrieved context.)"),
            (
                "Evidence Quality Notice:\n"
                "The retrieved evidence may be weak. Distinguish supported facts "
                "from uncertainty."
                if low_relevance
                else ""
            ),
            "User Question:\n" + question.strip(),
        ]
    )
    return RAGPrompt(system=system, user=user)


__all__ = ["RAGPrompt", "build_prompt"]
