# Repository Guidelines

## Project Structure & Module Organization
This repository is currently minimal, with no committed application code or tooling visible in the workspace. Keep new work organized from the start:

- `src/` for application code
- `tests/` for automated tests
- `assets/` for static files such as images or fixtures
- `docs/` for design notes or architecture decisions

Prefer small, focused modules. Group related code by feature or domain, and keep tests close in intent to the code they validate.

## Build, Test, and Development Commands
No standard build or test commands are defined yet. When adding tooling, expose a small, predictable command set and document it here. Recommended baseline:

- `npm install` to install dependencies
- `npm run dev` to start local development
- `npm test` to run the test suite
- `npm run build` to produce a production build

If the project uses Python instead, mirror the same intent with commands such as `python -m pytest` and a documented entry point.

## Coding Style & Naming Conventions
Use 2 spaces for front-end files and 4 spaces for Python. Match the formatter configured for the language you introduce. Prefer:

- `PascalCase` for classes and React components
- `camelCase` for variables and functions
- `kebab-case` for file names in JavaScript or TypeScript projects
- `snake_case` for Python modules

Add linting and formatting early, such as ESLint and Prettier for JS/TS or Ruff and Black for Python.

## Testing Guidelines
Create tests alongside new features rather than deferring them. Use file names that mirror the source, for example `tests/auth.test.ts` or `tests/test_auth.py`. Cover core flows, edge cases, and regressions for every bug fix. Do not merge work that lacks a reproducible way to verify behavior locally.

## Commit & Pull Request Guidelines
No Git history is available in this workspace, so follow a clear default convention: short, imperative commit messages such as `feat: add chat session storage` or `fix: handle empty prompt input`.

Pull requests should include:

- a concise summary of the change
- testing notes with exact commands run
- linked issue or task reference when available
- screenshots or sample output for UI or CLI changes

## Configuration & Security
Do not commit secrets, tokens, or local `.env` files. Provide a sanitized `.env.example` when configuration is required, and document any required environment variables before introducing them.
