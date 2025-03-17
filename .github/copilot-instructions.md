# Copilot Instructions

## Commit Message Guidelines

All commit messages should follow the format defined in `.gitmessage`. Messages must be written in English and use one of the following prefixes:

### Available Prefixes

- `feat:` - A new feature

  - Example: `feat: add quantum circuit visualization`

- `fix:` - A bug fix

  - Example: `fix: resolve qubit allocation issue`

- `docs:` - Documentation only changes

  - Example: `docs: update API reference`

- `style:` - Changes that do not affect the meaning of the code

  - Example: `style: format quantum gate definitions`

- `refactor:` - A code change that neither fixes a bug nor adds a feature

  - Example: `refactor: restructure backend implementation`

- `test:` - Adding missing or correcting existing tests

  - Example: `test: add unit tests for quantum operations`

- `ci:` - Changes to CI configuration files and scripts

  - Example: `ci: update GitHub Actions workflow`

- `chore:` - Updating grunt tasks etc; no production code change
  - Example: `chore: update dependencies`

### Message Structure

```plaintext
<type>: <description>

[optional body]

[optional footer]
```

- Description should be clear and concise
- Use imperative mood in the description ("add" not "added" or "adds")
- Body and footer are optional but should provide context when needed
- Line length should not exceed 72 characters
