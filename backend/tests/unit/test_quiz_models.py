from app.db.models import ProcessingStep


def test_processing_step_includes_quiz_values():
    assert ProcessingStep.QUIZ_PREGEN_Q1.value == "quiz_pregen_q1"
    assert ProcessingStep.QUIZ_ROLLUP.value == "quiz_rollup"
