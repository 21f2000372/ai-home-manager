from __future__ import annotations

from dataclasses import dataclass
import re

@dataclass
class ClassificationResult:
    domain: str
    document_type: str
    confidence: float
    reason: str


FINANCE_KEYWORDS = {
    "invoice",
    "retail invoice",
    "receipt",
    "bill",

    "amount",
    "total",
    "grand total",
    "subtotal",

    "payment",
    "paid",
    "cash received",
    "balance",
    "discount",

    "due",

    "bank",
    "statement",
    "loan",
    "emi",
    "transaction",
    "debit",
    "credit",

    "merchant",

    "gst",
    "tax",
}

MAINTENANCE_KEYWORDS = {
    "repair",
    "service",
    "maintenance",
    "warranty",
    "appliance",
    "technician",
    "serial number",
    "model number",
    "installation",
    "replacement",
    "service center",
    "service centre",
}

GROCERY_KEYWORDS = {
    "grocery",

    "supermarket",
    "super market",
    "mart",
    "dmart",

    "retail invoice",
    "retail receipt",

    "rice",
    "milk",
    "bread",
    "lemon",
    "fruit",
    "vegetable",
    "vegetables",

    "atta",
    "flour",
    "oil",
    "dal",
    "pulses",

    "qty",
    "quantity",

    "item name",
}

UTILITY_KEYWORDS = {
    "electricity",
    "water bill",
    "gas bill",
    "utility",
    "consumer number",
    "meter number",
    "units consumed",
}

BANK_KEYWORDS = {
    "bank statement",
    "account statement",
    "opening balance",
    "closing balance",
    "withdrawal",
    "deposit",
    "debit",
    "credit",
}

LOAN_KEYWORDS = {
    "loan",
    "emi",
    "principal",
    "interest",
    "outstanding balance",
    "repayment",
}

WARRANTY_KEYWORDS = {
    "warranty",
    "warranty period",
    "warranty expiry",
    "guarantee",
}

REPAIR_KEYWORDS = {
    "repair",
    "service charge",
    "technician",
    "service center",
    "service centre",
    "replacement part",
    "labor charge",
    "labour charge",
}

IRRELEVANT_KEYWORDS = {
    "resume",
    "curriculum vitae",
    "school",
    "university",
    "exam",
    "marksheet",
    "medical report",
    "patient",
    "prescription",
    "diagnosis",
    "passport",
    "aadhaar",
    "driving license",
}


def _count_matches(
    text: str,
    keywords: set,
) -> int:
    """
    Count keyword matches while tolerating
    OCR-generated spaces inside words.
    """

    compact_text = text.replace(
        " ",
        ""
    )

    matches = 0

    for keyword in keywords:

        normalized_keyword = (
            keyword.lower().strip()
        )

        compact_keyword = (
            normalized_keyword.replace(
                " ",
                ""
            )
        )

        if normalized_keyword in text:
            matches += 1

        elif (
            len(compact_keyword) >= 5
            and compact_keyword in compact_text
        ):
            matches += 1

    return matches

def _normalize_ocr_text(text: str) -> str:
    """
    Normalize noisy OCR text before classification.

    This fixes common OCR mistakes and spacing issues
    before keyword matching.
    """

    text = text.lower()

    # Common OCR errors seen in receipts/invoices.
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
        text = text.replace(
            wrong,
            correct,
        )

    # Replace punctuation with spaces.
    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text,
    )

    # Collapse repeated whitespace.
    text = " ".join(
        text.split()
    )

    return text

def classify_document(
    text: str,
) -> ClassificationResult:
    """
    Classify extracted document text.

    Returns:
        Finance
        Maintenance
        Irrelevant
        NeedsReview
    """

    normalized = _normalize_ocr_text(
        text
    )

   

    if not normalized:
        return ClassificationResult(
            domain="NeedsReview",
            document_type="Unknown",
            confidence=0.0,
            reason="No readable text was extracted.",
        )

    irrelevant_score = _count_matches(
        normalized,
        IRRELEVANT_KEYWORDS,
    )

    finance_score = _count_matches(
        normalized,
        FINANCE_KEYWORDS,
    )

    maintenance_score = _count_matches(
        normalized,
        MAINTENANCE_KEYWORDS,
    )

    # -------------------------
    # Irrelevant
    # -------------------------

    if (
        irrelevant_score >= 2
        and finance_score == 0
        and maintenance_score == 0
    ):
        return ClassificationResult(
            domain="Irrelevant",
            document_type="Unsupported",
            confidence=0.95,
            reason="Document appears unrelated to Finance or Maintenance.",
        )

    # -------------------------
    # Maintenance
    # -------------------------

    warranty_score = _count_matches(
        normalized,
        WARRANTY_KEYWORDS,
    )

    repair_score = _count_matches(
        normalized,
        REPAIR_KEYWORDS,
    )

    if warranty_score >= 1:
        return ClassificationResult(
            domain="Maintenance",
            document_type="Warranty",
            confidence=min(
                0.70 + warranty_score * 0.08,
                0.98,
            ),
            reason="Warranty-related terms were detected.",
        )

    if repair_score >= 2:
        return ClassificationResult(
            domain="Maintenance",
            document_type="RepairInvoice",
            confidence=min(
                0.70 + repair_score * 0.07,
                0.98,
            ),
            reason="Repair/service-related terms were detected.",
        )

    # -------------------------
    # Finance
    # -------------------------

    grocery_score = _count_matches(
        normalized,
        GROCERY_KEYWORDS,
    )

    utility_score = _count_matches(
        normalized,
        UTILITY_KEYWORDS,
    )

    bank_score = _count_matches(
        normalized,
        BANK_KEYWORDS,
    )

    loan_score = _count_matches(
        normalized,
        LOAN_KEYWORDS,
    )

    if grocery_score >= 2 and finance_score >= 1:
        return ClassificationResult(
            domain="Finance",
            document_type="GroceryReceipt",
            confidence=min(
                0.72 + grocery_score * 0.04,
                0.98,
            ),
            reason="Grocery and receipt/payment terms were detected.",
        )

    if utility_score >= 1 and finance_score >= 1:
        return ClassificationResult(
            domain="Finance",
            document_type="UtilityBill",
            confidence=min(
                0.75 + utility_score * 0.05,
                0.98,
            ),
            reason="Utility billing terms were detected.",
        )

    if bank_score >= 2:
        return ClassificationResult(
            domain="Finance",
            document_type="BankStatement",
            confidence=min(
                0.75 + bank_score * 0.05,
                0.98,
            ),
            reason="Bank statement terms were detected.",
        )

    if loan_score >= 2:
        return ClassificationResult(
            domain="Finance",
            document_type="LoanStatement",
            confidence=min(
                0.75 + loan_score * 0.05,
                0.98,
            ),
            reason="Loan repayment terms were detected.",
        )

    if finance_score >= 2:
        return ClassificationResult(
            domain="Finance",
            document_type="ReceiptOrInvoice",
            confidence=min(
                0.65 + finance_score * 0.04,
                0.95,
            ),
            reason="Finance-related terms were detected.",
        )

    if maintenance_score >= 1:
        return ClassificationResult(
            domain="Maintenance",
            document_type="MaintenanceDocument",
            confidence=0.65,
            reason="Maintenance-related terms were detected.",
        )

    return ClassificationResult(
        domain="NeedsReview",
        document_type="Unknown",
        confidence=0.40,
        reason="Document could not be confidently classified.",
    )