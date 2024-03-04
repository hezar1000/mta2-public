from .models import Assignment, AssignmentQuestion
from peer_review.choices import FILE


class AssignmentUtils:
    @staticmethod
    def create_empty_question(question_number, assignment):
        return AssignmentQuestion._default_manager.create(
            title="Q" + str(question_number),
            description="Question %d from the problem statement" % (question_number),
            category=FILE,
            assignment=assignment,
        )
