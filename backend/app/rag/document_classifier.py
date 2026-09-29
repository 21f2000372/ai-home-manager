from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Dict, Iterable, List, Set


@dataclass
class ClassificationResult:
    domain: str
    document_type: str
    confidence: float
    reason: str


FINANCE_KEYWORDS: Set[str] = {
    "invoice", "retail invoice", "receipt", "retail receipt", "bill",
    "amount", "total", "grand total", "subtotal", "payment", "paid",
    "cash received", "balance", "discount", "due", "merchant",
    "gst", "tax", "vat", "card", "cash",
}

MAINTENANCE_KEYWORDS: Set[str] = {
    "repair", "service", "maintenance", "warranty", "appliance",
    "technician", "serial number", "model number", "installation",
    "replacement", "service center", "service centre",
}

GROCERY_ITEM_KEYWORDS: Set[str] = {
    "grocery", "groceries", "supermarket", "super market", "mart", "dmart",
    "rice", "milk", "oat milk", "bread", "brown bread", "whole wheat bread",
    "fruit", "dragon fruit", "banana", "bananas", "vegetable", "vegetables",
    "lemon", "atta", "flour", "oil", "dal", "pulses", "eggs", "egg",
    "butter", "cheese", "yogurt", "curd", "sugar", "salt", "tea", "coffee",
    "qty", "quantity", "item name",
}

GROCERY_LIST_MARKERS: Set[str] = {
    "grocery list", "shopping list", "things to buy", "items to buy", "buy list",
}

UTILITY_KEYWORDS: Set[str] = {
    "electricity", "electricity bill", "water bill", "gas bill", "utility",
    "consumer number", "consumer no", "meter number", "meter no",
    "units consumed", "kwh",
}

BANK_KEYWORDS: Set[str] = {
    "bank statement", "account statement", "opening balance", "closing balance",
    "withdrawal", "deposit", "debit", "credit", "account number", "transaction",
}

LOAN_KEYWORDS: Set[str] = {
    "loan", "emi", "principal", "interest", "outstanding balance",
    "repayment", "installment", "instalment",
}

WARRANTY_KEYWORDS: Set[str] = {
    "warranty", "warranty period", "warranty expiry", "warranty expires",
    "guarantee",
}

REPAIR_KEYWORDS: Set[str] = {
    "repair", "service charge", "technician", "service center",
    "service centre", "replacement part", "labor charge", "labour charge",
    "parts replaced",
}

TASK_KEYWORDS: Set[str] = {
    "to do", "todo", "task list", "appointment", "meeting",
    "schedule", "reminder", "due date",
}

IRRELEVANT_KEYWORDS: Set[str] = {
    "resume", "curriculum vitae", "university", "exam", "marksheet",
    "medical report", "patient", "prescription", "diagnosis", "passport",
    "aadhaar", "driving license",
}

TRANSACTION_MARKERS: Set[str] = {
    "receipt", "retail receipt", "invoice", "retail invoice", "subtotal",
    "grand total", "total amount", "amount paid", "payment", "paid",
    "cash", "card", "gst", "tax",
}

BILL_MARKERS: Set[str] = {
    "bill", "invoice", "amount due", "due date", "payment due",
}


def _normalize_ocr_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = re.sub(r"---\s*page\s+\d+\s*---", " ", text)

    replacements = {
        "feta il inyqice": "retail invoice",
        "reta il inyqice": "retail invoice",
        "reta il invoice": "retail invoice",
        "inyqice": "invoice",
        "iny0ice": "invoice",
        "superma rket": "supermarket",
        "super market": "supermarket",
        "gand total": "grand total",
        "grand t0tal": "grand total",
        "ttal": "total",
        "total anunt": "total amount",
        "anunt": "amount",
        "dispount": "discount",
        "cash feceived": "cash received",
        "feceived": "received",
        "lem on": "lemon",
        "tem kame": "item name",
        "mem kame": "item name",
        "balartz": "balance",
    }

    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)

    text = re.sub(r"[^a-z0-9₹$€£%\s]", " ", text)
    return " ".join(text.split())


def _contains_phrase(text: str, phrase: str) -> bool:
    phrase = " ".join((phrase or "").lower().split())
    if not phrase:
        return False

    pattern = r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])"
    if re.search(pattern, text):
        return True

    compact_phrase = phrase.replace(" ", "")
    if len(compact_phrase) < 6:
        return False

    compact_text = text.replace(" ", "")
    return compact_phrase in compact_text


def _count_matches(text: str, keywords: Iterable[str]) -> int:
    return sum(1 for keyword in keywords if _contains_phrase(text, keyword))


def _raw_content_lines(text: str) -> List[str]:
    lines: List[str] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^---\s*page\s+\d+\s*---$", line, flags=re.I):
            continue
        lines.append(line)
    return lines


def _list_structure_score(text: str) -> int:
    score = 0
    quantity_pattern = re.compile(
        r"\b\d+(?:\.\d+)?\s*"
        r"(?:kg|kgs|g|gm|grams?|l|ltr|litres?|liters?|ml|"
        r"pcs?|pieces?|packs?|packets?|loaves?|loaf|dozen)?\b",
        flags=re.I,
    )

    for line in _raw_content_lines(text):
        lower = line.lower()

        if lower in GROCERY_LIST_MARKERS or lower.startswith("grocery list"):
            continue

        has_separator = bool(re.search(r"\s[-:x×]\s|\t", line))
        has_quantity = bool(quantity_pattern.search(line))
        has_bullet = bool(re.match(r"^[\-\*\u2022]\s+", line))

        if (has_separator and has_quantity) or (has_bullet and has_quantity):
            score += 1
        elif has_separator and re.search(r"\d", line):
            score += 1

    return score


def _confidence(base: float, evidence: int, step: float, cap: float = 0.98) -> float:
    return round(min(base + (max(evidence, 0) * step), cap), 2)


def classify_document(text: str) -> ClassificationResult:
    """
    Deterministically classify extracted household-document text.

    Classification is a routing hint only. The later tool-less document
    interpreter still reads the document directly and proposes evidence-linked
    actions.
    """

    normalized = _normalize_ocr_text(text)

    if not normalized:
        return ClassificationResult(
            domain="NeedsReview",
            document_type="Unknown",
            confidence=0.0,
            reason="No readable text was extracted.",
        )

    scores: Dict[str, int] = {
        "finance": _count_matches(normalized, FINANCE_KEYWORDS),
        "maintenance": _count_matches(normalized, MAINTENANCE_KEYWORDS),
        "grocery": _count_matches(normalized, GROCERY_ITEM_KEYWORDS),
        "grocery_list_marker": _count_matches(normalized, GROCERY_LIST_MARKERS),
        "utility": _count_matches(normalized, UTILITY_KEYWORDS),
        "bank": _count_matches(normalized, BANK_KEYWORDS),
        "loan": _count_matches(normalized, LOAN_KEYWORDS),
        "warranty": _count_matches(normalized, WARRANTY_KEYWORDS),
        "repair": _count_matches(normalized, REPAIR_KEYWORDS),
        "tasks": _count_matches(normalized, TASK_KEYWORDS),
        "irrelevant": _count_matches(normalized, IRRELEVANT_KEYWORDS),
        "transaction": _count_matches(normalized, TRANSACTION_MARKERS),
        "bill": _count_matches(normalized, BILL_MARKERS),
    }

    list_structure = _list_structure_score(text)

    supported_signal = (
        scores["finance"]
        + scores["maintenance"]
        + scores["grocery"]
        + scores["utility"]
        + scores["bank"]
        + scores["loan"]
        + scores["tasks"]
    )

    if scores["irrelevant"] >= 2 and supported_signal == 0:
        return ClassificationResult(
            domain="Irrelevant",
            document_type="Unsupported",
            confidence=0.95,
            reason="Document appears unrelated to supported household domains.",
        )

    if scores["grocery_list_marker"] >= 1:
        evidence = (
            scores["grocery_list_marker"]
            + min(scores["grocery"], 4)
            + min(list_structure, 4)
        )
        return ClassificationResult(
            domain="Food",
            document_type="GroceryList",
            confidence=_confidence(0.82, evidence, 0.025),
            reason=(
                "An explicit grocery/shopping-list marker and list content "
                "were detected."
            ),
        )

    if (
        list_structure >= 2
        and scores["grocery"] >= 2
        and scores["transaction"] == 0
    ):
        evidence = min(list_structure, 4) + min(scores["grocery"], 4)
        return ClassificationResult(
            domain="Food",
            document_type="GroceryList",
            confidence=_confidence(0.72, evidence, 0.025),
            reason="Grocery terms and list-style quantity lines were detected.",
        )

    if scores["warranty"] >= 1:
        evidence = scores["warranty"] + min(scores["maintenance"], 3)
        return ClassificationResult(
            domain="Maintenance",
            document_type="Warranty",
            confidence=_confidence(0.76, evidence, 0.04),
            reason="Warranty-related terms were detected.",
        )

    if scores["repair"] >= 2:
        evidence = scores["repair"] + min(scores["finance"], 2)
        return ClassificationResult(
            domain="Maintenance",
            document_type="RepairInvoice",
            confidence=_confidence(0.74, evidence, 0.035),
            reason="Repair/service terms were detected.",
        )

    if scores["utility"] >= 1 and (scores["bill"] >= 1 or scores["finance"] >= 1):
        evidence = scores["utility"] + scores["bill"] + min(scores["finance"], 3)
        return ClassificationResult(
            domain="Finance",
            document_type="UtilityBill",
            confidence=_confidence(0.76, evidence, 0.035),
            reason="Utility and billing terms were detected.",
        )

    if scores["bank"] >= 2:
        return ClassificationResult(
            domain="Finance",
            document_type="BankStatement",
            confidence=_confidence(0.76, scores["bank"], 0.04),
            reason="Bank-statement terms were detected.",
        )

    if scores["loan"] >= 2:
        return ClassificationResult(
            domain="Finance",
            document_type="LoanStatement",
            confidence=_confidence(0.76, scores["loan"], 0.04),
            reason="Loan/repayment terms were detected.",
        )

    if scores["grocery"] >= 2 and scores["transaction"] >= 2:
        evidence = min(scores["grocery"], 5) + min(scores["transaction"], 5)
        return ClassificationResult(
            domain="Finance",
            document_type="GroceryReceipt",
            confidence=_confidence(0.74, evidence, 0.025),
            reason="Grocery-item and completed-transaction terms were detected.",
        )

    if scores["finance"] >= 2 or scores["transaction"] >= 2:
        evidence = max(scores["finance"], scores["transaction"])
        return ClassificationResult(
            domain="Finance",
            document_type="ReceiptOrInvoice",
            confidence=_confidence(0.66, evidence, 0.04, cap=0.95),
            reason="Receipt, invoice, payment, or amount terms were detected.",
        )

    if scores["tasks"] >= 2:
        return ClassificationResult(
            domain="Tasks",
            document_type="TaskOrSchedule",
            confidence=_confidence(0.68, scores["tasks"], 0.05, cap=0.92),
            reason="Task/schedule terms were detected.",
        )

    if scores["maintenance"] >= 1:
        return ClassificationResult(
            domain="Maintenance",
            document_type="MaintenanceDocument",
            confidence=_confidence(0.62, scores["maintenance"], 0.05, cap=0.90),
            reason="Maintenance-related terms were detected.",
        )

    return ClassificationResult(
        domain="NeedsReview",
        document_type="Unknown",
        confidence=0.40,
        reason="Document could not be confidently classified.",
    )
