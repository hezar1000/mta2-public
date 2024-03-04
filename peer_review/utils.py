from .models import *


class ReviewUtils:
    @staticmethod
    def get_file_links(rubric_question, review_assignment):

        file_links = ""

        review_content = rubric_question.reviewcontent_set.get(
            review_assignment__id=review_assignment.id
        )
        files = review_content.reviewcontentfile_set.all()
        for file_obj in files:
            file_link = '<a href="%s" download>%s</a>&#13;&#10;' % (
                file_obj.attachment.url,
                file_obj.attachment.name,
            )
            file_links += file_link

        return file_links

    @staticmethod
    def get_numeral_value(d, key, default):
        val = d.get(key)
        if isinstance(val, str) and val.isnumeric():
            return int(val)
        else:
            return default
