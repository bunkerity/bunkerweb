# OCSP Plugin UI Documentation Index

## Overview

Comprehensive documentation for the OCSP (Online Certificate Status Protocol) stapling plugin UI in BunkerWeb, including inline code documentation, configuration guides, and architecture documentation.

**Last Updated**: 2026-09-30  
**Documentation Version**: 1.0

---

## Quick Navigation

### For End Users
- **[UI_PAGES.md](UI_PAGES.md)** - User guide for all OCSP UI pages
- **[OCSP_STAPLING_GUIDE.md](OCSP_STAPLING_GUIDE.md)** - Configuration best practices and troubleshooting

### For Developers
- **[UI_ARCHITECTURE.md](UI_ARCHITECTURE.md)** - Code structure and extension points
- **[Inline Documentation](#inline-code-documentation)** - Docstrings in Python files

---

## Documentation Files

### 1. UI_PAGES.md
**Purpose**: User-facing guide to all OCSP plugin UI pages  
**Audience**: System administrators, operators  
**Content**:
- Overview of three main pages (/plugins/ocsp, /ocsp, /ocsp/settings)
- Detailed description of each page's components
- User workflows and common tasks
- API endpoint documentation
- Troubleshooting section
- Security notes

**Key Sections**:
- Pages and Routes
- Time Display Formats
- User Workflows
- API Endpoints
- Security Notes

---

### 2. OCSP_STAPLING_GUIDE.md
**Purpose**: Comprehensive guide to OCSP stapling concepts and configuration  
**Audience**: Operators, security engineers, compliance teams  
**Content**:
- OCSP stapling explanation and benefits
- BunkerWeb architecture overview
- Configuration hierarchy and options
- Best practices for different scenarios
- Detailed explanation of each OCSP staple mode
- Common issues and solutions
- Monitoring and maintenance guidelines
- Glossary of terms

**Key Sections**:
- What is OCSP Stapling?
- BunkerWeb OCSP Implementation
- Configuration Best Practices
- OCSP Staple Modes Explained
- Common Issues and Solutions
- Monitoring and Maintenance
- Troubleshooting Guide

**Configuration Scenarios Covered**:
- Recommended for most users
- High-traffic deployments (10,000+ req/s)
- High-security requirements
- Testing/development environments

---

### 3. UI_ARCHITECTURE.md
**Purpose**: Technical documentation of OCSP UI code architecture  
**Audience**: Developers, contributors  
**Content**:
- Directory structure overview
- Architecture components breakdown
- Flask blueprint organization
- Helper functions documentation
- Template architecture and data flow
- Database integration
- Security architecture
- Extension points for customization
- Code quality standards
- Testing guidelines
- Performance considerations
- Future enhancement suggestions

**Key Sections**:
- Directory Structure
- Architecture Components
  - Flask Blueprint (ocsp.py)
  - Status Card Display (actions.py)
  - Templates (HTML/Jinja2)
  - Database Integration
  - Security Architecture
- Extension Points
- Code Quality Standards
- Testing Checklist
- Future Enhancements

**Component Details**:
- 4 main HTTP routes with full documentation
- 6 helper functions with detailed docstrings
- 2 main templates with data flow explanation
- Security implementation details
- Extension mechanisms for new features

---

## Inline Code Documentation

### Python Files

#### blueprints/ocsp.py
**Module Documentation**:
- Module-level docstring explaining purpose and capabilities
- Auto-discovery mechanism
- Blueprint naming and URL structure

**Functions Documented**:
1. `format_datetime(dt)` - Format datetime for display
2. `calculate_remaining_time(end_time)` - Human-readable remaining time
3. `get_certificate_info(service)` - Extract certificate timing info
4. `get_services_ocsp_status()` - Retrieve OCSP config for all services
5. `ocsp_overview()` - Status overview page route
6. `ocsp_settings()` - Settings configuration page route
7. `fetch_ocsp_responses()` - Fetch new OCSP responses endpoint
8. `get_service_status()` - Service status API endpoint

**Docstring Format**:
- Summary line
- Detailed description
- Args section with types
- Returns section with format
- Example outputs for API endpoints

#### actions.py
**Module Documentation**:
- Purpose: Status card display for plugin page
- Auto-calling mechanism via pre_render hook
- Dependency injection via kwargs

**Functions Documented**:
1. `pre_render(**kwargs)` - Generate status card data
   - Comprehensive docstring
   - Args explanation
   - Returns format
   - Card types and properties

### HTML Templates

#### ocsp_overview.html
**Inline Comments**:
- Section headers marking major page sections
- Form/table organization comments
- JavaScript function documentation
- HTML escape function documentation

#### ocsp_settings.html
**Inline Comments**:
- Tab structure comments
- Form section documentation
- Modal functionality comments
- JavaScript event handler comments

---

## Documentation Standards

### Python Docstring Format

All Python functions follow comprehensive docstring format:

```python
def function_name(param1, param2):
    """
    Short one-line description.
    
    Longer multi-paragraph description explaining:
    - What the function does
    - Key behaviors
    - Important side effects
    
    Args:
        param1 (type): Description
        param2 (type): Description
        
    Returns:
        type: Description of return value
        
    Examples:
        >>> function_name("input")
        "output"
    """
```

### Code Comments

- Comments explain "why", not "what"
- Inline comments for non-obvious logic
- Avoid redundant comments (code should be self-documenting)
- Use comments to mark major sections

### Security Documentation

- All security-relevant code has comments
- Input validation documented
- Output escaping marked
- Authentication/authorization checkpoints noted

---

## Code Organization

### Module Structure

```
ocsp/ui/
├── actions.py
│   └── pre_render() - Status card display
│
└── blueprints/
    ├── ocsp.py - All routes and business logic
    │   ├── format_datetime()
    │   ├── calculate_remaining_time()
    │   ├── get_certificate_info()
    │   ├── get_services_ocsp_status()
    │   ├── ocsp_overview()
    │   ├── ocsp_settings()
    │   ├── fetch_ocsp_responses()
    │   └── get_service_status()
    │
    └── templates/
        ├── ocsp_overview.html - Status dashboard
        └── ocsp_settings.html - Configuration UI
```

### Function Categories

**Display/Formatting Functions**:
- `format_datetime()` - Timestamp formatting
- `calculate_remaining_time()` - Duration calculation

**Data Retrieval Functions**:
- `get_certificate_info()` - Certificate parsing
- `get_services_ocsp_status()` - Service configuration retrieval

**Route Handlers** (Flask endpoints):
- `ocsp_overview()` - GET /ocsp
- `ocsp_settings()` - GET /ocsp/settings
- `fetch_ocsp_responses()` - POST /ocsp/fetch-responses
- `get_service_status()` - GET /ocsp/service-status

**Template Functions**:
- `pre_render()` - Status card generation

---

## Documentation Maintenance

### Update Checklist

When adding new features:

- [ ] Add function docstring (Args, Returns, Description)
- [ ] Add inline comments for complex logic
- [ ] Update UI_ARCHITECTURE.md if adding routes/functions
- [ ] Update UI_PAGES.md if adding user-facing features
- [ ] Update code examples in documentation
- [ ] Add API endpoint documentation if applicable

### Documentation Standards Verification

Run these checks:

```bash
# Check Python file has module docstring
grep -n "^\"\"\"" src/common/core/ocsp/ui/blueprints/ocsp.py

# Check all functions have docstrings
grep -n "^def " src/common/core/ocsp/ui/blueprints/ocsp.py
grep -n "\"\"\"" src/common/core/ocsp/ui/blueprints/ocsp.py

# Check for undocumented parameters
# (manual review)
```

---

## Related Documentation

**BunkerWeb Main Documentation**: https://docs.bunkerweb.io  
**OCSP Concepts**: See OCSP_STAPLING_GUIDE.md  
**SSL Plugin Settings**: See `/src/common/core/ssl/plugin.json`  
**Global Settings**: Navigate to `/global-settings` in UI  
**Service Configuration**: Navigate to `/services/<name>` in UI

---

## Contact & Support

For documentation issues:
1. Check if answer exists in one of the markdown files above
2. Review code comments and docstrings
3. Check troubleshooting section in OCSP_STAPLING_GUIDE.md
4. File issue on GitHub with `[docs]` prefix

---

## Version History

### v1.0 (2026-09-30)
- Initial documentation set created
- Covers all UI pages and features
- Inline code documentation added
- Troubleshooting guide included
- Best practices documented

---

## Quick Reference

### Most Common Tasks

| Task | Documentation | Quick Link |
|------|---|---|
| Enable OCSP stapling | UI_PAGES.md | Workflow 2 |
| Troubleshoot missing OCSP | OCSP_STAPLING_GUIDE.md | Common Issues |
| Add new route | UI_ARCHITECTURE.md | Adding New Routes |
| Configure for high traffic | OCSP_STAPLING_GUIDE.md | High-Traffic Config |
| Understand architecture | UI_ARCHITECTURE.md | Architecture Components |

### Code Entry Points

```python
# Main blueprint file
src/common/core/ocsp/ui/blueprints/ocsp.py

# Status card display
src/common/core/ocsp/ui/actions.py

# Templates
src/common/core/ocsp/ui/blueprints/templates/ocsp_overview.html
src/common/core/ocsp/ui/blueprints/templates/ocsp_settings.html
```

### Key Configuration Files

```
src/common/core/ocsp/plugin.json          # OCSP plugin settings
src/common/core/ssl/plugin.json           # SSL/OCSP stapling settings
```

---

**Documentation Complete** ✓

All OCSP plugin UI components are documented with comprehensive inline documentation and supporting guides.
