# recruitZaa Backend Development Guidelines

Welcome to the recruitZaa backend repository. To ensure maintainability, code quality, and security across our Python/FastAPI services, all developers must adhere to these guidelines.

---

## 1. Git Workflow & Branching Strategy

We use a structured branch naming strategy to keep git history organized.

### Branch Naming Conventions
* **Features:** `feature/be-<short-description>` (e.g., `feature/be-resume-parser`)
* **Bug Fixes:** `bugfix/be-<short-description>` (e.g., `bugfix/be-otp-rate-limit`)
* **Hotfixes:** `hotfix/be-<short-description>` (e.g., `hotfix/be-token-leak`)
* **Chore/Docs:** `chore/be-<short-description>` or `docs/be-<short-description>`

---

## 2. Commit Message Rules (Conventional Commits)

Commit messages must follow the **Conventional Commits** specification. The commit format is:
`type(scope): description`

### Allowed Types:
* `feat`: A new feature (e.g., `feat(api): add resume parsing endpoint`)
* `fix`: A bug fix (e.g., `fix(auth): fix OTP expiry calculation`)
* `docs`: Documentation changes only (e.g., `docs(contributing): update backend setup guide`)
* `style`: Code style changes (whitespace, formatting) that don't affect logic.
* `refactor`: Code changes that neither fix a bug nor add a feature.
* `test`: Adding or correcting tests.
* `chore`: Updating build tasks, dependencies, etc.

> **Note:** Violating commit formats will trigger a pre-commit block via the `conventional-pre-commit` hook.

---

## 3. Naming Conventions

* **Variables & Functions:** Use `snake_case` (PEP 8 compliant, e.g., `calculate_match_score`, `user_id`).
* **Classes:** Use `PascalCase` (e.g., `ResumeParserService`, `UserModel`).
* **Constants:** Use `UPPER_CASE` with snake_case separators (e.g., `OTP_EXPIRY_MINUTES`).
* **REST API Endpoints:** Use lowercase-with-hyphens (e.g., `/api/v1/job-postings`, `/api/v1/ai-mock-interviews`).

---

## 4. Linting & Formatting (Checkstyle)

We use **Ruff** for extremely fast linting and formatting.

* Codes are formatted automatically using Ruff during git pre-commit checks.
* Run the following commands to check manually:
  ```bash
  ruff check .        # Lint check
  ruff check --fix .  # Auto-fix linting issues
  ruff format .       # Format all python files
  ```

---

## 5. Setup Git Hooks (Pre-commit)

To activate local git validation, initialize `pre-commit`:
```bash
pip install pre-commit
pre-commit install --install-hooks
```
This ensures trailing whitespaces, EOF issues, YAML structures, formatting, linting, and commit messages are validated before every commit.
