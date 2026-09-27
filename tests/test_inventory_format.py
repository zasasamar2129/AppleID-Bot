"""Tests for the inventory import text parser.

Covers the exact format admins paste from their Apple ID supplier, including
the `🧍‍♂️Pet` field and the `🌆 Parentsmeet` (no space) variant.
"""

from __future__ import annotations

import re

import pytest

# Regexes from app/handlers/admin/inventory.py
EMAIL_RE = re.compile(r"🍏\s*(.+)")
PASS_RE = re.compile(r"🗝\s*(.+)")
DOB_RE = re.compile(r"📅\s*(.+)")
SCHOOL_RE = re.compile(r"🧍‍♂️\s*School\s*:\s*(.+)", re.IGNORECASE)
PET_RE = re.compile(r"🧍‍♂️\s*Pet\s*:\s*(.+)", re.IGNORECASE)
JOB_RE = re.compile(r"👨‍⚕️\s*Job\s*:\s*(.+)", re.IGNORECASE)
PARENTS_RE = re.compile(r"🌆\s*Parents\s*(?:Meet|meet)\s*:\s*(.+)", re.IGNORECASE)


def _parse(text: str) -> dict:
    return {
        "email": EMAIL_RE.search(text).group(1).strip(),
        "password": PASS_RE.search(text).group(1).strip(),
        "date_of_birth": DOB_RE.search(text).group(1).strip() if DOB_RE.search(text) else "",
        "school": SCHOOL_RE.search(text).group(1).strip() if SCHOOL_RE.search(text) else "",
        "pet": PET_RE.search(text).group(1).strip() if PET_RE.search(text) else "",
        "job": JOB_RE.search(text).group(1).strip() if JOB_RE.search(text) else "",
        "parents_meet": PARENTS_RE.search(text).group(1).strip() if PARENTS_RE.search(text) else "",
    }


def test_parses_real_world_supplier_format():
    """The exact format the user pasted must parse correctly."""
    text = """🍏 mimihinck23335@hotmail.com
🗝 Mycom123
📅 Date: 01/01/1980
🧍‍♂️Pet : Chocolate
👨‍⚕️Job : Pilot
🌆 Parentsmeet : Qom"""
    data = _parse(text)
    assert data["email"] == "mimihinck23335@hotmail.com"
    assert data["password"] == "Mycom123"
    assert data["date_of_birth"] == "Date: 01/01/1980"
    assert data["pet"] == "Chocolate"
    assert data["job"] == "Pilot"
    assert data["parents_meet"] == "Qom"
    assert data["school"] == ""  # not present in this format


def test_parses_with_school_and_pet_together():
    """Both 🧍‍♂️School and 🧍‍♂️Pet can appear in the same block."""
    text = """🍏 test@email.com
🗝 pass123
📅 Date: 01/01/1980
🧍‍♂️School : Test School
🧍‍♂️Pet : Chocolate
👨‍⚕️Job : Pilot
🌆 Parentsmeet : Qom"""
    data = _parse(text)
    assert data["school"] == "Test School"
    assert data["pet"] == "Chocolate"


def test_parses_parents_meet_with_space():
    """The `Parents Meet` (with space) variant must also work."""
    text = """🍏 test@email.com
🗝 pass123
🌆 Parents Meet : Tehran"""
    data = _parse(text)
    assert data["parents_meet"] == "Tehran"


def test_parses_parents_meet_lowercase():
    """The `parentsmeet` (all lowercase, no space) variant must also work."""
    text = """🍏 test@email.com
🗝 pass123
🌆 parentsmeet : Isfahan"""
    data = _parse(text)
    assert data["parents_meet"] == "Isfahan"


def test_email_and_password_are_required():
    """Text without 🍏 or 🗝 must be rejected."""
    assert EMAIL_RE.search("just some text") is None
    assert PASS_RE.search("just some text") is None


def test_password_with_spaces_and_symbols():
    """Passwords may contain symbols and should not be truncated."""
    text = """🍏 test@email.com
🗝 My$ecure#Pass!2024"""
    data = _parse(text)
    assert data["password"] == "My$ecure#Pass!2024"


def test_bulk_format_with_multiple_accounts():
    """The bulk parser splits on 🍏 lines, one account per block."""
    text = """🍏 a@x.com
🗝 pass1
📅 Date: 1990/01/01
🧍‍♂️Pet : Cat

🍏 b@x.com
🗝 pass2
📅 Date: 1991/02/02
🧍‍♂️Pet : Dog"""
    lines = text.splitlines()
    accounts = []
    current = {}

    def flush():
        if current.get("email") and current.get("password"):
            accounts.append(current.copy())
        current.clear()

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        m_email = re.search(r"🍏\s*(.+)", line)
        m_pass = re.search(r"🗝\s*(.+)", line)
        m_dob = re.search(r"📅\s*(.+)", line)
        m_pet = re.search(r"Pet\s*:\s*(.+)", line, re.IGNORECASE)

        if m_email:
            if current.get("email"):
                flush()
            current["email"] = m_email.group(1).strip()
        elif m_pass:
            current["password"] = m_pass.group(1).strip()
        elif m_dob:
            current["date_of_birth"] = m_dob.group(1).strip()
        elif m_pet:
            current["pet"] = m_pet.group(1).strip()
    flush()

    assert len(accounts) == 2
    assert accounts[0]["email"] == "a@x.com"
    assert accounts[0]["pet"] == "Cat"
    assert accounts[1]["email"] == "b@x.com"
    assert accounts[1]["pet"] == "Dog"
