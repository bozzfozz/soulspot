# SoulSpot Documentation

> **Version:** 1.0  
> **Last Updated:** 2025-11-17

---

## 📁 Documentation Structure

This documentation is organized by purpose to help you find what you need quickly.

```
docs/
├── project/          # Project-level documentation
├── guides/           # User and developer guides
│   ├── user/        # End-user documentation
│   └── developer/   # Developer documentation
├── api/             # API reference documentation
├── development/     # Development roadmaps and guidelines
├── implementation/  # Implementation details and guides
├── history/         # Historical records of implementations
└── archived/        # Archived and outdated documentation
```

---

## 🚀 Quick Start

### For Users
New to SoulSpot? Start here:
1. [Setup Guide](guides/user/setup-guide.md) - Installation and configuration
2. [User Guide](guides/user/user-guide.md) - How to use all features
3. [Troubleshooting](guides/user/troubleshooting-guide.md) - Common issues and solutions

### For Developers
Contributing to SoulSpot? Start here:
1. [Architecture](project/architecture.md) - System design and structure
2. [Contributing Guide](project/contributing.md) - How to contribute
3. [Testing Guide](guides/developer/testing-guide.md) - Writing and running tests

### For Operators
Deploying or maintaining SoulSpot? Start here:
1. [Deployment Guide](guides/developer/deployment-guide.md) - Production deployment
2. [Operations Runbook](guides/developer/operations-runbook.md) - Day-to-day operations
3. [Observability Guide](guides/developer/observability-guide.md) - Monitoring and logging

---

## 📚 Documentation Sections

### Project Documentation (`project/`)
Core project information and guidelines:
- **[CHANGELOG](project/CHANGELOG.md)** - Version history and release notes
- **[Architecture](project/architecture.md)** - System architecture and design
- **[Contributing](project/contributing.md)** - Contribution guidelines

### User Guides (`guides/user/`)
End-user documentation:
- **[Setup Guide](guides/user/setup-guide.md)** - Installation and initial setup
- **[User Guide](guides/user/user-guide.md)** - Complete feature walkthrough
- **[Advanced Search Guide](guides/user/advanced-search-guide.md)** - Search tips and tricks
- **[Troubleshooting Guide](guides/user/troubleshooting-guide.md)** - Problem resolution

### Developer Guides (`guides/developer/`)
Technical documentation for developers:

**Development**
- **[Testing Guide](guides/developer/testing-guide.md)** - Test strategies and execution
- **[Deployment Guide](guides/developer/deployment-guide.md)** - Deployment procedures
- **[Operations Runbook](guides/developer/operations-runbook.md)** - Operational procedures
- **[Observability Guide](guides/developer/observability-guide.md)** - Logging and monitoring

**UI/UX Development**
- **[Component Library](guides/developer/component-library.md)** - Reusable UI components
- **[Design Guidelines](guides/developer/design-guidelines.md)** - Design system and patterns
- **[HTMX Patterns](guides/developer/htmx-patterns.md)** - HTMX integration patterns
- **[Style Guide](guides/developer/soulspot-style-guide.md)** - CSS and styling conventions
- **[Visual Guide](guides/developer/ui-ux-visual-guide.md)** - Visual component showcase
- **[Keyboard Navigation](guides/developer/keyboard-navigation.md)** - Accessibility shortcuts

**Dashboard Development**
- **[Dashboard Developer Guide](guides/developer/dashboard-developer-guide.md)** - Dashboard system overview
- **[Widget Development Guide](guides/developer/widget-development-guide.md)** - Creating custom widgets
- **[GridStack Quick Reference](guides/developer/gridstack-page-builder-quick-ref.md)** - Page builder reference
- **[Page Reference](guides/developer/page-reference.md)** - Page structure and components

**Release Management**
- **[Release Quick Reference](guides/developer/release-quick-reference.md)** - Release process overview

### API Documentation (`api/`)
REST API reference:
- **[API Overview](api/README.md)** - API introduction and conventions
- **[Advanced Search API](api/advanced-search-api.md)** - Search endpoint documentation
- **[Library Management API](api/library-management-api.md)** - Library operations
- **[Download Management](api/download-management.md)** - Download queue management

**Interactive Documentation:**
- Swagger UI: http://localhost:8765/docs
- ReDoc: http://localhost:8765/redoc

### Development Documentation (`development/`)
Development planning and guidelines:
- **[Backend Roadmap](development/backend-roadmap.md)** - Backend development plan
- **[Frontend Roadmap](development/frontend-roadmap.md)** - Frontend development plan
- **[CI/CD](development/ci-cd.md)** - Continuous integration and deployment
- **[Design Guidelines](development/design-guidelines.md)** - Design principles
- **[Performance Optimization](development/performance-optimization.md)** - Performance best practices

### Implementation Documentation (`implementation/`)
Detailed implementation guides:
- **[Dashboard Implementation](implementation/dashboard-implementation.md)** - Dashboard system details
- **[Onboarding UI Implementation](implementation/onboarding-ui-implementation.md)** - Onboarding flow
- **[Onboarding UI Overview](implementation/onboarding-ui-overview.md)** - Onboarding design
- **[Onboarding Visual Guide](implementation/onboarding-ui-visual-guide.md)** - Onboarding visuals

**Feature Implementations** (`implementation/features/`)
- **[Circuit Breaker](implementation/features/circuit-breaker.md)** - Circuit breaker pattern
- **[Feature Ideas](implementation/features/soulspot-ideas.md)** - Planned features

### History (`history/`)
Historical implementation records - see [History README](history/README.md) for details.

### Archived (`archived/`)
Outdated or superseded documentation - see [Archived README](archived/README.md) for details.

---

## 🔍 Finding What You Need

### By Role

**I'm a new user** → Start with [Setup Guide](guides/user/setup-guide.md) and [User Guide](guides/user/user-guide.md)

**I'm a developer** → Check [Architecture](project/architecture.md) and [Contributing Guide](project/contributing.md)

**I'm deploying to production** → See [Deployment Guide](guides/developer/deployment-guide.md)

**I'm troubleshooting an issue** → Try [Troubleshooting Guide](guides/user/troubleshooting-guide.md)

**I'm building a custom widget** → Read [Widget Development Guide](guides/developer/widget-development-guide.md)

**I need API documentation** → Browse [API Documentation](api/)

### By Topic

**Setup & Configuration**
- [Setup Guide](guides/user/setup-guide.md)
- [Deployment Guide](guides/developer/deployment-guide.md)

**Using Features**
- [User Guide](guides/user/user-guide.md)
- [Advanced Search Guide](guides/user/advanced-search-guide.md)

**Development**
- [Architecture](project/architecture.md)
- [Backend Roadmap](development/backend-roadmap.md)
- [Frontend Roadmap](development/frontend-roadmap.md)
- [Testing Guide](guides/developer/testing-guide.md)

**UI/UX**
- [Component Library](guides/developer/component-library.md)
- [Design Guidelines](guides/developer/design-guidelines.md)
- [Style Guide](guides/developer/soulspot-style-guide.md)
- [HTMX Patterns](guides/developer/htmx-patterns.md)

**Operations**
- [Operations Runbook](guides/developer/operations-runbook.md)
- [Observability Guide](guides/developer/observability-guide.md)
- [CI/CD Documentation](development/ci-cd.md)

**Dashboard & Widgets**
- [Dashboard Implementation](implementation/dashboard-implementation.md)
- [Dashboard Developer Guide](guides/developer/dashboard-developer-guide.md)
- [Widget Development Guide](guides/developer/widget-development-guide.md)

---

## 📝 Documentation Standards

All documentation in this repository follows these standards:

### Format
- All documentation is in Markdown format
- Files use `.md` extension
- Use descriptive filenames with hyphens (e.g., `setup-guide.md`)

### Structure
- Every document starts with a title (H1)
- Include version and last updated date at the top
- Use clear headings and subheadings
- Add a table of contents for long documents

### Versioning
- All documentation references **version 1.0**
- No version prefixes in filenames (no v1.0, v2.0)
- Historical versions are in `archived/` directory

### Links
- Use relative links within documentation
- Link to related documentation where appropriate
- Verify links work before committing

---

## 🤝 Contributing to Documentation

Documentation improvements are always welcome! 

- Fix typos or unclear explanations
- Add missing information
- Improve examples and code snippets
- Update outdated content

See the [Contributing Guide](project/contributing.md) for details on how to submit documentation changes.

---

## ❓ Getting Help

Can't find what you're looking for?

1. Check the [Troubleshooting Guide](guides/user/troubleshooting-guide.md)
2. Search the documentation using your IDE or text editor
3. Open an issue on GitHub with the question
4. Check existing GitHub issues for similar questions

---

**SoulSpot version 1.0** - Complete documentation for a complete music automation platform.
