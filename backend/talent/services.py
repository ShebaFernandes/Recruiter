import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zipfile import BadZipFile, ZipFile

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
RESUME_SKILLS = [
    "Agentic AI",
    "Generative AI",
    "Distributed Systems",
    "Platform Engineering",
    "AI Strategy",
    "LangGraph",
    "Machine Learning",
    *KNOWN_SKILLS,
]
LOCATIONS = [
    "Bengaluru",
    "Pune",
    "Hyderabad",
    "Chennai",
    "Mumbai",
    "Delhi",
    "Gurgaon",
    "Gurugram",
    "Remote",
]
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
    "core expertise",
    "publications talks  recognition",
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
    rf"(?P<end>present|current|now|{DATE_VALUE_PATTERN}|\d{{2}})(?!\d)",
    re.IGNORECASE,
)


def read_docx(file_obj):
    """Bound decompression before reading an uploaded Office document."""
    file_obj.seek(0)
    try:
        with ZipFile(file_obj) as archive:
            entries = archive.infolist()
            if len(entries) > 2048 or sum(entry.file_size for entry in entries) > 40 * 1024 * 1024:
                raise ValueError("Document is too complex to preview safely.")
    except BadZipFile as exc:
        raise ValueError("Unreadable DOCX document.") from exc
    file_obj.seek(0)
    return Document(file_obj)


def extract_text(file_obj, filename):
    extension = Path(filename).suffix.lower()
    file_obj.seek(0)
    if extension == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(file_obj).pages)
    if extension == ".docx":
        document = read_docx(file_obj)
        return "\n".join(
            block.text
            if hasattr(block, "text")
            else "\n".join(" | ".join(cell.text for cell in row.cells) for row in block.rows)
            for block in document.iter_inner_content()
        )
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
            r"lead|specialist|intern|director|officer|scientist|administrator|associate|advisor)\b",
            value,
        )
    )


def _role_and_company(values):
    cleaned = [value.strip(" |•-–—") for value in values if value.strip(" |•-–—")]
    cleaned = [value for value in cleaned if not DATE_RANGE_PATTERN.fullmatch(value)]
    if not cleaned:
        return "", ""
    at_match = re.match(r"(?i)^(.+?)\s+(?:at|@)\s+(.+)$", cleaned[-1])
    if at_match:
        return at_match.group(1).strip(), at_match.group(2).strip()
    if len(cleaned) < 2:
        return "", ""
    first, second = cleaned[-2:]
    if _looks_like_role(second) and not _looks_like_role(first):
        return second, first
    return first, second


def _concise_role(value):
    """Accept a title, never an achievement sentence that happens to mention engineers."""
    value = value.strip(" |•-–—(")
    if re.match(
        r"(?i)^(built|led|architected|shipped|delivered|managed|developed|created|"
        r"responsible|owned|improved|drove|handling|scoring)\b",
        value,
    ):
        return ""
    value = re.split(r"\s[—–]\s(?=(?:C/|built|responsible))", value, flags=re.I)[0]
    value = re.split(r"\.\s", value)[0].strip()
    if len(value) > 125 or len(value.split()) > 18:
        return ""
    if _looks_like_role(value) or re.search(
        r"(?i)\b(AVP|VP|CTO|CEO|head|president|engineering|leadership)\b", value
    ):
        return value
    return ""


def _range_dates(match):
    start_value, end_value = match.group("start", "end")
    if re.fullmatch(r"\d{2}", end_value):
        end_value = start_value[-4:-2] + end_value
    return _resume_date(start_value), (
        None if end_value.lower() in {"present", "current", "now"} else _resume_date(end_value)
    )


def _standard_experiences(lines):
    section = _section_lines(lines, EXPERIENCE_HEADINGS)
    experiences = []
    employer = ""
    for index, line in enumerate(section):
        matches = list(DATE_RANGE_PATTERN.finditer(line))
        if not matches:
            continue
        for number, match in enumerate(matches):
            prefix = line[matches[number - 1].end() if number else 0 : match.start()]
            prefix = prefix.lstrip(" |•·-–—)").rstrip(" |•·-–—(")
            start_date, end_date = _range_dates(match)
            description_start = index + 1
            role, company = "", ""
            if "|" in prefix or re.search(r"\s(?:at|@)\s", prefix, re.I):
                role, company = _role_and_company(prefix.split("|"))
                role = _concise_role(role)
            elif prefix and _concise_role(prefix):
                role = _concise_role(prefix)
                company = employer
                # Some PDF exporters put an undated employer on one line and the
                # role plus date range on the next. Keep that explicit adjacency;
                # never infer an employer from a description farther away.
                if index > 0:
                    previous = section[index - 1].strip(" |•-–—")
                    if (
                        previous
                        and len(previous) <= 180
                        and not DATE_RANGE_PATTERN.search(previous)
                        and not _looks_like_role(previous)
                        and not previous.endswith((".", "!", ":"))
                    ):
                        company = previous
                        employer = previous
            elif prefix:
                # Employer-level tenure can contain several dated promotions. Remember
                # its employer, but do not count the umbrella tenure as another job.
                employer = re.split(r"\s·\s|\s+India['’]s\b", prefix)[0].strip()
                company = employer
                if index + 1 < len(section):
                    next_line = section[index + 1]
                    if not DATE_RANGE_PATTERN.search(next_line):
                        role = _concise_role(next_line.split("|")[0])
                        if role:
                            description_start = index + 2
            else:
                role, company = _role_and_company(section[max(0, index - 2) : index])
                role = _concise_role(role)
            if not role or not company or not start_date:
                continue
            employer = company
            description = []
            for following in section[description_start:]:
                if DATE_RANGE_PATTERN.search(following):
                    break
                if re.match(r"(?i)^.+?\s+(?:at|@)\s+.+$", following) and _concise_role(following):
                    break
                description.append(following.strip(" |•-–—"))
            # Some documents put the role and its work details on the same undated line.
            if description_start == index + 2:
                role_line = section[index + 1].split("|", 1)[0].strip()
                remainder = role_line[len(role) :].strip(" |•-–—.")
                if remainder:
                    description.insert(0, remainder)
            experiences.append(
                {
                    "role": role,
                    "company": company[:180],
                    "start_date": start_date,
                    "end_date": end_date,
                    "date_label": match.group(0),
                    "description": " ".join(description)[:1000],
                }
            )
    return experiences


def _education_rows(text, lines):
    rows = [value.strip() for value in re.findall(r"(?im)^\s*Education\s*:\s*(.+)$", text)]
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
    # A tenure or a metric in a job description is not total career experience.
    years_match = re.search(
        r"(?i)(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?experience", text
    )
    skills_line = _value_after_label(text, "Skills")
    skills = [skill for skill in RESUME_SKILLS if re.search(rf"(?i)\b{re.escape(skill)}\b", text)]
    if skills_line:
        skills = list(
            dict.fromkeys([s.strip() for s in skills_line.split(",") if s.strip()] + skills)
        )
    location = _value_after_label(text, "Location") or next(
        (city for line in lines[:5] for city in LOCATIONS if re.search(rf"(?i)\b{city}\b", line)),
        "",
    )
    name = _value_after_label(text, "Name") or (lines[0] if lines else "")
    headline = _concise_role(_value_after_label(text, "Role") or _value_after_label(text, "Title"))
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
                "date_label": f"{match.group(3)} — {end_value}",
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
    # Preserve explicitly paired undated history without making up employment dates.
    for line in _section_lines(lines, EXPERIENCE_HEADINGS):
        if DATE_RANGE_PATTERN.search(line):
            continue
        match = re.fullmatch(r"(.+?)\s+(?:at|@)\s+(.+)", line, re.IGNORECASE)
        if match and _looks_like_role(match.group(1)):
            role, employer = match.groups()
            if not any(
                row["role"] == role and row["company"] == employer for row in experience_rows
            ):
                experience_rows.append(
                    {
                        "role": role[:180],
                        "company": employer[:180],
                        "start_date": None,
                        "end_date": None,
                        "date_label": "Dates not specified",
                        "description": "",
                    }
                )
    education_rows = _education_rows(text, lines)
    if experience_rows and (not headline or not company):
        current = max(experience_rows, key=lambda item: item["start_date"] or "")
        headline = headline or current["role"]
        company = company or current["company"]
    intervals = []
    for row in sorted(experience_rows, key=lambda item: item["start_date"] or "9999"):
        if not row["start_date"]:
            continue
        start = date.fromisoformat(row["start_date"])
        end = date.fromisoformat(row["end_date"]) if row["end_date"] else date.today()
        if end < start:
            continue
        if intervals and start <= intervals[-1][1]:
            intervals[-1] = (intervals[-1][0], max(intervals[-1][1], end))
        else:
            intervals.append((start, end))
    total_experience = (
        float(years_match.group(1))
        if years_match
        else (
            round(sum((end - start).days for start, end in intervals) / 365.25, 1)
            if intervals
            else None
        )
    )
    standout = _value_after_label(text, "Achievement")
    if not standout:
        # Select an intact evidence sentence, not an invented summary or a cut-off line.
        for line in _section_lines(lines, EXPERIENCE_HEADINGS):
            sentence = re.split(r"(?<=[.!?])\s+", line)[0]
            if (
                40 <= len(sentence) <= 300
                and sentence.endswith((".", "!"))
                and re.match(
                    r"(?i)^(built|shipped|delivered|launched|improved|reduced|"
                    r"architected|\d+\s*→)",
                    sentence,
                )
            ):
                standout = sentence
                break
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
        preference_text = (
            _value_after_label(text, "Work preferences")
            or _value_after_label(text, "Preferred work setup")
        )
        if re.search(pattern, preference_text, re.IGNORECASE):
            work_preferences.append(preference)
    return {
        "full_name": name[:180],
        "headline": headline[:240],
        "current_company": company[:180],
        "email": email_match.group(0) if email_match else "",
        "phone": phone_match.group(0) if phone_match else "",
        "location": location,
        "total_experience": total_experience,
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
        "_text_truncated": len(text) > 15000,
        "standout_signal": standout[:1000],
    }


def _search_role(query):
    role_match = re.search(
        r"(?i)\b(backend engineer|frontend engineer|full.?stack (?:engineer|developer)|"
        r"software engineer|platform engineer|data engineer|product manager|designer|engineer)\b",
        query,
    )
    if role_match:
        start = role_match.start()
        prefix = query[:start].strip()
        if (
            prefix
            and len(prefix.split()) <= 3
            and re.search(r"(?i)\b(ai|ml|genai|senior|staff|lead|founding)\b", prefix)
        ):
            return f"{prefix} {role_match.group(1)}".strip()
        return role_match.group(1)
    candidate = re.split(
        r"(?i)\b(?:with|having)\b|\b\d+(?:\.\d+)?\s*(?:\+?\s*years?|yrs?)\b|"
        r"\b(?:remote|hybrid|on[ -]?site|in\s+[A-Z][\w-]+)\b",
        query,
        maxsplit=1,
    )[0]
    candidate = re.sub(
        r"(?i)^\s*(?:find|show me|looking for|search for|we need|hire|hiring)\s+", "", candidate
    ).strip(" ,.-")
    if candidate and len(candidate.split()) <= 8 and _looks_like_role(candidate):
        return candidate
    return ""


def _display_role(value):
    if not value:
        return ""
    normalized = value.title()
    return re.sub(r"\b(?:Ai|Ml|Genai)\b", lambda match: match.group(0).upper(), normalized)


def parse_search_query(query):
    lower = query.lower()
    years = re.search(r"(\d+(?:\.\d+)?)\s*(?:\+?\s*years?|yrs?)", lower)
    years_range = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:to|-|–)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)", lower
    )
    location = next((city for city in LOCATIONS if city.lower() in lower), None)
    skills = [skill for skill in KNOWN_SKILLS if skill.lower() in lower]
    role = _search_role(query)
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
        "role": _display_role(role),
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
        criteria["role"] = _display_role(_search_role(answer))
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
