---
context: fork
allowed-tools: Grep, Read
argument-hint: <directory-or-file-to-audit>
---

Perform a security audit of the code at $ARGUMENTS.

Look for:
1. Injection vulnerabilities: SQL injection, command injection, path traversal
2. Hardcoded secrets or credentials (API keys, passwords, tokens)
3. Insecure defaults: debug mode enabled, permissive CORS, missing auth checks
4. Overly permissive file access or directory listing
5. Unvalidated external input reaching sensitive operations

For each finding, output:
- **Severity**: Critical / High / Medium / Low
- **Location**: file:line
- **Description**: what the vulnerability is
- **Recommendation**: how to fix it
