# PowerStore CT Engine - Agent Rules

This file contains rules and guidelines for AI agents working on the PowerStore CT Engine project.

## File Operations

### File Verification Rule (CRITICAL)
- **ALWAYS verify file save operations**: After any file write operation, immediately verify that the file has been successfully saved by:
  - Running `ls -la` on the target directory to confirm the file exists
  - Checking file permissions and size
  - Reading a portion of the file to confirm content integrity
  - Confirming the file path is correct (especially for cross-platform paths)

- **Cross-platform path handling**: 
  - When working with Windows paths from WSL, translate `C:\` to `/mnt/c/`
  - Always verify the actual mount points using `df -h`
  - Test path accessibility before attempting file operations

- **File operation workflow**:
  1. Perform the file write operation
  2. Immediately verify with `ls -la [target_directory]`
  3. If verification fails, retry with the correct path
  4. Confirm success to the user

## Security Rules

### Credential Management
- **NEVER commit credentials**: Never commit files containing:
  - API keys, tokens, or passwords
  - Database credentials
  - SSH keys or certificates
  - Environment files with secrets (.env, .env.*, etc.)

- **Always update .gitignore**: Ensure sensitive files are excluded:
  - `.env*` files
  - `*.key`, `*.pem`, `*.crt` files
  - `credentials.json`, `secrets.json`
  - `__pycache__/`, `*.pyc` files

### Code Security
- **SQL injection prevention**: Never use string interpolation in SQL queries
- **Input validation**: Always validate and sanitize user inputs
- **SSL/TLS**: Never disable SSL verification in production code

## Code Quality Rules

### Error Handling
- **Specific exceptions**: Use specific exception types instead of generic `Exception`
- **Resource cleanup**: Always use context managers or finally blocks for resource cleanup
- **Logging**: Log errors with sufficient context for debugging

### Code Style
- **PEP 8 compliance**: Follow Python naming conventions
- **Type hints**: Add type hints to function signatures
- **Documentation**: Include docstrings for functions and classes

## Project-Specific Rules

### Configuration Management
- **Use new config system**: Prefer `shared.config_loader` over deprecated `shared.config`
- **Environment-specific configs**: Use appropriate config classes (DevelopmentConfig, StagingConfig, ProductionConfig)
- **Vault integration**: Use Vault for secret management in production

### Database Operations
- **Connection pooling**: Implement connection pooling for database operations
- **Transaction management**: Use proper transaction boundaries and rollback on errors
- **Parameterized queries**: Always use parameterized queries to prevent SQL injection

### Branch Management
- **Branch protection**: Set up appropriate branch protection rules
- **Default branch**: Keep `main` as the default branch
- **Pull requests**: Require PRs for merging to protected branches

## Testing Rules

### Test Coverage
- **Unit tests**: Write unit tests for critical functions
- **Integration tests**: Test external service integrations
- **Test verification**: Always run tests before committing changes

### Test Commands
- **Run tests**: Use project-specific test commands (check for test scripts, pytest, etc.)
- **Test coverage**: Aim for minimum test coverage thresholds
- **Test isolation**: Ensure tests are independent and can run in parallel

## Documentation Rules

### Code Documentation
- **Docstrings**: Include docstrings for all public functions and classes
- **Comments**: Add comments for complex logic (but avoid obvious comments)
- **README**: Keep README.md updated with project information

### Change Documentation
- **Commit messages**: Use descriptive commit messages following conventional commit format
- **Change logs**: Document significant changes in CHANGELOG.md
- **API docs**: Generate API documentation using tools like Swagger/OpenAPI

## Git Operations

### Commit Rules
- **Pre-commit verification**: Always verify staged changes with `git status` and `git diff`
- **Commit message format**: Use conventional commit format: `type(scope): description`
- **Atomic commits**: Make commits that are atomic and focused on a single change

### Push Rules
- **Verification before push**: Always check git status before pushing
- **Branch verification**: Ensure you're on the correct branch before pushing
- **Remote verification**: Confirm the remote URL is correct

## Build and Deployment Rules

### Build Verification
- **Build commands**: Run build commands and verify successful completion
- **Error handling**: Check build output for errors and warnings
- **Artifact verification**: Verify build artifacts are created correctly

### Deployment Safety
- **Environment checks**: Verify target environment before deployment
- **Backup verification**: Confirm backups exist before destructive operations
- **Rollback planning**: Always have a rollback plan for deployments

## Communication Rules

### User Interaction
- **Progress updates**: Inform users about progress during long operations
- **Error reporting**: Clearly explain errors and suggest solutions
- **Confirmation**: Ask for user confirmation before destructive operations

### Tool Usage
- **Explain operations**: Briefly explain what commands will do before executing
- **Show results**: Display relevant output from commands
- **Handle errors gracefully**: Provide helpful error messages and recovery options

## Verification Commands

### File Verification Commands
```bash
# Verify file exists and check details
ls -la /path/to/file

# Check file size
wc -c /path/to/file

# Verify file content
head -n 5 /path/to/file

# Check file permissions
stat /path/to/file
```

### Git Verification Commands
```bash
# Check git status
git status

# Verify staged changes
git diff --staged

# Check commit history
git log --oneline -5

# Verify remote
git remote -v
```

## Common Workflows

### File Save Workflow
1. Write file using write tool
2. Immediately verify with `ls -la [directory]`
3. If verification fails, check path and retry
4. Confirm success to user

### Git Commit Workflow
1. Make changes and stage with `git add`
2. Verify with `git status` and `git diff --staged`
3. Commit with proper message format
4. Verify commit with `git log -1`
5. Push with verification

### Code Change Workflow
1. Read existing code to understand patterns
2. Make changes following project conventions
3. Test changes if test infrastructure exists
4. Verify changes don't break existing functionality
5. Document changes in commit message

## Priority Rules

1. **Security**: Security issues take highest priority
2. **File verification**: Always verify file operations
3. **Testing**: Test changes before committing
4. **Documentation**: Document significant changes
5. **Code quality**: Maintain code quality standards

## Error Recovery

### File Operation Failures
- Check file permissions
- Verify directory existence
- Check disk space
- Verify path correctness (especially cross-platform)

### Git Operation Failures
- Check network connectivity
- Verify authentication
- Check branch status
- Resolve conflicts if needed

### Build Failures
- Check dependency installation
- Verify configuration
- Check for syntax errors
- Review build logs for specific errors

## Continuous Improvement

### Rule Updates
- Update this file when new patterns are discovered
- Add rules for new tools or technologies
- Remove outdated rules
- Learn from past mistakes and add preventive rules

### Knowledge Sharing
- Document learned patterns in this file
- Share successful workflows
- Note common pitfalls and solutions
- Keep rules updated with project evolution