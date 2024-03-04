from peer_assignment.models import Assignment, AssignmentSubmission, AssignmentQuestion
from peer_review.models import (
    AssignmentWithReviews,
    Rubric,
    ReviewAssignment,
    RubricQuestionMultipleChoiceItem,
)

# from peer_review.base import ReviewBase
from .models import EvaluationAssignment
from itertools import chain



class EvaluationBase:
    @staticmethod
    def __assign_evaluations(reviews, num_to_assign):
        reviews = reviews.order_by("?")
        reviewers = reviews.values_list("grader", flat=True)
        total_count = reviews.count()

        for i, review in enumerate(reviews):

            num_evaluations_assigned = review.evaluations.filter(
                grader__in=reviewers
            ).count()

            index = (i + 1) % total_count

            while num_evaluations_assigned < num_to_assign:

                evaluator = reviews[index].grader
                if review.evaluations.filter(grader=evaluator).exists():
                    index = (index + 1) % total_count
                    continue

                else:
                    print("%s, %s" % (review, evaluator))
                    EvaluationAssignment._default_manager.create(
                        review=review, grader=evaluator
                    )

                    num_evaluations_assigned += 1
                    index = (index + 1) % total_count

    @staticmethod
    def assign_student_evaluations(assignment, num_independent, num_supervised):
        reviews = ReviewAssignment._default_manager.filter(
            submission__assignment__id=assignment.id
        )
        EvaluationBase.__assign_evaluations(
            reviews.filter(grader__is_independent=True), num_independent
        )
        EvaluationBase.__assign_evaluations(
            reviews.filter(grader__is_independent=False), num_supervised
        )

    @staticmethod
    def get_my_evaluations(user, course, option="all"):
        if option == "pending":
            return [
                ea
                for ea in EvaluationAssignment._default_manager.filter(
                    review__submission__assignment__course=course, grader__user=user
                )
                if (
                    not ea.deadline_passed()
                    or ea.grader.role == "ta"
                    or ea.grader.role == "instructor"
                )
                and not ea.contents.exists()
            ]
        elif option == "all":
            return EvaluationAssignment._default_manager.filter(
                review__submission__assignment__course=course, grader__user=user
            ).order_by("-deadline")



    @staticmethod
    def get_my_grades(user, course):
        submissions = AssignmentSubmission._default_manager.filter(
            assignment__course=course, author__user=user, calibration_id=0
        )
    #    reviews = ReviewAssignment._default_manager.filter(
    #        submission__assignment__course=course,
    #        grader__user=user,
    #        submission__calibration_id=0,
    #    )
        evals= EvaluationAssignment._default_manager.filter(
                review__submission__assignment__course=course, review__grader__user=user
        )

        grading_items = sorted(
            chain(submissions, evals),
            key=lambda x: x.creation_date
            if isinstance(x, EvaluationAssignment)
            else x.time_submitted,
        )
        return grading_items


    @staticmethod
    def get_evaluation_components_dict(evaluation):
        components = {}

        for sc in evaluation.review.submission.components.all():
            # TODO: refactor this part out
            content_queryset = evaluation.contents.filter(submission_component=sc)
            contents = list()

            for content_obj in content_queryset:
                content_dict = dict()

                content_dict["question"] = content_obj.choice.question.text
                content_dict["content_obj"] = content_obj
                content_dict["reason"] = content_obj.reason

                # if content_obj.choice.question.category == MULTIPLECHOICE :
                choice_id = int(content_obj.choice.id)
                chosen = RubricQuestionMultipleChoiceItem._default_manager.get(
                    pk=choice_id
                )
                content_dict["answer"] = chosen.text
                content_dict["grade"] = chosen.marks
                content_dict["max_grade"] = chosen.question.max_grade()

                # elif content_obj.choice.question.category == TEXT :
                #     content_dict['answer'] = content_obj.choice.id

                # elif content_obj.choice.question.category == FILE :
                #     pass
                # content_dict['answer'] = ReviewUtils.get_file_links(
                #     content_obj.choice.question, review)

                contents.append(content_dict)

            components[sc.id] = contents

        return components

    @staticmethod
    def assign_spot_checks(aid, num_to_assign, tas):
        """
            Randomly assigns evaluations to `num_to_assign` reviews that didn't already
            have TA reviews assigned to them.
            Will cyclically assign TAs until the required number of evaluations is met.

            Pre-conditions:
              - param `tas` is not empty
        """
        # order reviews randomly
        reviews = EvaluationBase.get_reviews_without_ta_evaluation(aid).order_by("?")[
            :num_to_assign
        ]

        # order tas randomly
        tas = list(tas.order_by("?"))
        num_tas = len(tas)

        for i, review in enumerate(reviews):
            EvaluationAssignment._default_manager.create(
                review=review, grader=tas[i % num_tas]
            )

        return reviews.count()

    @staticmethod
    def _assign_evaluation_on_spot_check(submission, spot_check):
        std_reviews = submission.reviewassignment_set.filter(grader__role="student")
        for review in std_reviews:
            # if review.grader.is_independent is False:
            if not review.evaluations.filter(grader__role="ta").exists():
                EvaluationAssignment._default_manager.create(
                    review=review, grader=spot_check.grader
                )

    @staticmethod
    def get_reviews_without_ta_evaluation(aid):
        return (
            ReviewAssignment._default_manager.filter(
                submission__assignment__id=aid, submitted=True
            )
            .exclude(evaluations__grader__role="ta")
            .exclude(evaluations__grader__role="instructor")
        )

    @staticmethod
    def review_without_ta_evaluation_count(aid):
        return EvaluationBase.get_reviews_without_ta_evaluation(aid).count()


# ReviewBase.add_spot_check_hook(EvaluationBase._assign_evaluation_on_spot_check)
