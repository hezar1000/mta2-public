from django.utils import timezone
from rest_framework import serializers
from .models import Assignment, AssignmentQuestion, AssignmentQuestionMultipleChoice
from peer_review.models import AssignmentWithReviews


# class ChoiceSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = AssignmentQuestionMultipleChoice
#         fields = ('id', 'choice_text', 'marks',)


# class QuestionSerializer(serializers.ModelSerializer):
#     choices = ChoiceSerializer(
#         many=True, read_only=True,
#         source='assignment_question_multiple_choice_set')

#     class Meta:
#         model = AssignmentQuestion
#         fields = ('id', 'title', 'description', 'category', 'choices',)


class AssignmentSerializer(serializers.ModelSerializer):
    # questions = QuestionSerializer(many=True, read_only=True, source='questions')

    def to_representation(self, obj):
        """Add number of questions to the representation"""
        ret = super(AssignmentSerializer, self).to_representation(obj)
        ret["num_questions"] = obj.questions.count()
        return ret

    def validate_deadline(self, value):
        if value is not None and value < timezone.now():
            if self.instance and self.instance.deadline < timezone.now():
                pass
            else:
                raise serializers.ValidationError("Deadline cannot be set in the past.")
        return value

    def validate(self, data):
        if "deadline" in data:
            if "release_time" in data and data["deadline"] < data["release_time"]:
                raise serializers.ValidationError(
                    "Deadline cannot be set before the release time."
                )
            if self.instance is not None:
                awr = AssignmentWithReviews._default_manager.filter(
                    assignment__id=self.instance.id
                ).first()
                # TODO: check deadline + grace_hours
                if (
                    awr is not None
                    and awr.student_review_deadline_default < data["deadline"]
                ):
                    raise serializers.ValidationError(
                        "Deadline cannot be set after the deadline for student reviews: %s."
                        % awr.student_review_deadline_default.strftime("%c")
                    )
        return data

    class Meta:
        model = Assignment
        fields = (
            "id",
            "course",
            "name",
            "browsable",
            "release_time",
            "deadline",
            "assignment_type",
            "statement",
            "max_late_units",
            "grace_hours",
            "submission_required",
            "qualification_grade",
        )  # 'questions',)
