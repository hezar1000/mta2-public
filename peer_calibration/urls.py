from django.conf.urls import url

from .views import CalibrationViews

urlpatterns = [
    url(r"^([0-9]+)/request/$", CalibrationViews.calibration_request),
    url(r"^([0-9]+)/view/$", CalibrationViews.calibration_view),
    url(r"^([0-9]+)/create/$", CalibrationViews.calibration_create),
    url(
        r"^(?P<aid>[0-9]+)/assign_calibration_reviews/$",
        CalibrationViews.assign_calibration_reviews,
        name="assign_calibration_reviews",
    ),
    url(
        r"^(?P<aid>[0-9]+)/calibration_assignment_create/$",
        CalibrationViews.calibration_assignment_create,
        name="calibration_assignment_create",
    ),
    url(
        r"^(?P<sid>[0-9]+)/calibration_assignment_edit/$",
        CalibrationViews.calibration_assignment_edit,
        name="calibration_assignment_edit",
    ),
    url(
        r"^(?P<rid>[0-9]+)/calibration_groundtruth_edit/$",
        CalibrationViews.calibration_groundtruth_edit,
        name="calibration_groundtruth_edit",
    ),
]
