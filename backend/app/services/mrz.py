"""
MRZ (Machine Readable Zone) parser + ICAO Doc 9303 checksum validator.

This is the most reliable, deterministic signal in the whole pipeline:
every TD3 passport MRZ (the 2 lines of 44 characters at the bottom of the
photo page) encodes check digits for the passport number, date of birth,
expiry date, and a final composite check digit. If OCR gives us the MRZ
text, we can verify it mathematically -- no ML guesswork needed. A
mismatch here is one of the strongest real-world tampering signals
(e.g. someone edited the printed DOB but didn't/couldn't recompute the
check digit hidden in the MRZ).
"""
import re
from dataclasses import dataclass, field

# ICAO 9303 character weighting for check digits
_WEIGHTS = [7, 3, 1]
_CHAR_VALUES = {c: i for i, c in enumerate("0123456789")}
_CHAR_VALUES.update({c: i + 10 for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")})
_CHAR_VALUES["<"] = 0


def _char_value(c: str) -> int:
    return _CHAR_VALUES.get(c.upper(), 0)


def compute_check_digit(data: str) -> int:
    total = 0
    for i, ch in enumerate(data):
        total += _char_value(ch) * _WEIGHTS[i % 3]
    return total % 10


@dataclass
class MRZCheck:
    field: str
    raw: str
    expected_check_digit: int
    found_check_digit: str
    passed: bool


@dataclass
class MRZResult:
    valid_format: bool
    line1: str = ""
    line2: str = ""
    document_type: str = ""
    issuing_country: str = ""
    surname: str = ""
    given_names: str = ""
    passport_number: str = ""
    nationality: str = ""
    date_of_birth: str = ""
    sex: str = ""
    date_of_expiry: str = ""
    checks: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    @property
    def all_checks_passed(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)

    @property
    def failed_checks(self):
        return [c for c in self.checks if not c.passed]


def _clean_mrz_line(line: str) -> str:
    # OCR often confuses <-> especially with spaces/underscores near it
    line = line.upper().replace(" ", "")
    line = re.sub(r"[_\-]", "<", line)
    return line


def find_mrz_lines(ocr_text: str):
    """Pull the two 44-char TD3 MRZ lines out of raw OCR text, if present."""
    candidates = [_clean_mrz_line(l) for l in ocr_text.splitlines() if l.strip()]
    mrz_lines = [l for l in candidates if len(l) >= 30 and l.count("<") >= 3]
    # Pad/truncate to 44 chars, keep the last two plausible MRZ lines in order
    mrz_lines = mrz_lines[-2:]
    fixed = []
    for l in mrz_lines:
        if len(l) < 44:
            l = l + "<" * (44 - len(l))
        else:
            l = l[:44]
        fixed.append(l)
    return fixed


def parse_td3_mrz(ocr_text: str) -> MRZResult:
    lines = find_mrz_lines(ocr_text)
    if len(lines) != 2:
        return MRZResult(valid_format=False, errors=["Could not locate two 44-character MRZ lines in OCR output."])

    line1, line2 = lines
    result = MRZResult(valid_format=True, line1=line1, line2=line2)

    try:
        result.document_type = line1[0:2].replace("<", "")
        result.issuing_country = line1[2:5]
        names_field = line1[5:44]
        surname, _, given = names_field.partition("<<")
        result.surname = surname.replace("<", " ").strip()
        result.given_names = given.replace("<", " ").strip()

        result.passport_number = line2[0:9]
        pn_check = line2[9]
        result.nationality = line2[10:13]
        dob = line2[13:19]
        dob_check = line2[19]
        result.sex = line2[20]
        expiry = line2[21:27]
        expiry_check = line2[27]
        personal_number = line2[28:42]
        pn2_check = line2[42]
        composite_check = line2[43]

        result.date_of_birth = dob
        result.date_of_expiry = expiry

        def add_check(name, data, found):
            expected = compute_check_digit(data)
            passed = found.isdigit() and int(found) == expected
            result.checks.append(MRZCheck(name, data, expected, found, passed))

        add_check("passport_number", result.passport_number, pn_check)
        add_check("date_of_birth", dob, dob_check)
        add_check("date_of_expiry", expiry, expiry_check)
        if personal_number.strip("<"):
            add_check("personal_number", personal_number, pn2_check)

        composite_data = (
            result.passport_number + pn_check +
            dob + dob_check +
            expiry + expiry_check +
            personal_number + pn2_check
        )
        add_check("composite", composite_data, composite_check)

    except Exception as e:
        result.errors.append(f"MRZ parse error: {e}")
        result.valid_format = False

    return result
