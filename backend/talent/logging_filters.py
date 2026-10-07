import logging
import re


class SensitiveValueFilter(logging.Filter):
    """Redact common credential shapes if a dependency includes them in a log message."""

    patterns = (
        re.compile(r"(?i)(authorization\s*[:=]\s*(?:token|bearer)\s+)[^\s,;]+"),
        re.compile(r"(?i)((?:password|secret|access[_-]?key|session|token)\s*[:=]\s*)[^\s,;]+"),
    )

    def filter(self, record):
        message = record.getMessage()
        for pattern in self.patterns:
            message = pattern.sub(r"\1[REDACTED]", message)
        record.msg = message
        record.args = ()
        return True
