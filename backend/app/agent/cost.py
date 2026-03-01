from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

INPUT_PRICE_PER_M = Decimal("3.00")
OUTPUT_PRICE_PER_M = Decimal("15.00")


@dataclass
class TokenUsage:
    tokens_in: int = 0
    tokens_out: int = 0

    @property
    def cost_usd(self) -> Decimal:
        cost = (Decimal(self.tokens_in) / 1_000_000 * INPUT_PRICE_PER_M) + (
            Decimal(self.tokens_out) / 1_000_000 * OUTPUT_PRICE_PER_M
        )
        return cost.quantize(Decimal("0.000001"))


def parse_claude_code_usage(stderr_output: str) -> TokenUsage:
    """Parse token usage from Claude Code CLI stderr output."""
    tokens_in = 0
    tokens_out = 0

    # Look for patterns like "input: 50000 tokens" or "Input tokens: 50000"
    in_match = re.search(r"(?:input|Input)[\s:]*(\d[\d,]*)\s*tokens?", stderr_output)
    out_match = re.search(r"(?:output|Output)[\s:]*(\d[\d,]*)\s*tokens?", stderr_output)

    if in_match:
        tokens_in = int(in_match.group(1).replace(",", ""))
    if out_match:
        tokens_out = int(out_match.group(1).replace(",", ""))

    return TokenUsage(tokens_in=tokens_in, tokens_out=tokens_out)
