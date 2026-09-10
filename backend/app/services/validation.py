"""
Module 2: Document Validation.

Checks the OCR-extracted, MRZ-parsed fields against official document
rules: valid date formats/ranges, expiry status, plausible age vs.
document type, valid sex code, etc. This is separate from tampering
detection -- a document can be internally consistent (passes here) yet
still be a well-forged fake, which is exactly why Module 3 exists too.
"""
import datetime

VALID_SEX_CODES = {"M", "F", "X", "<"}


def _parse_yymmdd(s: str):
    if not s or len(s) != 6 or not s.isdigit():
        return None
    yy, mm, dd = int(s[0:2]), int(s[2:4]), int(s[4:6])
    # ICAO convention: pivot year ~2000; dates > current year+1 assumed 1900s
    current_yy = datetime.date.today().year % 100
    century = 2000 if yy <= current_yy + 1 else 1900
    try:
        return datetime.date(century + yy, mm, dd)
    except ValueError:
        return None


def validate_fields(mrz_result):
    issues = []
    info = {}

    if not mrz_result.valid_format:
        return {"issues": ["MRZ could not be parsed -- cannot run field validation."], "info": info}

    dob = _parse_yymmdd(mrz_result.date_of_birth)
    expiry = _parse_yymmdd(mrz_result.date_of_expiry)
    today = datetime.date.today()

    if dob is None:
        issues.append("Date of birth field is not a valid calendar date.")
    else:
        age = (today - dob).days / 365.25
        info["age_years"] = round(age, 1)
        if dob > today:
            issues.append("Date of birth is in the future.")
        if age > 120:
            issues.append(f"Computed age ({age:.0f}) is implausibly high.")

    if expiry is None:
        issues.append("Expiry date field is not a valid calendar date.")
    else:
        info["expiry_date"] = expiry.isoformat()
        if expiry < today:
            issues.append(f"Document expired on {expiry.isoformat()}.")

    sex = (mrz_result.sex or "").upper()
    if sex not in VALID_SEX_CODES:
        issues.append(f"Sex field '{sex}' is not a recognized MRZ code (expected M/F/X).")

    if not mrz_result.passport_number.strip("<"):
        issues.append("Passport number field is empty.")

    if not re_alpha(mrz_result.issuing_country):
        issues.append(f"Issuing country code '{mrz_result.issuing_country}' is not 3 alphabetic characters.")

    if not re_alpha(mrz_result.nationality):
        issues.append(f"Nationality code '{mrz_result.nationality}' is not 3 alphabetic characters.")

    return {"issues": issues, "info": info}


def re_alpha(code: str) -> bool:
    code = (code or "").replace("<", "")
    return len(code) == 3 and code.isalpha()
