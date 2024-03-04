NONE = "NONE"
MULTIPLECHOICE = "MULT"
TEXT = "TEXT"
FILE = "FILE"

QUESTION_TYPE_CHOICES = (
    (NONE, "--------"),
    (MULTIPLECHOICE, "Multiple Choice"),
    (TEXT, "Text"),
    (FILE, "File"),
)

MAX_CHAR = "MAXCHAR"
MIN_CHAR = "MINCHAR"

VALIDATION_RULE_TYPE_CHOICES = (
    (MAX_CHAR, "Maximum number of characters"),
    (MIN_CHAR, "Minimum number of characters"),
)

PDF = "pdf"
FORM = "form"
TEXT_ASGN = "text"
QUIZ_ASGN = "quiz"

ASSGN_TYPE_CHOICES = (
    (PDF, "PDF"),
    (FORM, "Free Form"),
    (TEXT_ASGN, "Text"),
    (QUIZ_ASGN, "Quiz"),
)
