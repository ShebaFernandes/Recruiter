import re
import shutil
import subprocess
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.conf import settings
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
RESUME_RAW_TEXT_LIMIT = 50_000
OCR_REQUIRED_MARKER = '[LOCAL_OCR_REQUIRED_PAGE]'
OCR_USED_MARKER = '[LOCAL_OCR_TEXT_PAGE]'
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
    "career history",
    "employment experience",
    "career experience",
    "industry experience",
    "relevant experience",
    "selected experience",
    "professional background",
    "professional journey",
    "internship experience",
    "internships",
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
    "career history",
    "employment experience",
    "career experience",
    "industry experience",
    "relevant experience",
    "selected experience",
    "professional background",
    "professional journey",
    "internship experience",
    "internships",
}
EDUCATION_HEADINGS = {"education", "academic background", "qualifications"}
MONTH_PATTERN = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)"
)
DATE_VALUE_PATTERN = (
    rf"(?:{MONTH_PATTERN}\.?\s+\d{{4}}|\d{{1,2}}[/-]\d{{4}}|"
    rf"\d{{4}}[/-]\d{{1,2}}|\d{{4}})"
)
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


def _append_right_column_sections(text):
    """Add a reading-order view when a PDF places career history in a right column."""
    lines = text.splitlines()
    additions = []
    heading_pattern = re.compile(
        r"(?i)\b(professional experience|employment history|work experience|work history|"
        r"career experience|industry experience|relevant experience|selected experience|"
        r"professional background|"
        r"professional journey|internship experience|internships)\b"
    )
    for index, line in enumerate(lines):
        match = heading_pattern.search(line)
        if not match or not line[: match.start()].strip():
            continue
        column = match.start()
        section = [match.group(1)]
        for following in lines[index + 1 :]:
            value = following[column:].strip() if len(following) > column else ""
            if not value:
                continue
            heading, _ = _heading_and_tail(value)
            if heading and heading not in EXPERIENCE_HEADINGS:
                break
            section.append(value)
        if len(section) > 1:
            additions.extend(section)
    return text + ("\n" + "\n".join(additions) if additions else "")


def _local_ocr_pdf(file_obj, pages):
    """OCR only textless pages, locally and within fixed resource bounds."""
    if (not settings.configured or not settings.RESUME_LOCAL_OCR_ENABLED
            or len(pages) > settings.RESUME_LOCAL_OCR_MAX_PAGES):
        return {}
    if not shutil.which('pdftoppm') or not shutil.which('tesseract'):
        return {}
    file_obj.seek(0, 2)
    size = file_obj.tell()
    if size > settings.RESUME_LOCAL_OCR_MAX_FILE_BYTES:
        return {}
    file_obj.seek(0)
    with tempfile.TemporaryDirectory(prefix='enter-resume-ocr-') as scratch:
        source = Path(scratch) / 'source.pdf'
        source.write_bytes(file_obj.read(settings.RESUME_LOCAL_OCR_MAX_FILE_BYTES + 1))
        if source.stat().st_size != size:
            return {}
        results = {}
        for page_index in pages:
            target = Path(scratch) / f'page-{page_index + 1}'
            try:
                subprocess.run([
                    'pdftoppm', '-f', str(page_index + 1), '-l', str(page_index + 1),
                    '-scale-to', '1800', '-png', '-singlefile', str(source), str(target),
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=settings.RESUME_LOCAL_OCR_TIMEOUT_SECONDS)
                image = target.with_suffix('.png')
                if not image.is_file() or image.stat().st_size > 12_000_000:
                    continue
                output = subprocess.run([
                    'tesseract', str(image), 'stdout', '-l', 'eng', '--psm', '6',
                ], check=True, capture_output=True,
                    timeout=settings.RESUME_LOCAL_OCR_TIMEOUT_SECONDS)
            except (OSError, subprocess.SubprocessError):
                continue
            text = output.stdout[:12_000].decode('utf-8', errors='ignore').strip()
            if text:
                results[page_index] = text
        return results


def extract_text(file_obj, filename):
    extension = Path(filename).suffix.lower()
    file_obj.seek(0)
    if extension == ".pdf":
        reader = PdfReader(file_obj)
        if len(reader.pages) > 100:
            raise ValueError("Resume exceeds the safe page limit.")
        parts, characters, textless_pages = [], 0, []
        for index, page in enumerate(reader.pages):
            # Layout mode keeps columns separated and makes employer/title/date
            # associations materially less ambiguous. Some older or malformed
            # PDFs cannot use it, so retain the bounded plain-text fallback.
            try:
                text = page.extract_text(
                    extraction_mode="layout", layout_mode_space_vertically=False
                ) or ""
            except (TypeError, ValueError, KeyError, IndexError):
                text = page.extract_text() or ""
            if len(re.sub(r'\W', '', text)) < 40:
                textless_pages.append(index)
            text = _append_right_column_sections(text)
            characters += len(text)
            if characters > 500_000:
                raise ValueError("Resume exceeds the safe text limit.")
            parts.append(text)
        if textless_pages:
            recognized = _local_ocr_pdf(file_obj, textless_pages)
            for index in textless_pages:
                parts[index] = (
                    recognized[index] + '\n' + OCR_USED_MARKER if index in recognized
                    else parts[index] + '\n' + OCR_REQUIRED_MARKER
                )
        return "\n".join(parts)
    if extension == ".docx":
        document = read_docx(file_obj)
        lines = []
        for block in document.iter_inner_content():
            if hasattr(block, "text"):
                lines.extend(block.text.splitlines())
                continue
            for row in block.rows:
                cells = [" ".join(cell.text.split()) for cell in row.cells]
                populated = [cell for cell in cells if cell]
                if populated:
                    lines.append(" | ".join(populated))
        return "\n".join(lines)
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
    return " ".join(re.sub(r"[^a-z ]", " ", value.lower()).split())


def _heading_and_tail(value):
    """Return an exact section heading plus content sharing its table/PDF row."""
    stripped = value.strip()
    for heading in sorted(SECTION_HEADINGS, key=len, reverse=True):
        match = re.match(rf"(?i)^\s*{re.escape(heading)}\s*(?:[:|]\s*(.*))?$", stripped)
        if match:
            return heading, (match.group(1) or "").strip()
    return "", ""


def _section_lines(lines, headings):
    for index, line in enumerate(lines):
        heading, tail = _heading_and_tail(line)
        if heading not in headings:
            continue
        section = [tail] if tail else []
        for value in lines[index + 1 :]:
            next_heading, _ = _heading_and_tail(value)
            if next_heading:
                break
            section.append(value)
        return section
    return []


def _resume_date(value):
    # Normalize the optional four-letter abbreviation without corrupting
    # the full month name ("September" previously became "Sepember").
    normalized = re.sub(r"(?i)^sept(?=\s)", "Sep", value.strip().replace(".", ""))
    for date_format in ("%b %Y", "%B %Y", "%m/%Y", "%m-%Y", "%Y-%m", "%Y/%m", "%Y"):
        try:
            return datetime.strptime(normalized, date_format).date().replace(day=1).isoformat()
        except ValueError:
            continue
    return None


def _looks_like_role(value):
    return bool(
        re.search(
            r"(?i)\b(engineer|developer|manager|designer|analyst|consultant|architect|"
            r"lead|specialist|intern|director|officer|scientist|researcher|writer|"
            r"administrator|associate|advisor)\b",
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


def _layout_header_role(line):
    """Read a title followed by a separate, widely spaced PDF location column."""
    parts = re.split(r"\s{3,}", line.strip())
    if len(parts) != 2 or len(parts[1]) > 80 or DATE_RANGE_PATTERN.search(parts[1]):
        return ""
    if _looks_like_role(parts[1]):
        return ""
    return _concise_role(parts[0])


def _plausible_employer_line(value):
    value = value.strip(' |•-–—')
    if (not value or len(value) > 180 or DATE_RANGE_PATTERN.search(value)
            or value.endswith(('.', '!', ':'))):
        return False
    if not _looks_like_role(value):
        return True
    # Company names can contain title words, such as "Developer Tools".
    return bool(re.search(
        r'(?i)\b(?:labs?|systems?|works?|tools?|technolog(?:y|ies)|'
        r'solutions?|group|studio|analytics|software|services?)\b', value
    ))


def _range_dates(match):
    start_value, end_value = match.group("start", "end")
    if re.fullmatch(r"\d{2}", end_value):
        end_value = start_value[-4:-2] + end_value
    return _resume_date(start_value), (
        None if end_value.lower() in {"present", "current", "now"} else _resume_date(end_value)
    )


def _table_date_range(line):
    """Turn separate DOCX table date cells into the same explicit range grammar."""
    cells = [cell.strip() for cell in line.split("|")]
    if len(cells) < 4:
        return line
    for index in range(1, len(cells) - 1):
        start, end = cells[index], cells[index + 1]
        if re.fullmatch(DATE_VALUE_PATTERN, start, re.I) and re.fullmatch(
            rf"(?:present|current|now|{DATE_VALUE_PATTERN}|\d{{2}})", end, re.I
        ):
            return " | ".join(cells[:index] + [f"{start} - {end}"] + cells[index + 2 :])
    return line


def _employment_details(value, role=""):
    employment_type = next(
        (
            label
            for label, pattern in (
                ("Full-time", r"\bfull[ -]?time\b"),
                ("Part-time", r"\bpart[ -]?time\b"),
                ("Contract", r"\bcontract(?:or)?\b"),
                ("Internship", r"\binternship\b"),
                ("Freelance", r"\bfreelance\b"),
            )
            if re.search(pattern, value, re.I)
        ),
        "",
    )
    if not employment_type and any(
        re.search(r"\b(?:intern|internship)\s*\)?\s*(?:$|[-–—:])", title.strip(), re.I)
        for title in re.split(r"[|/;]", role)
    ):
        employment_type = "Internship"
    location = ""
    location_match = re.search(
        r"(?i)(?:\||·)\s*([^|·]{2,80}(?:,\s*[A-Za-z]{2,40})?)\s*$", value
    )
    if location_match and not DATE_RANGE_PATTERN.search(location_match.group(1)):
        candidate = location_match.group(1).strip()
        if any(re.search(rf"(?i)\b{re.escape(place)}\b", candidate) for place in LOCATIONS) or (
            "," in candidate and len(candidate.split()) <= 5
        ):
            location = candidate
    return employment_type, location


def _standard_experiences(lines, original_section=None):
    if original_section is None:
        original_section = _section_lines(lines, EXPERIENCE_HEADINGS)
    section = [_table_date_range(line) for line in original_section]
    # Separate employer/title/date lines belong to the next role, never to the
    # previous role's achievements. Only explicit adjacent dated headers qualify.
    header_starts = set()
    for date_index in range(2, len(section)):
        if DATE_RANGE_PATTERN.fullmatch(section[date_index]):
            next_role, next_company = _role_and_company(section[date_index - 2 : date_index])
            if _concise_role(next_role) and next_company:
                header_starts.add(date_index - 2)
    experiences = []
    employer = ""
    for index, line in enumerate(section):
        if PIPE_EXPERIENCE_PATTERN.fullmatch(original_section[index]):
            continue  # Already parsed as one complete, structured Work row.
        matches = list(DATE_RANGE_PATTERN.finditer(line))
        if not matches:
            continue
        for number, match in enumerate(matches):
            prefix = line[matches[number - 1].end() if number else 0 : match.start()]
            layout_gap = len(prefix) - len(prefix.rstrip())
            prefix = prefix.lstrip(" |•·-–—)").rstrip(" |•·-–—(")
            start_date, end_date = _range_dates(match)
            description_start = index + 1
            role, company = "", ""
            if "|" in prefix or re.search(r"\s(?:at|@)\s", prefix, re.I):
                role, company = _role_and_company(prefix.split("|"))
                role = _concise_role(role)
                if not role:
                    parts = [part.strip() for part in prefix.split('|') if part.strip()]
                    if len(parts) == 1 and _concise_role(parts[0]):
                        role = _concise_role(parts[0])
                        company = employer
                        if index > 0:
                            previous = section[index - 1].strip()
                            if _plausible_employer_line(previous):
                                company = previous
                    elif len(parts) == 1:
                        employer = parts[0]
            elif prefix and layout_gap >= 3 and index + 1 < len(section):
                role = _layout_header_role(section[index + 1])
                if role:
                    company = prefix
                    description_start = index + 2
            elif prefix and _concise_role(prefix):
                role = _concise_role(prefix)
                company = employer
                # Some PDF exporters put an undated employer on one line and the
                # role plus date range on the next. Keep that explicit adjacency;
                # never infer an employer from a description farther away.
                if index > 0:
                    previous = section[index - 1].strip(" |•-–—")
                    if _plausible_employer_line(previous):
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
                        role = _concise_role(next_line.split("|")[0]) or _layout_header_role(
                            next_line
                        )
                        if role:
                            description_start = index + 2
            else:
                role, company = _role_and_company(section[max(0, index - 2) : index])
                role = _concise_role(role)
                # A promotion often follows an achievement or an undated
                # progression note. Those lines are not new employers.
                preceding = section[index - 2].strip() if index >= 2 else ''
                if employer and (
                    preceding.endswith(('.', '!', ':'))
                    or re.search(r'(?i)\b(?:progression|same employer|promotion)\b', preceding)
                ):
                    company = employer
            if not role or not company or not start_date:
                continue
            role = re.sub(
                r'(?i)\s*\((?:contract|contractor|full[ -]?time|part[ -]?time|internship)\)$',
                '', role,
            ).strip()
            employer = company
            description = []
            for following_index in range(description_start, len(section)):
                following = section[following_index]
                if following_index in header_starts or DATE_RANGE_PATTERN.search(following):
                    break
                if re.match(r"(?i)^.+?\s+(?:at|@)\s+.+$", following) and _concise_role(following):
                    break
                description.append(following.strip(" |•-–—"))
            # Some documents put the role and its work details on the same undated line.
            if description_start == index + 2:
                role_line = section[index + 1].split("|", 1)[0].strip()
                remainder = "" if _layout_header_role(role_line) else role_line[len(role) :].strip(
                    " |•-–—."
                )
                if remainder:
                    description.insert(0, remainder)
            evidence_lines = [line]
            if not prefix:
                evidence_lines = section[max(0, index - 2) : index + 1]
            if description_start == index + 2:
                evidence_lines.append(section[index + 1])
            evidence_lines.extend(description)
            employment_type, role_location = _employment_details(
                " | ".join(evidence_lines[:2]), role
            )
            experiences.append(
                {
                    "role": role,
                    "company": company[:180],
                    "start_date": start_date,
                    "end_date": end_date,
                    "is_current": match.group("end").lower() in {"present", "current", "now"},
                    "date_label": match.group(0),
                    "employment_type": employment_type,
                    "location": role_location,
                    "description": " ".join(description)[:1000],
                    "source_evidence": "\n".join(evidence_lines)[:2000],
                    "confidence_status": "supported",
                }
            )
    return experiences


def _unheaded_employment_lines(lines):
    """Find an explicit dated-role block when a resume has no history heading.

    These observations can add supported roles, but never prove that the whole
    career history was enumerated for archival.
    """
    start = 0
    for index, line in enumerate(lines[:12]):
        if re.match(r'(?i)^(?:name|title|summary|skills|location|email|phone)\s*:', line):
            start = index + 1
    end = len(lines)
    for index in range(start, len(lines)):
        heading, _ = _heading_and_tail(lines[index])
        if heading in {
            'projects', 'education', 'certifications', 'publications talks  recognition'
        }:
            end = index
            break
    return lines[start:end]


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
        if rows and value.casefold() == rows[-1].casefold():
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


PIPE_EXPERIENCE_PATTERN = re.compile(
    r"^\s*(?:Experience|Work)\s*:\s*([^|\n]+)\|([^|\n]+)\|"
    r"(\d{4}-\d{2}-\d{2})\|([^|\n]+)(?:\|([^\n]+))?$",
    re.IGNORECASE | re.MULTILINE,
)


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
    name = _value_after_label(text, "Name") or (
        lines[0] if lines and lines[0] != OCR_REQUIRED_MARKER else ""
    )
    headline = _concise_role(_value_after_label(text, "Role") or _value_after_label(text, "Title"))
    company = _value_after_label(text, "Company")
    experience_rows = []
    for match in PIPE_EXPERIENCE_PATTERN.finditer(text):
        end_value = match.group(4).strip()
        experience_rows.append(
            {
                "role": match.group(1).strip()[:180],
                "company": match.group(2).strip()[:180],
                "start_date": match.group(3),
                "end_date": None if end_value.lower() in {"present", "current"} else end_value,
                "is_current": end_value.lower() in {"present", "current", "now"},
                "date_label": f"{match.group(3)} — {end_value}",
                "employment_type": "",
                "location": "",
                "description": (match.group(5) or "").strip(),
                "source_evidence": match.group(0)[:2000],
                "confidence_status": "supported",
            }
        )
    section = _section_lines(lines, EXPERIENCE_HEADINGS)
    employment_lines = section or _unheaded_employment_lines(lines)
    for item in _standard_experiences(lines, employment_lines):
        key = (item["role"].lower(), item["company"].lower(), item["start_date"])
        existing = {
            (row["role"].lower(), row["company"].lower(), row["start_date"])
            for row in experience_rows
        }
        if key not in existing:
            experience_rows.append(item)
    unknown_start = re.compile(
        rf'(?i)^(?P<title>[^|]+)\|\s*start date (?:not stated|unknown|unavailable)'
        rf'\s*[-–—]\s*(?P<end>{DATE_VALUE_PATTERN})\s*$'
    )
    for index, line in enumerate(employment_lines):
        match = unknown_start.fullmatch(line)
        if not match or index == 0 or not _plausible_employer_line(employment_lines[index - 1]):
            continue
        role = _concise_role(match.group('title'))
        end = _resume_date(match.group('end'))
        if role and end:
            experience_rows.append({
                'role': role, 'company': employment_lines[index - 1].strip(),
                'start_date': None, 'end_date': end, 'is_current': False,
                'date_label': f'Start date not stated — {match.group("end")}',
                'employment_type': '', 'location': '', 'description': '',
                'source_evidence': '\n'.join(employment_lines[index - 1:index + 1])[:2000],
                'confidence_status': 'partial',
            })
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
                        "is_current": False,
                        "date_label": "Dates not specified",
                        "employment_type": _employment_details(line)[0],
                        "location": _employment_details(line)[1],
                        "description": "",
                        "source_evidence": line[:2000],
                        "confidence_status": "partial",
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
    normalized_headings = {_heading(line) for line in lines}
    explicit_no_employment = bool(
        re.search(
            r"(?i)\b(?:fresher|no (?:professional |work |employment )?experience|"
            r"seeking (?:a )?first (?:job|role)|never (?:been )?employed)\b",
            text,
        )
    )
    section = _section_lines(lines, EXPERIENCE_HEADINGS)
    employment_headings = sum(
        _heading_and_tail(line)[0] in EXPERIENCE_HEADINGS for line in lines
    )
    selective_headings = {
        'selected experience', 'relevant experience',
        'internship experience', 'internships',
    }
    selective_section = any(
        _heading_and_tail(line)[0] in selective_headings for line in lines
    )
    # Archiving needs an independently enumerable, bounded work-history section.
    # A successful model response or the parser's ordinary reliability heuristic
    # cannot prove that a free-form section contains every role.
    pipe_complete = bool(
        employment_headings == 1 and not selective_section
        and section
        and len(section) == len(experience_rows)
        and len(list(PIPE_EXPERIENCE_PATTERN.finditer(text))) == len(experience_rows)
        and all(PIPE_EXPERIENCE_PATTERN.fullmatch(line) for line in section)
        and all(row.get("start_date") and (row.get("end_date") or row.get("is_current"))
                for row in experience_rows)
        and not explicit_no_employment
        and len(text) <= RESUME_RAW_TEXT_LIMIT
    )
    # Standard dated layouts can also be counted independently. Every dated
    # header must map to one parsed row, and every line in the bounded section
    # must be covered by that row's verbatim evidence. Unpaired headers, umbrella
    # tenures, truncated evidence, and ambiguous undated lines fail closed.
    dated_lines = [line for line in section if DATE_RANGE_PATTERN.search(_table_date_range(line))]
    evidence = [row.get('source_evidence', '') for row in experience_rows]
    standard_complete = bool(
        employment_headings == 1 and section and not pipe_complete and not selective_section
        and len(dated_lines) == len(experience_rows) > 0
        and all(len(DATE_RANGE_PATTERN.findall(_table_date_range(line))) == 1
                for line in dated_lines)
        and all(row.get('start_date') and (row.get('end_date') or row.get('is_current'))
                for row in experience_rows)
        and all(sum(line in item for item in evidence) == 1 for line in dated_lines)
        and all(any(line.strip(' |•-–—') in item for item in evidence) for line in section)
        and all(
            line in dated_lines
            or line.lstrip().startswith(('-', '•', '*'))
            or line.rstrip().endswith(('.', '!', '?'))
            or any(line.strip(' |•-–—').casefold() in {
                row['company'].casefold(), row['role'].casefold()
            } or _layout_header_role(line) == row['role'] for row in experience_rows)
            for line in section
        )
        and all(not _looks_like_role(line) or any(
            (_layout_header_role(line) or _concise_role(line)) == row.get('role')
            for row in experience_rows
        ) for line in section if line not in dated_lines)
        and not explicit_no_employment and len(text) <= RESUME_RAW_TEXT_LIMIT
    )
    complete_for_archival = ((pipe_complete or standard_complete)
                             and OCR_REQUIRED_MARKER not in text and OCR_USED_MARKER not in text)
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
        "_employment_parse": {
            "reliable": bool(experience_rows) and (
                sum(
                    len(DATE_RANGE_PATTERN.findall(_table_date_range(line)))
                    for line in _section_lines(lines, EXPERIENCE_HEADINGS)
                )
                <= sum(bool(row.get("start_date")) for row in experience_rows)
                + len({row["company"].casefold() for row in experience_rows})
            ),
            "recognized_roles": len(experience_rows),
            "section_detected": bool(normalized_headings & EXPERIENCE_HEADINGS),
            "explicit_no_employment": explicit_no_employment,
            "complete_for_archival": complete_for_archival,
            "ocr_required": OCR_REQUIRED_MARKER in text,
            "ocr_used": OCR_USED_MARKER in text,
            "rule_role_keys": [
                {key: row.get(key) for key in (
                    "company", "role", "start_date", "end_date", "is_current", "date_label"
                )}
                for row in experience_rows
            ] if complete_for_archival else [],
        },
        "notice_period_days": int(notice_match.group(1)) if notice_match else None,
        "current_salary_lpa": float(current_salary.group(1)) if current_salary else None,
        "expected_salary_lpa": float(expected_salary.group(1)) if expected_salary else None,
        "summary": _value_after_label(text, "Summary"),
        "raw_text": text[:RESUME_RAW_TEXT_LIMIT],
        "_text_truncated": len(text) > RESUME_RAW_TEXT_LIMIT,
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
