"""Offline unit tests for GitHub issue/PR rendering internals."""
from __future__ import annotations

from web_search_mcp.social.github import (
    _render_comments,
    _render_header,
    _render_reactions_bar,
    _render_single_comment,
    _sum_reactions,
    parse_github_url,
    render_issue_markdown,
)


class TestParseGithubUrl:
    """Test GitHub URL parsing."""

    def test_valid_issue_url(self) -> None:
        owner, repo, num, kind = parse_github_url("https://github.com/owner/repo/issues/42")
        assert (num, kind) == (42, "issue")

    def test_valid_pr_url(self) -> None:
        owner, repo, num, kind = parse_github_url("https://github.com/owner/repo/pull/7")
        assert (num, kind) == (7, "pr")

    def test_www_subdomain_accepted(self) -> None:
        owner, repo, num, kind = parse_github_url("https://www.github.com/owner/repo/issues/1")
        assert kind == "issue"

    def test_unsupported_host_raises(self) -> None:
        from pytest import raises
        with raises(ValueError, match="Unsupported GitHub host"):
            parse_github_url("https://gitlab.com/owner/repo/issues/1")

    def test_missing_host_raises(self) -> None:
        from pytest import raises
        with raises(ValueError, match="missing"):
            parse_github_url("https:///issues/1")

    def test_non_matching_path_raises(self) -> None:
        from pytest import raises
        with raises(ValueError, match="not a recognized"):
            parse_github_url("https://github.com/owner/repo/wiki")


class TestSumReactions:
    """Test _sum_reactions aggregation."""

    def test_none_input_returns_empty(self) -> None:
        assert _sum_reactions(None) == {}

    def test_empty_list_returns_empty(self) -> None:
        assert _sum_reactions([]) == {}

    def test_aggregates_counts(self) -> None:
        groups = [
            {"content": "THUMBS_UP", "users": {"totalCount": 3}},
            {"content": "HEART", "users": {"totalCount": 2}},
            {"content": "THUMBS_UP", "users": {"totalCount": 1}},
        ]
        result = _sum_reactions(groups)
        assert result == {"THUMBS_UP": 4, "HEART": 2}

    def test_skips_non_dict_entries(self) -> None:
        groups = [{"content": "LAUGH", "users": {"totalCount": 5}}, "not a dict"]
        result = _sum_reactions(groups)
        assert result == {"LAUGH": 5}

    def test_skips_zero_counts(self) -> None:
        groups = [{"content": "ROCKET", "users": {"totalCount": 0}}]
        assert _sum_reactions(groups) == {}

    def test_handles_invalid_count_as_zero(self) -> None:
        groups = [{"content": "EYES", "users": {"totalCount": "bad"}}]
        result = _sum_reactions(groups)
        assert result == {}  # count=0 is skipped


class TestRenderReactionsBar:
    """Test _render_reactions_bar formatting."""

    def test_empty_counts_returns_empty_string(self) -> None:
        assert _render_reactions_bar({}) == ""

    def test_single_reaction(self) -> None:
        result = _render_reactions_bar({"THUMBS_UP": 3})
        assert "👍 3" in result

    def test_multiple_reactions_joined_with_pipe(self) -> None:
        result = _render_reactions_bar({"THUMBS_UP": 2, "HEART": 5})
        parts = result.split(" | ")
        assert len(parts) == 2

    def test_unknown_emoji_returns_empty(self) -> None:
        result = _render_reactions_bar({"UNKNOWN_FLAG": 1})
        assert result == ""


class TestRenderHeader:
    """Test _render_header output."""

    def test_issue_kind(self) -> None:
        data = {"title": "Bug fix", "url": "https://gh.io/1", "state": "open"}
        lines = _render_header(data, "issue")
        assert "# Issue" in lines
        assert "Bug fix" in lines[1]

    def test_pr_kind(self) -> None:
        data = {"title": "Feature", "url": "https://gh.io/2", "state": "open"}
        lines = _render_header(data, "pr")
        assert "# Pull Request" in lines

    def test_merged_state_emoji(self) -> None:
        data = {"title": "Merged", "url": "u", "state": "merged"}
        lines = _render_header(data, "issue")
        assert "merged" in lines[1]

    def test_closed_state_emoji(self) -> None:
        data = {"title": "Closed", "url": "u", "state": "closed"}
        lines = _render_header(data, "issue")
        assert "closed" in lines[1]

    def test_author_from_dict(self) -> None:
        data = {
            "title": "T", "url": "u", "state": "open",
            "author": {"login": "alice"},
        }
        lines = _render_header(data, "issue")
        assert "@alice" in lines[1]

    def test_missing_author_empty(self) -> None:
        data = {"title": "T", "url": "u", "state": "open"}
        lines = _render_header(data, "issue")
        assert "Author: @" in lines[1]

    def test_title_defaults_to_untitled(self) -> None:
        data = {"url": "u", "state": "open"}
        lines = _render_header(data, "issue")
        assert "Untitled" in lines[1]


class TestRenderComments:
    """Test comment rendering with minimized filtering and sorting."""

    def test_no_comments_section(self) -> None:
        lines = _render_comments(None)
        assert "# Comments" in lines
        assert "_No comments._" in lines

    def test_empty_list(self) -> None:
        lines = _render_comments([])
        assert "# Comments" in lines
        assert "_No comments._" in lines

    def test_minimized_comments_filtered_out(self) -> None:
        comments = [
            {"body": "good comment", "isMinimized": False, "author": {"login": "a"}},
            {"body": "hidden", "isMinimized": True, "author": {"login": "b"}},
        ]
        lines = _render_comments(comments)
        text = "\n".join(lines)
        assert "good comment" in text
        assert "hidden" not in text

    def test_comments_sorted_by_reaction_count_desc(self) -> None:
        comments = [
            {"body": "few", "reactionGroups": [{"content": "THUMBS_UP", "users": {"totalCount": 1}}],
             "isMinimized": False, "author": {"login": "x"}},
            {"body": "many", "reactionGroups": [
                {"content": "THUMBS_UP", "users": {"totalCount": 3}},
                {"content": "HEART", "users": {"totalCount": 2}},
            ],
             "isMinimized": False, "author": {"login": "y"}},
        ]
        lines = _render_comments(comments)
        full = "\n".join(lines)
        # "many" (5 reactions) should appear before "few" (1 reaction)
        assert full.index("many") < full.index("few")


class TestRenderSingleComment:
    """Test individual comment rendering."""

    def test_member_badge(self) -> None:
        lines = _render_single_comment({
            "author": {"login": "alice"},
            "authorAssociation": "MEMBER",
            "createdAt": "2024-01-01T00:00:00Z",
            "url": "https://gh.io/c/1",
            "body": "Hello",
        }, 1)
        assert any(line.startswith("## Comment 1") for line in lines)
        assert any("🏷" in line for line in lines)  # MEMBER badge

    def test_collaborator_badge(self) -> None:
        lines = _render_single_comment({
            "author": {"login": "bob"},
            "authorAssociation": "COLLABORATOR",
            "body": "Test",
        }, 2)
        text = "\n".join(lines)
        assert "## Comment 2" in text
        assert "🤝" in text  # COLLABORATOR badge

    def test_owner_badge(self) -> None:
        lines = _render_single_comment({
            "author": {"login": "owner"},
            "authorAssociation": "OWNER",
            "body": "Test",
        }, 3)
        text = "\n".join(lines)
        assert "## Comment 3" in text
        assert "👑" in text  # OWNER badge

    def test_no_body_shows_placeholder(self) -> None:
        lines = _render_single_comment({
            "author": {"login": "x"},
            "body": "",
        }, 1)
        text = "\n".join(lines)
        assert "_No text._" in text

    def test_empty_reaction_bar_excluded_from_meta(self) -> None:
        lines = _render_single_comment({
            "author": {"login": "x"},
            "body": "hello",
            "reactionGroups": [],
        }, 1)
        text = "\n".join(lines)
        assert "Reactions:" not in text


class TestRenderIssueMarkdown:
    """Test render_issue_markdown end-to-end with dict fixtures."""

    def test_minimal_issue(self) -> None:
        data = {"title": "Bug", "url": "https://gh.io/1", "state": "open", "body": "Steps: 1"}
        result = render_issue_markdown(data, "issue")
        assert "# Issue" in result
        assert "Bug" in result
        assert "Steps: 1" in result

    def test_pr_with_reactions_and_comments(self) -> None:
        data = {
            "title": "Fix #42",
            "url": "https://gh.io/2",
            "state": "merged",
            "body": "This PR fixes the bug.",
            "reactionGroups": [{"content": "HOORAY", "users": {"totalCount": 3}}],
            "comments": [
                {
                    "body": "LGTM",
                    "author": {"login": "reviewer"},
                    "authorAssociation": "MEMBER",
                    "createdAt": "2024-01-02T00:00:00Z",
                    "url": "https://gh.io/c/1",
                    "reactionGroups": [{"content": "THUMBS_UP", "users": {"totalCount": 1}}],
                    "isMinimized": False,
                }
            ],
        }
        result = render_issue_markdown(data, "pr")
        assert "# Pull Request" in result
        assert "🎉 3" in result
        assert "LGTM" in result

    def test_no_comments_section(self) -> None:
        data = {"title": "T", "url": "u", "state": "open"}
        result = render_issue_markdown(data)
        assert "# Comments" in result
        assert "_No comments._" in result
