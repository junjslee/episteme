## Summary

Describe the specific problem this PR solves and what changed.

## Linked issue

Closes #

## Scope

- [ ] This PR addresses one coherent change set
- [ ] No unrelated refactors or drive-by edits

## Verification

### Commands run

```bash
python3 -m py_compile src/agent_os/cli.py
python -m pytest -q
```

Paste outputs or summarize failures/fixes.

### Behavioral checks

- [ ] CLI help/usage still valid for changed commands
- [ ] README/docs examples match current behavior
- [ ] `cognitive-os` naming is consistent (no legacy command drift)

## Risk and rollback

- Risk level: low / medium / high
- Rollback plan:

## Evidence

Include test output, screenshots, or sample command output where helpful.

## Final checklist

- [ ] I tested this change locally
- [ ] Docs updated (if behavior changed)
- [ ] CI should pass on Python 3.10/3.11/3.12
