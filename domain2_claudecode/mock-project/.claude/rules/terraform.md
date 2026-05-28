## Terraform Standards
- Always run `terraform fmt` before committing
- Never hardcode resource names — use variables
- Tag every resource with `project` and `environment`
- Store state in S3 backend (never local)
