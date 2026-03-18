from scripts.trace_engineer_backends import build_trace_report


def test_build_trace_report_keeps_results():
    report = build_trace_report(
        "simple_ma",
        "default",
        2000,
        [{"backend_name": "openai_compatible", "success": False}],
    )

    assert report["spec_name"] == "simple_ma"
    assert report["style"] == "default"
    assert report["max_tokens"] == 2000
    assert report["results"][0]["backend_name"] == "openai_compatible"
