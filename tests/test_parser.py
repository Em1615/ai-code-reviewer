from ai_reviewer.parser import parse_issues

def test_no_issues_found_returns_empty_list():
    assert parse_issues("NO ISSUES FOUND") == []


def test_empty_output_returns_empty_list():
    assert parse_issues("") == []
    assert parse_issues("  \n  ") == []


def test_parses_single_issue_with_em_dash():
    output = "[CRITICAL] auth.py:47 - SECURITY: SQL injection via unescaped input"
    issues = parse_issues(output)
    assert len(issues) == 1
    issue = issues[0]
    assert issue.severity == "CRITICAL"
    assert issue.file == "auth.py"
    assert issue.line == 47
    assert issue.category == "SECURITY"
    assert issue.description == "SQL injection via unescaped input"


def test_parses_issue_with_plain_hyphen_fallback():
    output = "[HIGH] worker.py:112 - RELIABILITY: unhandled exception from requests.get"
    issues = parse_issues(output)
    assert len(issues) == 1
    assert issues[0].category == "RELIABILITY"


def test_parses_issue_with_plain_hyphen_fallback():
    output = "[HIGH] worker.py:112 - RELIABILITY: unhandled exception from requests.get"
    issues = parse_issues(output)
    assert len(issues) == 1
    assert issues[0].category == "RELIABILITY"


def test_parses_multiple_issues():
    output = (
        "[CRITICAL] a.py:1 - BUG: wrong comparison operator\n"
        "[LOW] b.py:99 - DEPRECATION: ssl.wrap_socket removed in 3.12\n"
    )
    issues = parse_issues(output)
    assert len(issues) == 2
    assert issues[0].file == "a.py"
    assert issues[1].file == "b.py"


def test_drops_unparseable_lines_without_crashing():
    output = (
        "Here is my review:\n"
        "[CRITICAL] a.py:1 - BUG: wrong comparison operator\n"
        "Hope this helps!\n"
    )
    issues = parse_issues(output)
    assert len(issues) == 1


def test_rejects_unknown_severity():
    output = "[WHATEVER] a.py:1 - BUG: something"
    assert parse_issues(output) == []


def test_rejects_unknown_category():
    output = "[CRITICAL] a.py:1 - STYLE: bad naming"
    assert parse_issues(output) == []


def test_filename_with_path_separators():
    output = "[MEDIUM] src/utils/cache.py:78 - MEMORY: unbounded dict growth"
    issues = parse_issues(output)
    assert issues[0].file == "src/utils/cache.py"


def test_format_comment_contains_severity_and_category():
    output = "[HIGH] db.py:34 - PERFORMANCE: N+1 query in loop"
    issue = parse_issues(output)[0]
    comment = issue.format_comment()
    assert "HIGH" in comment
    assert "PERFORMANCE" in comment
    assert "N+1 query in loop" in comment