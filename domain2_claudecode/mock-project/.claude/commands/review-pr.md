Review pull request $ARGUMENTS.

Check for:
- Logic errors and edge cases that tests don't cover
- Missing or insufficient tests
- Security issues: injection, authentication bypass, secrets committed to code
- Breaking changes to public API surface

Output a structured report:
- **High**: must fix before merge
- **Medium**: should fix before merge
- **Low**: consider fixing, non-blocking

Group findings by severity. Include file:line references for each finding.
