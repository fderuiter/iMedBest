# Contributor & Issue Management Guide

Welcome to the **iMedBest** development team! To maintain high engineering velocity, code cleanliness, and flawless team communication, all contributors must strictly follow the guidelines detailed below.

---

## 🛠️ 1. Code Quality & Formatting Guardrails

We enforce strict automated formatting and lint checks using **Ruff** (written in Rust, runs in microseconds).

### Configuration Guidelines
* **Line Length Limit:** 120 characters maximum.
* **Quote Style:** Double quotes (`"`) for strings.
* **Indent Style:** Spaces (4 spaces per indent).

### Pre-commit Git Hooks
Before committing any changes, you must activate the local git hooks to format and lint your code automatically:
```bash
# Install pre-commit globally or inside your uv environment
uv run pre-commit install
```
On every `git commit`, the hooks will automatically run Ruff checks and formatters. If logical issues are detected, the commit will be blocked until resolved.

---

## 🐛 2. Anatomy of a Great GitHub Issue

Issues are our primary **team communication tools**. A great issue minimises back-and-forth, providing all details needed to understand and resolve the task.

Whenever you create a new issue on GitHub, select from our three pre-configured templates:
1. **🐛 Bug Report Template**
2. **✨ Feature Request Template**
3. **🛠️ Technical Task / Chore Template**

### Essential Principles for Issue Creation

#### 1. Clear, Prefix-Based Titles
Titles must act like headlines, conveying the category, location, and nature of the task clearly:
* **Bad:** `It's broken` or `Error on dashboard`
* **Good:** `[Bug] Token expiration causes 500 error on Dashboard`
* **Great:** `[Bug] Profile View: User-names with hyphens fail character validations`

#### 2. Clear Context & "Why" (User Impact)
State the business or clinical impact before technical details. Explain why this issue matters to operators:
> *"Users are unable to save their profile changes if they have a hyphen in their last name, preventing clinical staff from completing onboarding during fast shifts."*

#### 3. Expected vs. Actual Behavior
Eliminate all ambiguity about what constitutes a bug vs. a feature request:
* **Expected:** The form submits successfully, returns a `200 OK`, updates the database, and shows a success toast.
* **Actual:** The UI freezes, the browser console shows an unhandled JSON validation exception, and the network tab returns a `422 Unprocessable Entity` error.

#### 4. Environment & Technical Details
Always specify the exact technical parameters of the environment:
* **OS/Browser:** macOS Sonoma, Chrome v124
* **Version/Commit:** v0.1.0 or commit hash `8a3f2b1`
* **Environment:** Local Dev (Docker Compose) / Staging / Production

#### 5. Logs & Code Snippets
Format stack traces or code examples clearly using markdown code blocks:
```typescript
TypeError: Cannot read properties of undefined (reading 'map')
    at ProfileComponents.tsx:42:18
```

---

## ⛓️ 3. GitHub Native Project Management & Automation

To minimize administrative overhead and keep our backlog dynamically synchronized with our codebase, we strictly leverage GitHub's native issue ecosystems.

### 1. Native Sub-Issues Hierarchy (Parent-Child)
* **The Rule:** Do not use plain Markdown checklists (`- [ ]`) in the description to track sub-tasks. Use GitHub's native **Sub-Issues** framework.
* **Benefits:**
  * Displays an active progress bar indicating completion rollups in issue lists.
  * Allows nesting up to eight levels deep and linking up to 100 sub-issues.
  * Each sub-issue operates as a fully featured entity with distinct assignees, milestones, labels, and discussion threads.

### 2. Native Issue Dependencies & Blockers
* **The Rule:** For linear workflows (such as sequential sync implementation in Epic 2), declare blockers natively using GitHub's **Issue Dependencies** metadata.
* **Benefits:**
  * Visibly flags the blocked state inside the GitHub UI.
  * Automatically warns developers and reviewers against opening or merging Pull Requests while upstream blockers remain open.

### 3. Git & PR Lifecycle Automation (Closing Keywords)
* **The Rule:** Always link your Pull Requests to their corresponding issues using active closing keywords in the PR description:
  * `Fixes #123`, `Closes #123`, or `Resolves #123`.
* **Benefits:** Automatically closes and transitions the target issue to the "Closed" state the millisecond the PR merges into the default branch (`main` or `develop`).

### 4. Issue Types vs. Labels
* **The Rule:** Categorize the architectural intent of the task using native **Issue Types** (Bug, Feature, Chore) instead of fluid ad-hoc labels.
* **Benefits:** Integrates directly with our GitHub Project Boards to populate Kanban iteration sprints, chart velocity, and automate burndown metrics based on sub-issue rollups.

---

## 🚀 4. Sync Pipeline Dependency Flow

When working on active database sync issues (Epic 2), ensure that migrations and sync scripts are executed in their logical relational order to prevent Foreign Key constraints failures:

```text
Level 1: Studies -> Sites (Independent Globals)
Level 2: Subjects -> Forms -> Intervals -> Users (Core Clinical Structures)
Level 3: Variables -> Visits (Operational Properties)
Level 4: Records -> (Codings, Queries, RecordRevisions) -> Jobs (Data Capture Layer)
```

---

## 📡 5. Clinical Agent Data Signaling (Sync Integrity Framework)

When developing a new clinical data integration agent (e.g., integrating a new EDC provider or API), the agent must handle asynchronous/partial synchronization natively to maintain 100% data integrity.

### Strict Signaling Protocols
If an agent successfully processes a record but discovers that a **parent record** required for database persistence has not yet been synced (e.g., receiving a Subject when the Site hasn't been synced):
* **Do NOT** throw an unhandled exception or fail the job outright.
* **Do NOT** return a silent success (e.g., 200 OK or generic object).
* **MUST** explicitly return a `202` HTTP status tuple signaling that the data has been securely stored in the temporary buffer and is awaiting its parent dependencies:

```python
# Mandatory Buffered Return Pattern for Agents
return 202, {"message": "Buffered due to missing parent"}
```

Returning this signal safely transitions the orchestrator task to the `BUFFERED` state, securely holding the data and automatically preventing downstream child orchestration (e.g., visits or labs) until the required parent data arrives.

The Sync Integrity Framework handles auto-resolution, task resumption, and compliance audit logging automatically.
