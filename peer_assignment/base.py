import collections
import json
from django.utils import timezone
from django.db.models import Q

from peer_course.models import Course
from peer_course.base import CourseBase

from .models import *
from .utils import AssignmentUtils
from peer_review.choices import TEXT_ASGN, QUIZ_ASGN, PDF, FILE, TEXT, MULTIPLECHOICE


class AssignmentBase:
    @staticmethod
    def add_files(src, files, table="assignment"):
        return False
        # if table == 'assignment' :
        #     for fun in files:
        #         assf = AssignmentFile(
        #             assignment=src,
        #             attachment=fun,
        #         )
        #         assf.save()
        # elif table == 'submission' :
        #     for fun in files:
        #         subf = SubmissionFile(
        #             submission=src,
        #             attachment=fun,
        #         )
        #         subf.save()
        # return True

    @staticmethod
    def remove_files(task, table="assignment"):
        # # TODO: needs fix
        # if table == 'assignment' :
        #     task.assignmentfile_set.all().delete()
        # elif table == 'submission' :
        #     pass # TODO: check if we need this
        #     # for sc in task.components.all():
        #     #     sc.submissioncomponentfile_set.delete()
        #     # task.submissionfile_set.all().delete()
        return True

    @staticmethod
    def find_files(task, table="assignment"):
        # # TODO: needs fix
        # files = []
        # if table == 'assignment' :
        #     files = task.assignmentfile_set.all()
        # elif table == 'submission' :
        #     files = [sc.attachment for sc in task.submissioncomponent_set.all()]
        return files

    @staticmethod
    def save_submission_files(cleaned_data, submission, request):
        has_file = False
        if submission == None:
            raise ValueError("Submission cannot be None")

        for field_name, field_content in cleaned_data.items():
            found = re.search("rq_file_([0-9]+)", field_name)
            if found is None:
                continue

            rq_id = found.group(1)
            print("rq_id", rq_id)
            print("field_name", field_name)

            rq = AssignmentQuestion._default_manager.get(pk=rq_id)
            rc = SubmissionComponent._default_manager.get(
                question=rq, submssion=submission
            )

            files = request.FILES.getlist(field_name)
            for f in files:
                rcf = SubmissionComponentFile(attachment=f, belongs_to=rc)
                rcf.save()
            rc.content = "files"
            rc.save()

            has_file = True
        return has_file

    @staticmethod
    def get(user, course, option="all"):
        all_assignments = Assignment._default_manager.filter(
            course=course, browsable=True, submission_required=True
        ).order_by("-deadline")
        if option == "all":
            return all_assignments
        elif option == "completed":
            return all_assignments.filter(assignmentsubmission__author__user=user)
        elif option == "pending":
            return all_assignments.exclude(assignmentsubmission__author__user=user)

    @staticmethod
    def delete_submission(user, sid):
        sub = AssignmentSubmission._default_manager.get(id=sid)
        cid = sub.assignment.course.id
        if user is not sub.author.user:
            raise Exception(
                "You cannot delete this submission because you are not its author."
            )
        elif sub.author.active == False:
            raise Exception(
                "You cannot delete this submission because your account has been deactivated."
            )
        else:
            sub.delete()
            return cid

    @staticmethod
    def find_submission(user, assignment):
        sub = AssignmentSubmission._default_manager.filter(
            author__user=user, assignment=assignment
        ).first()
        return sub

    @staticmethod
    def get_user_assignments_by_status(user, course=None):
        if course is None:
            courses = CourseBase.get_courses(user)  # .order_by('displayname')
        else:
            courses = [course]

        # TODO: instructors can't use this, since they should be able to see every course
        assignments_all = Assignment._default_manager.filter(
            course__in=courses, browsable=True
        ).order_by("-deadline")
        return {
            "all": assignments_all,
            "completed": assignments_all.filter(
                assignmentsubmission__author__user=user
            ),
            "pending": (
                assignments_all.exclude(assignmentsubmission__author__user=user).filter(
                    deadline__gte=timezone.now()
                )
            ),
        }

    @staticmethod
    def get_visible_assignments(course, user, is_student):
        assignments = course.assignment_set.all()
        if is_student:
            assignments = course.assignment_set.filter(browsable=True)
        assignments = assignments.order_by("-deadline")

        assignment_dict = collections.OrderedDict()

        for assignment in assignments:

            aid = str(assignment.id)
            assignment_dict[aid] = dict()
            assignment_dict[aid]["assignment"] = assignment

            submissions = assignment.assignmentsubmission_set.all()
            if is_student:
                deadlinePassed = timezone.now() > assignment.deadline
                assignment_dict[aid]["deadline_passed"] = deadlinePassed

                submissions = submissions.filter(author__user=user)
                assignment_dict[aid]["has_submission"] = submissions.exists()
                if submissions.exists():
                    assignment_dict[aid]["mysubmission"] = submissions.first()
                    # The commented code below is for displaying the files of a submission
                    # We are going to replace it in forms.py
                    # assignment_dict[aid]['submissionFiles'] = AssignmentBase.find_files(submissions.first(), 'submission')
            else:
                assignment_dict[str(aid)]["submissions"] = submissions

        return assignment_dict

    @staticmethod
    def get_submission(sid):
        return AssignmentSubmission._default_manager.filter(id=sid).first()


def pdf_q_creator(saved_instance, data):
    # TODO: check if doing this is okay
    correct_num_questions = int(data["num_questions"])
    if (
        saved_instance.questions.count() != correct_num_questions
        or saved_instance.questions.filter(category=FILE).count()
        != correct_num_questions
    ):
        saved_instance.questions.all().delete()
        for i in range(correct_num_questions):
            AssignmentUtils.create_empty_question(i + 1, saved_instance)


def add_q_choices(choices, question):
    for choice in choices:
        pk = choice.pop("pk", None) or None
        c = AssignmentQuestionMultipleChoice._default_manager.update_or_create(
            pk=pk, defaults={"question": question, **choice}
        )


def text_q_creator(saved_instance, data):
    questions = json.loads(data["questions"])

    if data.get("assignment_type", TEXT_ASGN) == TEXT_ASGN:
        category = TEXT
    else:
        category = MULTIPLECHOICE
    for q_data in questions:
        choices = q_data.pop("choices", [])
        pk = q_data.pop("pk", None) or None
        q, _ = AssignmentQuestion._default_manager.update_or_create(
            pk=pk,
            defaults={"category": category, "assignment": saved_instance, **q_data},
        )

        if category == MULTIPLECHOICE:
            add_q_choices(choices, q)
            choice_pks = [c.get("pk", None) or None for c in choices]
            q.choices.exclude(pk__in=choice_pks).delete()
        else:
            q.choices.all().delete()


question_creators = {
    PDF: pdf_q_creator,
    TEXT_ASGN: text_q_creator,
    QUIZ_ASGN: text_q_creator,
}
