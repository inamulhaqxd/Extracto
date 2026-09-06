import re
from datetime import timedelta
from typing import Any

import rapidfuzz.fuzz
import sympy
from dateutil import parser as date_parser
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from ai_rfp_excel.app.logging import get_logger

logger = get_logger("ai.math_engine")

TRANSFORMATIONS = (*standard_transformations, implicit_multiplication_application)


class SymbolicMathEngine:
    """Universal mathematical, timeline, and fuzzy evaluation engine using SymPy, python-dateutil, and RapidFuzz."""

    @staticmethod
    def evaluate_expression(expr_str: str) -> float | int | None:
        """Parse and evaluate any arithmetic expression string dynamically using SymPy."""
        if not expr_str:
            return None

        # Clean expression (strip commas, dollar signs, trailing text)
        cleaned = re.sub(r"[,\$]", "", expr_str.strip())
        cleaned = re.sub(r"[a-zA-Z%]+$", "", cleaned).strip()

        try:
            parsed = parse_expr(cleaned, transformations=TRANSFORMATIONS, evaluate=True)
            val = float(parsed.evalf())
            if val.is_integer():
                return int(val)
            return round(val, 4)
        except Exception as e:
            logger.debug("SymPy expression parsing failed", expr=expr_str, error=str(e))
            return None

    @staticmethod
    def solve_formula_from_context(
        requirement_text: str,
        context_facts_text: str,
    ) -> str | None:
        """Dynamically detect equations and variable bindings in context text and solve using SymPy."""
        req_lower = requirement_text.lower()
        if not any(k in req_lower for k in ["formula", "calculate", "equation", "required mbps", "capacity"]):
            return None

        # 1. Search for equation pattern: TargetVar = (VarA * VarB) / Number * VarC
        formula_match = re.search(
            r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z0-9_\(\)\s\*\/\+\-\.]+)",
            context_facts_text,
        )
        if not formula_match:
            # Try to find inline math expression with numbers directly from context
            math_expr_match = re.search(
                r"(\(?\s*[\d,]+(?:\.\d+)?\s*[\*\/\+]\s*[\d,]+(?:\.\d+)?(?:[\s\*\/\+\-\(\)]*[\d,]+(?:\.\d+)?)*\s*\)?)",
                context_facts_text,
            )
            if math_expr_match:
                eval_res = SymbolicMathEngine.evaluate_expression(math_expr_match.group(1))
                if eval_res is not None:
                    unit = "Mbps" if "mbps" in req_lower else ""
                    return f"{eval_res:,} {unit}".strip()
            return None

        target_var = formula_match.group(1).strip()
        expr_raw = formula_match.group(2).strip()

        try:
            sympy_expr = parse_expr(expr_raw, transformations=TRANSFORMATIONS)
            free_symbols = {str(s) for s in sympy_expr.free_symbols}
        except Exception:
            return None

        # Use RapidFuzz and regex to bind variable values dynamically from document facts
        substitutions: dict[Any, float] = {}
        for sym_name in free_symbols:
            # Pattern 1: Regex with variable name
            pattern_var = sym_name.replace("_", r"[\s_]+")
            val_match = re.search(
                rf"{pattern_var}\s*[:=]\s*([\d,]+(?:\.\d+)?)",
                context_facts_text,
                re.IGNORECASE,
            )
            if val_match:
                substitutions[sympy.Symbol(sym_name)] = float(val_match.group(1).replace(",", ""))
                continue

            # Pattern 2: Context search with RapidFuzz
            clean_sym = sym_name.replace("_", " ").lower()
            for line in context_facts_text.split("\n"):
                if rapidfuzz.fuzz.partial_ratio(clean_sym, line.lower()) > 75:
                    num_match = re.search(r"\b([\d,]+(?:\.\d+)?)\b", line)
                    if num_match:
                        substitutions[sympy.Symbol(sym_name)] = float(num_match.group(1).replace(",", ""))
                        break

        # If all variables are bound, calculate exact solution
        if len(substitutions) == len(free_symbols) and free_symbols:
            try:
                result_val = float(sympy_expr.subs(substitutions).evalf())
                formatted = f"{int(result_val):,}" if result_val.is_integer() else f"{result_val:,.2f}"
                unit = "Mbps" if "mbps" in target_var.lower() or "mbps" in req_lower else ""
                return f"{formatted} {unit}".strip()
            except Exception as e:
                logger.debug("SymPy evaluation failed", error=str(e))

        return None

    @staticmethod
    def calculate_time_duration(
        requirement_text: str,
        context_facts_text: str,
    ) -> str | None:
        """Parse timeline timestamps and compute exact elapsed time duration using python-dateutil."""
        req_lower = requirement_text.lower()
        if not any(k in req_lower for k in ["duration", "calculate from start/end", "elapsed time", "how long did"]):
            return None

        # Look specifically for start time (first alert / incident start) and resolution time
        start_match = re.search(
            r"(\b[012]?\d:[0-5]\d\b)\s*[-\u2013\u2014:]*\s*(?:First|alert|fires|start|duty)",
            context_facts_text,
            re.IGNORECASE,
        )
        if not start_match:
            start_match = re.search(
                r"(?:first alert|started).*?(\b[012]?\d:[0-5]\d\b)",
                context_facts_text,
                re.IGNORECASE,
            )

        end_match = re.search(
            r"(\b[012]?\d:[0-5]\d\b)\s*[-\u2013\u2014:]*\s*(?:.*?(?:declared resolved|resolved|closed|back to 0%))",
            context_facts_text,
            re.IGNORECASE,
        )
        if not end_match:
            end_match = re.search(
                r"(?:declared resolved|resolved|closed).*?(\b[012]?\d:[0-5]\d\b)",
                context_facts_text,
                re.IGNORECASE,
            )

        if start_match and end_match:
            start_str = start_match.group(1)
            end_str = end_match.group(1)
        else:
            # Look at timeline entries (lines starting with HH:MM)
            timeline_times = re.findall(r"(?:^|\n)\s*([012]?\d:[0-5]\d)\b", context_facts_text)
            if len(timeline_times) >= 2:
                start_str = timeline_times[0]
                end_str = timeline_times[-1]
            else:
                return None

        try:
            t_start = date_parser.parse(start_str)
            t_end = date_parser.parse(end_str)

            # Handle cross-midnight rollover (e.g. 23:14 to 00:27)
            if t_end < t_start:
                t_end += timedelta(days=1)

            diff = t_end - t_start
            total_minutes = int(diff.total_seconds() // 60)
            hours = total_minutes // 60
            mins = total_minutes % 60

            if hours > 0 and mins > 0:
                return f"{total_minutes} minutes ({hours} hour{'s' if hours > 1 else ''} {mins} mins, from {start_str} to {end_str})"
            elif hours > 0:
                return f"{hours} hour{'s' if hours > 1 else ''} ({total_minutes} minutes, from {start_str} to {end_str})"
            else:
                return f"{total_minutes} minutes (from {start_str} to {end_str})"
        except Exception as e:
            logger.debug("Failed dateutil duration calculation", error=str(e))
            return None
