from __future__ import annotations


def extract_text_from_adf(adf: dict | None) -> str:
    """Extract plain text from Jira's Atlassian Document Format."""
    if not adf:
        return ""
    parts: list[str] = []
    _walk(adf, parts)
    return "\n".join(parts).strip()


def _walk(node: dict, parts: list[str]) -> None:
    node_type = node.get("type", "")

    if node_type == "text":
        parts.append(node.get("text", ""))
        return

    if node_type == "hardBreak":
        parts.append("\n")
        return

    for child in node.get("content", []):
        _walk(child, parts)

    # Add newline after block-level nodes
    if node_type in ("paragraph", "heading", "bulletList", "orderedList", "listItem"):
        parts.append("\n")
