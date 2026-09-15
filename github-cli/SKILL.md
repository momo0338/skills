---
name: github-cli
description: Use the GitHub 'gh' CLI to interact with GitHub repositories, issues, pull requests, workflows, and API. Always specify --repo owner/repo when not in a git directory, or use URLs directly.
---

# GitHub CLI Skill

Use the `gh` CLI to interact with GitHub. This skill provides comprehensive guidance for using `gh` commands for repository operations, PR management, CI checks, and advanced API queries.

## Prerequisites

- GitHub CLI (`gh`) must be installed: `brew install gh` (macOS) or see [installation guide](https://github.com/cli/cli#installation)
- Must be authenticated: `gh auth login` or set `GITHUB_TOKEN` environment variable
- Token should have appropriate scopes for desired operations (e.g., `repo`, `workflow`)

## Repository Context

**Rule: Always specify `--repo owner/repo` when not in a git directory, or use URLs directly.**

When working in a git repository with a GitHub remote, `gh` automatically detects the repo. Otherwise, you must specify:

```bash
# Explicit repo specification
gh pr list --repo owner/repo

# Or use URL-based commands
gh pr view https://github.com/owner/repo/pull/55
```

---

## Pull Requests

### View PRs

```bash
# List PRs in repo
gh pr list --repo owner/repo --state open --limit 20

# View specific PR
gh pr view 55 --repo owner/repo

# View PR with web browser
gh pr view 55 --repo owner/repo --web
```

### Check CI Status

```bash
# Check CI checks on a PR
gh pr checks 55 --repo owner/repo

# Watch checks until completion
gh pr checks 55 --repo owner/repo --watch
```

### Create PR

```bash
# Create PR from current branch
gh pr create --title "Fix bug" --body "Description here"

# Create PR with template
gh pr create --template

# Create PR from specific branch
gh pr create --base main --head feature-branch --title "Feature"
```

### Review PR

```bash
# Approve PR
gh pr review 55 --approve --body "Looks good!"

# Request changes
gh pr review 55 --request-changes --body "Need fixes"

# Comment on PR
gh pr review 55 --comment --body "Question about this"
```

### Merge PR

```bash
# Merge PR (default: merge commit)
gh pr merge 55 --repo owner/repo

# Squash merge
gh pr merge 55 --squash

# Rebase merge
gh pr merge 55 --rebase
```

---

## Workflows & CI

### List Workflow Runs

```bash
# List recent runs
gh run list --repo owner/repo --limit 10

# Filter by workflow
gh run list --repo owner/repo --workflow ci.yml

# Filter by status
gh run list --repo owner/repo --status failed
```

### View Run Details

```bash
# View a specific run
gh run view <run-id> --repo owner/repo

# View logs for failed steps only
gh run view <run-id> --repo owner/repo --log-failed

# View full logs
gh run view <run-id> --repo owner/repo --log

# Watch run until completion
gh run watch <run-id> --repo owner/repo
```

### Trigger Workflows

```bash
# Trigger workflow run
gh workflow run ci.yml --repo owner/repo

# Trigger with parameters
gh workflow run ci.yml --repo owner/repo -f branch=main -f environment=staging
```

---

## Issues

### List Issues

```bash
# List open issues
gh issue list --repo owner/repo --state open

# Filter by label
gh issue list --repo owner/repo --label bug

# Filter by assignee
gh issue list --repo owner/repo --assignee username
```

### Create Issue

```bash
# Create issue
gh issue create --title "Bug report" --body "Description"

# Create with labels
gh issue create --title "Bug" --body "Description" --label bug,priority-high
```

### View Issue

```bash
# View issue details
gh issue view 123 --repo owner/repo

# View with comments
gh issue view 123 --repo owner/repo --comments
```

---

## API for Advanced Queries

The `gh api` command is useful for accessing data not available through other subcommands.

### Query Examples

```bash
# Get PR with specific fields
gh api repos/owner/repo/pulls/55 --jq '.title, .state, .user.login'

# Get repository info
gh api repos/owner/repo --jq '.description, .stargazers_count, .language'

# List contributors
gh api repos/owner/repo/contributors --jq '.[].login'

# Get user info
gh api users/username --jq '.name, .bio, .public_repos'

# Search code
gh api search/code?q=function+repo:owner/repo --jq '.items[].path'

# Search issues
gh api search/issues?q=is:issue+is:open+repo:owner/repo --jq '.items[].title'
```

### Pagination

```bash
# Paginated API call
gh api repos/owner/repo/issues --paginate --jq '.[].title'

# Limit results
gh api repos/owner/repo/issues --jq '.[:10]'
```

---

## JSON Output

Most commands support `--json` for structured output. Use `--jq` to filter:

```bash
# List issues as JSON
gh issue list --repo owner/repo --json number,title,state

# Filter with jq
gh issue list --repo owner/repo --json number,title --jq '.[] | "\(.number): \(.title)"'

# PR details as JSON
gh pr view 55 --repo owner/repo --json title,body,author,files

# Workflow runs as JSON
gh run list --repo owner/repo --json id,name,status,conclusion --jq '.[] | select(.status=="completed")'
```

### Common jq Patterns

```bash
# Select and format
--jq '.[] | "\(.field1): \(.field2)"'

# Filter by condition
--jq '.[] | select(.status == "open")'

# Get specific fields
--jq '{name: .name, count: .count}'

# Count results
--jq 'length'
```

---

## Repositories

### View Repository

```bash
# View repo info
gh repo view owner/repo

# View with web browser
gh repo view owner/repo --web
```

### Create Repository

```bash
# Create new repo
gh repo create my-project --public

# Create private repo
gh repo create my-project --private

# Create with description
gh repo create my-project --public --description "My project"
```

### Fork & Clone

```bash
# Fork repo
gh repo fork owner/repo

# Clone repo
gh repo clone owner/repo

# Clone to specific directory
gh repo clone owner/repo ./my-dir
```

---

## Gists

```bash
# Create gist
gh gist create myfile.txt --public

# Create private gist
gh gist create myfile.txt

# List gists
gh gist list

# View gist
gh gist view <gist-id>
```

---

## Releases

```bash
# List releases
gh release list --repo owner/repo

# View release
gh release view v1.0.0 --repo owner/repo

# Create release
gh release create v1.0.0 --repo owner/repo --title "Version 1.0" --notes "Release notes"

# Download release assets
gh release download v1.0.0 --repo owner/repo
```

---

## Quick Reference

| Category | Command | Purpose |
|----------|---------|---------|
| PR | `gh pr list` | List PRs |
| PR | `gh pr view N` | View PR details |
| PR | `gh pr checks N` | Check CI status |
| PR | `gh pr create` | Create new PR |
| PR | `gh pr merge N` | Merge PR |
| Issue | `gh issue list` | List issues |
| Issue | `gh issue create` | Create issue |
| Workflow | `gh run list` | List runs |
| Workflow | `gh run view ID` | View run details |
| Workflow | `gh run watch ID` | Watch run |
| API | `gh api path` | Direct API call |
| Repo | `gh repo view` | View repo info |
| Release | `gh release list` | List releases |

---

## Common Mistakes

| Problem | Solution |
|---------|----------|
| "gh: command not found" | Install: `brew install gh` |
| "authentication required" | Run `gh auth login` |
| "no git remote found" | Use `--repo owner/repo` flag |
| "permission denied" | Check token scopes: `gh auth status` |
| Rate limit errors | Use `--paginate` for large queries |
| JSON output unreadable | Add `--jq` for filtering |

---

## Security Note

- The skill requires `gh` CLI installed and authenticated
- Any gh-authenticated credentials determine what repos the skill can access
- Limit token scope to minimum necessary
- Only grant access to accounts/repos you trust
- Avoid enabling in environments where you don't want automated GitHub commands