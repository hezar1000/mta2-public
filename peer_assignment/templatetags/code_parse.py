from django import template
from peer_course.models import CourseMember
import re

register = template.Library()


@register.filter
def code_parse(code, author):
    """Parses {$ python code $}"""

    if author is None:
        author = CourseMember()
        author.id = 0

    def parse_match(match):
        try:
            return str(eval(match.group(1), {"author": author}))
        except:
            return "**[PARSING ERROR]**"

    return re.sub(r"{\$\s*([^$]*)\$}", parse_match, code)
