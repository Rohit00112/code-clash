from app.services.draft_service import DraftService


def test_default_templates_include_function_name_for_all_languages():
    function_name = "find_answer"
    languages = ["python", "java", "c", "cpp", "javascript", "csharp"]

    for language in languages:
        template = DraftService.get_default_template(language, function_name)
        assert function_name in template
