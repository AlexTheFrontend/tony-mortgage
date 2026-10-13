from scripts.extract_text import short_issues


def test_short_issues_lists_issues_with_little_text():
    issues = [{"date": "2022-04-07", "chars": 13641},
              {"date": "2022-04-13", "chars": 150},
              {"date": "2022-04-21", "chars": 0}]
    assert short_issues(issues) == ["2022-04-13", "2022-04-21"]
