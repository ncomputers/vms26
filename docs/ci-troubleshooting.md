# CI Troubleshooting

When GitHub Actions runs fail, the tips below cover the most common culprits and how to resolve them.

## Network restrictions
Self-hosted or corporate runners may block outbound network access. This prevents dependency downloads and external API calls.

**Resolution:** Ensure required domains are whitelisted and that proxies allow the runner to reach PyPI, npm, and other services. Retry the job after network access is restored.

## Missing `GITHUB_TOKEN`
Some steps rely on the automatically provided `GITHUB_TOKEN` for authentication. If the token is missing or has insufficient permissions, the workflow may fail to check out code or publish artifacts.

**Resolution:** Verify that the workflow is running in a GitHub context where `GITHUB_TOKEN` is available and has the necessary scopes. For forks, enable workflows or provide a personal access token with appropriate rights.

## Artifact upload limits
Large test logs or coverage reports can exceed GitHub's artifact size or retention limits.

**Resolution:** Prune unnecessary files before uploading, or split artifacts into smaller pieces. Consider storing large artifacts in external storage if they regularly exceed the limits.
