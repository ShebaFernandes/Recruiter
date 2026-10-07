import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from docx import Document
from pypdf import PdfReader

KNOWN_SKILLS = [
    "Python",
    "Django",
    "Java",
    "Spring Boot",
    "Kafka",
    "Go",
    "Node.js",
    "React",
    "TypeScript",
    "AWS",
    "Kubernetes",
    "PostgreSQL",
    "Redis",
    "Microservices",
]
LOCATIONS = ["Bengaluru", "Pune", "Hyderabad", "Chennai", "Mumbai", "Delhi", "Gurgaon", "Remote"]
SECTION_HEADINGS = {
    "experience",
    "work experience",
    "professional experience",
    "employment history",
    "work history",
    "education",
    "academic background",
    "qualifications",
    "skills",
    "technical skills",
    "projects",
    "certifications",
    "summary",
    "professional summary",
}
EXPERIENCE_HEADINGS = {
    "experience",
    "work experience",
    "professional experience",
    "employment history",
    "work history",
}
EDUCATION_HEADINGS = {"education", "academic background", "qualifications"}
MONTH_PATTERN = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)"
)
DATE_VALUE_PATTERN = rf"(?:{MONTH_PATTERN}\.?\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}})"
DATE_RANGE_PATTERN = re.compile(
    rf"(?P<start>{DATE_VALUE_PATTERN})\s*(?:-|–|—|to)\s*"
    rf"(?P<end>present|current|now|{DATE_VALUE_PATTERN})",
    re.IGNORECASE,
)


def extract_text(file_obj, filename):
    extension = Path(filename).suffix.lower()
    file_obj.seek(0)
    if extension == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(file_obj).pages)
    if extension == ".docx":
        return "\n".join(paragraph.text for paragraph in Document(file_obj).paragraphs)
    return file_obj.read().decode("utf-8", errors="ignore")


def _value_after_label(text, label):
    match = re.search(rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+)$", text)
    return match.group(1).strip() if match else ""


def _profile_url(text, host):
    match = re.search(rf"(?i)(?:https?://)?(?:www\.)?{re.escape(host)}/[^\s,;]+", text)
    if not match:
        return ""
    value = match.group(0).rstrip(".)],")
    return value if value.lower().startswith(("http://", "https://")) else f"https://{value}"


def _heading(value):
    return re.sub(r"[^a-z ]", "", value.lower()).strip()


def _section_lines(lines, headings):
    for index, line in enumerate(lines):
        if _heading(line) not in headings:
            continue
        section = []
        for value in lines[index + 1 :]:
            if _heading(value) in SECTION_HEADINGS:
                break
            section.append(value)
        return section
    return []


def _resume_date(value):
    normalized = re.sub(r"(?i)^sept", "Sep", value.strip().replace(".", ""))
    for date_format in ("%b %Y", "%B %Y", "%m/%Y", "%Y"):
        try:
            return datetime.strptime(normalized, date_format).date().replace(day=1).isoformat()
        except ValueError:
            continue
    return None


def _looks_like_role(value):
    return bool(
        re.search(
            r"(?i)\b(engineer|developer|manager|designer|analyst|consultant|architect|"
            r"lead|specialist|intern|director|officer|scientist|administrator|associate)\b",
            value,
        )
    )


def _role_and_company(values):
    cleaned = [value.strip(" |•-–—") for value in values if value.strip(" |•-–—")]
    if not cleaned:
        return "", ""
    at_match = re.match(r"(?i)^(.+?)\s+(?:at|@)\s+(.+)$", cleaned[0])
    if at_match:
        return at_match.group(1).strip(), at_match.group(2).strip()
    if len(cleaned) < 2:
        return "", ""
    first, second = cleaned[-2:]
    if _looks_like_role(second) and not _looks_like_role(first):
        return second, first
    return first, second


def _standard_experiences(lines):
    section = _section_lines(lines, EXPERIENCE_HEADINGS)
    experiences = []
    for index, line in enumerate(section):
        date_match = DATE_RANGE_PATTERN.search(line)
        if not date_match:
            continue
        prefix = line[: date_match.start()].strip(" |•-–—")
        if prefix:
            context = [part for part in re.split(r"\s*\|\s*", prefix) if part]
        else:
            context = section[max(0, index - 2) : index]
        role, company = _role_and_company(context)
        start_date = _resume_date(date_match.group("start"))
        end_value = date_match.group("end")
        end_date = (
            None
            if end_value.lower() in {"present", "current", "now"}
            else _resume_date(end_value)
        )
        if not role or not company or not start_date:
            continue
        suffix = line[date_match.end() :].strip(" |•-–—")
        description = suffix
        if not description and index + 1 < len(section):
            candidate = section[index + 1].strip(" |•-–—")
            if (
                candidate
                and not DATE_RANGE_PATTERN.search(candidate)
                and not _looks_like_role(candidate)
            ):
                description = candidate
        experiences.append(
            {
                "role": role[:180],
                "company": company[:180],
                "start_date": start_date,
                "end_date": end_date,
                "description": description[:1000],
            }
        )
    return experiences


def _education_rows(text, lines):
    rows = [
        value.strip() for value in re.findall(r"(?im)^\s*Education\s*:\s*(.+)$", text)
    ]
    degree_words = re.compile(
        r"(?i)\b(b\.?tech|bachelor|master|mba|m\.?tech|degree|diploma|ph\.?d)\b"
    )
    institution_words = re.compile(r"(?i)\b(university|college|institute|school|academy)\b")
    for raw_value in _section_lines(lines, EDUCATION_HEADINGS):
        value = raw_value.strip(" |•-–—")
        if not value or len(value) > 240:
            continue
        if rows and DATE_RANGE_PATTERN.fullmatch(value):
            rows[-1] = f"{rows[-1]} · {value}"
        elif rows and (
            (degree_words.search(rows[-1]) and institution_words.search(value))
            or (institution_words.search(rows[-1]) and degree_words.search(value))
        ):
            rows[-1] = f"{rows[-1]} · {value}"
        elif value not in rows:
            rows.append(value)
    return list(dict.fromkeys(rows))[:8]


def parse_resume(file_obj, filename):
    text = extract_text(file_obj, filename)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    email_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    phone_match = re.search(r"(?:\+?91[-\s]?)?[6-9]\d{9}", text)
    linkedin = _profile_url(text, "linkedin.com")
    github = _profile_url(text, "github.com")
    years_match = re.search(r"(?i)(\d+(?:\.\d+)?)\s*(?:years?|yrs?)", text)
    skills_line = _value_after_label(text, "Skills")
    skills = [skill for skill in KNOWN_SKILLS if re.search(rf"(?i)\b{re.escape(skill)}\b", text)]
    if skills_line:
        skills = list(
            dict.fromkeys(skills + [s.strip() for s in skills_line.split(",") if s.strip()])
        )
    location = next((city for city in LOCATIONS if re.search(rf"(?i)\b{city}\b", text)), "")
    name = _value_after_label(text, "Name") or (lines[0] if lines else "")
    headline = _value_after_label(text, "Role") or _value_after_label(text, "Title")
    company = _value_after_label(text, "Company")
    experience_rows = []
    for match in re.finditer(
        r"(?im)^\s*(?:Experience|Work)\s*:\s*([^|\n]+)\|([^|\n]+)\|"
        r"(\d{4}-\d{2}-\d{2})\|([^|\n]+)(?:\|([^\n]+))?$",
        text,
    ):
        end_value = match.group(4).strip()
        experience_rows.append(
            {
                "role": match.group(1).strip()[:180],
                "company": match.group(2).strip()[:180],
                "start_date": match.group(3),
                "end_date": None if end_value.lower() in {"present", "current"} else end_value,
                "description": (match.group(5) or "").strip(),
            }
        )
    for item in _standard_experiences(lines):
        key = (item["role"].lower(), item["company"].lower(), item["start_date"])
        existing = {
            (row["role"].lower(), row["company"].lower(), row["start_date"])
            for row in experience_rows
        }
        if key not in existing:
            experience_rows.append(item)
    education_rows = _education_rows(text, lines)
    if experience_rows and (not headline or not company):
        current = max(experience_rows, key=lambda item: item["start_date"])
        headline = headline or current["role"]
        company = company or current["company"]
    notice_match = re.search(r"(?im)^\s*Notice(?: period)?\s*:\s*(\d+)\s*days?", text)
    current_salary = re.search(r"(?im)^\s*Current (?:salary|CTC)\s*:\s*(\d+(?:\.\d+)?)", text)
    expected_salary = re.search(r"(?im)^\s*Expected (?:salary|CTC)\s*:\s*(\d+(?:\.\d+)?)", text)
    work_preferences = []
    preference_patterns = [
        ("Flexible", r"\bflexible\b"),
        ("Remote", r"\bremote\b"),
        ("Hybrid", r"\bhybrid\b"),
        ("On-site", r"\b(?:on[ -]?site|office-based)\b"),
    ]
    for preference, pattern in preference_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            work_preferences.append(preference)
    return {
        "full_name": name[:180],
        "headline": headline[:240],
        "current_company": company[:180],
        "email": email_match.group(0) if email_match else "",
        "phone": phone_match.group(0) if phone_match else "",
        "location": location,
        "total_experience": float(years_match.group(1)) if years_match else 0,
        "linkedin_url": linkedin,
        "github_url": github,
        "work_preferences": work_preferences,
        "skills": skills,
        "education": education_rows,
        "work_experiences": experience_rows,
        "notice_period_days": int(notice_match.group(1)) if notice_match else None,
        "current_salary_lpa": float(current_salary.group(1)) if current_salary else None,
        "expected_salary_lpa": float(expected_salary.group(1)) if expected_salary else None,
        "summary": _value_after_label(text, "Summary"),
        "raw_text": text[:15000],
    }


def parse_search_query(query):
    lower = query.lower()
    years = re.search(r"(\d+(?:\.\d+)?)\s*(?:\+?\s*years?|yrs?)", lower)
    years_range = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:to|-|–)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)", lower
    )
    location = next((city for city in LOCATIONS if city.lower() in lower), None)
    skills = [skill for skill in KNOWN_SKILLS if skill.lower() in lower]
    role_match = re.search(
        r"(?i)\b(backend engineer|frontend engineer|full.?stack engineer|software engineer|"
        r"platform engineer|data engineer|product manager|designer|engineer)\b",
        query,
    )
    remote = "remote" in lower or "work from home" in lower
    work_preferences = []
    for label, pattern in (
        ("Remote", r"\bremote\b|work from home"),
        ("Hybrid", r"\bhybrid\b"),
        ("On-site", r"\b(?:on[ -]?site|office-based)\b"),
        ("Flexible", r"\bflexible\b"),
    ):
        if re.search(pattern, lower):
            work_preferences.append(label)
    employment_type = next(
        (
            label
            for label, pattern in (
                ("Contract", r"\bcontract(?:or)?\b"),
                ("Part-time", r"\bpart[ -]?time\b"),
                ("Full-time", r"\bfull[ -]?time\b"),
            )
            if re.search(pattern, lower)
        ),
        "",
    )
    criteria = {
        "role": role_match.group(1).title() if role_match else "",
        "skills": skills,
        "min_experience": float(years_range.group(1))
        if years_range
        else (float(years.group(1)) if years else None),
        "max_experience": float(years_range.group(2)) if years_range else None,
        "location": location,
        "remote_ok": remote,
        "notice_period_days": None,
        "max_salary_lpa": None,
        "employment_type": employment_type,
        "work_preferences": work_preferences,
    }
    notice = re.search(r"(?:within|under|up to)\s*(\d+)\s*days?", lower)
    if notice:
        criteria["notice_period_days"] = int(notice.group(1))
    salary = re.search(r"(?:under|up to|max(?:imum)?)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?)", lower)
    if salary:
        criteria["max_salary_lpa"] = float(salary.group(1))
    question = next_search_question(criteria)
    return criteria, question


def apply_search_answer(criteria, answer):
    lower = answer.lower()
    city = next((city for city in LOCATIONS if city.lower() in lower), None)
    if "remote" in lower or "anywhere" in lower:
        criteria["remote_ok"] = True
    if city and city != "Remote":
        criteria["location"] = city
    if not criteria.get("role"):
        role_match = re.search(
            r"(?i)((?:backend|frontend|full.?stack|platform|data|software)\s+engineer|"
            r"product manager|designer)",
            answer,
        )
        if role_match:
            criteria["role"] = role_match.group(0).title()
    for skill in KNOWN_SKILLS:
        if skill.lower() in lower and skill not in criteria.get("skills", []):
            criteria.setdefault("skills", []).append(skill)
    return criteria


def next_search_question(criteria):
    if not criteria.get("role"):
        return "Which role or job title should these candidates match?"
    if not criteria.get("location") and not criteria.get("remote_ok"):
        return "Do you have a preferred location, or are remote candidates acceptable?"
    return ""


def calculate_match(candidate, criteria):
    score = Decimal("55")
    reasons = []
    role = criteria.get("role", "").replace(" Engineer", "").lower()
    if role and role in candidate.headline.lower():
        score += 15
        reasons.append(f"Current role aligns with {criteria['role']}")
    requested_skills = criteria.get("skills") or []
    candidate_skills = {skill.lower() for skill in candidate.skills}
    matched = [skill for skill in requested_skills if skill.lower() in candidate_skills]
    if requested_skills:
        score += Decimal(str(20 * len(matched) / len(requested_skills)))
    if matched:
        reasons.append(f"Matches {', '.join(matched)}")
    minimum = criteria.get("min_experience")
    maximum = criteria.get("max_experience")
    if minimum is not None and float(candidate.total_experience) >= float(minimum):
        score += 7
        reasons.append("Experience meets the requested level")
    if maximum is not None and float(candidate.total_experience) > float(maximum):
        score -= 8
    location = criteria.get("location")
    if location and candidate.location.lower() == location.lower():
        score += 8
        reasons.append(f"Based in {candidate.location}")
    elif criteria.get("remote_ok") and candidate.location.lower() == "remote":
        score += 8
        reasons.append("Available remotely")
    return max(0, min(99, int(score))), reasons or ["Relevant adjacent experience"]


def years_between(start, end=None):
    end = end or date.today()
    return round((end - start).days / 365.25, 1)


def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()
