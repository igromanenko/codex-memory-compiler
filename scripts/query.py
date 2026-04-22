"""
Query the knowledge base using index-guided retrieval (no RAG).

The LLM reads the index, picks relevant articles, and synthesizes an answer.
No vector database, no embeddings, no chunking - just structured markdown
and an index the LLM can reason over.

Usage:
    python3 scripts/query.py "How should I handle auth redirects?"
    python3 scripts/query.py "What patterns do I use for API design?" --file-back
"""

from __future__ import annotations

import argparse

from config import KNOWLEDGE_DIR, QA_DIR, now_iso
from llm import run_json_response, run_text_response
from utils import apply_write_operations, load_state, read_all_wiki_content, record_usage, save_state

FILE_BACK_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "answer": {"type": "string"},
        "consulted": {
            "type": "array",
            "items": {"type": "string"},
        },
        "writes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "path": {"type": "string"},
                    "operation": {"type": "string", "enum": ["write", "append"]},
                    "content": {"type": "string"},
                },
                "required": ["path", "operation", "content"],
            },
        },
    },
    "required": ["answer", "consulted", "writes"],
}


def run_query(question: str, file_back: bool = False) -> str:
    """Query the knowledge base and optionally file the answer back."""
    wiki_content = read_all_wiki_content()

    file_back_instructions = ""
    if file_back:
        timestamp = now_iso()
        file_back_instructions = f"""

## File Back Instructions (JSON mode)

After answering, do the following:
1. Create a Q&A article at {QA_DIR}/ with the filename being a slugified version
   of the question (e.g., knowledge/qa/how-to-handle-auth-redirects.md)
2. Use the Q&A article format from the schema (frontmatter with title, question,
   consulted articles, filed date)
3. Update {KNOWLEDGE_DIR / 'index.md'} with a new row for this Q&A article
4. Append to {KNOWLEDGE_DIR / 'log.md'}:
   ## [{timestamp}] query (filed) | question summary
   - Question: {question}
   - Consulted: [[list of articles read]]
   - Filed to: [[qa/article-name]]
5. Return JSON with:
   - `answer`: the final user-facing answer
   - `consulted`: the consulted wikilinks, without `.md`
   - `writes`: repo-relative file operations
6. Use `operation: "write"` for the QA file and `knowledge/index.md`
7. Use `operation: "append"` only for `knowledge/log.md`
"""

    prompt = f"""You are a knowledge base query engine. Answer the user's question by
consulting the knowledge base below.

## How to Answer

1. Read the INDEX section first - it lists every article with a one-line summary
2. Identify 3-10 articles that are relevant to the question
3. Read those articles carefully (they're included below)
4. Synthesize a clear, thorough answer
5. Cite your sources using [[wikilinks]] (e.g., [[concepts/supabase-auth]])
6. If the knowledge base doesn't contain relevant information, say so honestly
7. If file-back instructions are present, answer the user and return the requested JSON only

## Knowledge Base

{wiki_content}

## Question

{question}
{file_back_instructions}"""

    try:
        if file_back:
            payload, result = run_json_response(
                prompt=prompt,
                instructions=(
                    "You answer questions against a markdown knowledge base. If file-back "
                    "instructions are present, only emit JSON that matches the schema."
                ),
                schema_name="knowledge_query_file_back",
                schema=FILE_BACK_SCHEMA,
                max_output_tokens=16_000,
            )
            answer = payload["answer"]
            apply_write_operations(payload["writes"])
        else:
            result = run_text_response(
                prompt=prompt,
                instructions=(
                    "You answer questions against a markdown knowledge base. Cite sources "
                    "using [[wikilinks]] when the knowledge base supports the claim."
                ),
                max_output_tokens=8_000,
            )
            answer = result.text
    except Exception as e:
        answer = f"Error querying knowledge base: {e}"
        result = None

    # Update state
    state = load_state()
    state["query_count"] = state.get("query_count", 0) + 1
    if result is not None:
        record_usage(state, result.usage, result.cost_usd)
    save_state(state)

    return answer


def main():
    parser = argparse.ArgumentParser(description="Query the personal knowledge base")
    parser.add_argument("question", help="The question to ask")
    parser.add_argument(
        "--file-back",
        action="store_true",
        help="File the answer back into the knowledge base as a Q&A article",
    )
    args = parser.parse_args()

    print(f"Question: {args.question}")
    print(f"File back: {'yes' if args.file_back else 'no'}")
    print("-" * 60)

    qa_before = len(list(QA_DIR.glob("*.md"))) if QA_DIR.exists() else 0
    answer = run_query(args.question, file_back=args.file_back)
    print(answer)

    if args.file_back:
        print("\n" + "-" * 60)
        qa_after = len(list(QA_DIR.glob("*.md"))) if QA_DIR.exists() else 0
        if qa_after > qa_before and not answer.startswith("Error querying knowledge base:"):
            print(f"Answer filed to knowledge/qa/ ({qa_after} Q&A articles total)")
        else:
            print("Answer was not filed to knowledge/qa/")


if __name__ == "__main__":
    main()
