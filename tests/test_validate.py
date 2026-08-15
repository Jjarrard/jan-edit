from janedit import validate


def test_valid_python_passes():
    assert validate.validate("a.py", "def f():\n    return 1\n").ok


def test_broken_python_is_caught():
    result = validate.validate("a.py", "def f(:\n    return 1\n")
    assert not result.ok
    assert "syntax error" in result.message.lower()


def test_bad_indentation_is_caught():
    result = validate.validate("a.py", "def f():\nreturn 1\n")
    assert not result.ok


def test_unclosed_paren_in_python_is_caught():
    result = validate.validate("a.py", "print('hello'\n")
    assert not result.ok


def test_valid_json_passes():
    assert validate.validate("a.json", '{"a": 1}').ok


def test_broken_json_is_caught():
    result = validate.validate("a.json", '{"a": 1,}')
    assert not result.ok
    assert "json" in result.message.lower()


def test_empty_json_file_passes():
    assert validate.validate("a.json", "  ").ok


def test_balanced_js_passes():
    assert validate.validate("a.js", "function f() { return [1, 2]; }\n").ok


def test_unclosed_brace_in_js_is_caught():
    result = validate.validate("a.js", "function f() { return 1;\n")
    assert not result.ok
    assert "unclosed" in result.message.lower()


def test_mismatched_bracket_in_js_is_caught():
    result = validate.validate("a.js", "const a = [1, 2};\n")
    assert not result.ok


def test_braces_inside_js_strings_are_ignored():
    # a naive counter would flag this valid file
    assert validate.validate("a.js", 'const s = "a { unmatched";\nconst t = 1;\n').ok


def test_braces_inside_js_comments_are_ignored():
    assert validate.validate("a.js", "// a { comment\n/* another } here */\nconst a = 1;\n").ok


def test_escaped_quote_in_js_string_is_handled():
    assert validate.validate("a.js", 'const s = "he said \\"hi\\"";\n').ok


def test_unknown_extension_always_passes():
    assert validate.validate("notes.md", "# hi {unbalanced").ok
    assert validate.validate("data.xyz", "((((").ok


def test_html_is_not_bracket_checked():
    # HTML legitimately contains unbalanced braces in inline CSS/JS snippets
    assert validate.validate("index.html", "<style>body { color: red }</style>").ok
