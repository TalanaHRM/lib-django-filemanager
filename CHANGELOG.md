# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-11-26

Fixes found while testing 1.0.0 in a QA environment (Jira: TM-817). All of them come from the original code
(`re.match(...).group(0)` and unchecked file operations, present since the first commit in 2014), not from the
1.0.0 changes.

### Fixed

- A name or path whose first character is outside the allowed set (`@`, `<`, `=`, `[`, `~`, `{` and others)
  made `handle_form` and `download` fail with `AttributeError: 'NoneType' object has no attribute 'group'`
  and an HTTP 500. It now answers the usual "Invalid path", "Invalid folder name", "Invalid file name" or
  "File name is not valid" message. An empty `path` answers "Invalid path" too.
- `download` raises `Http404` for a file or a folder that does not exist, or that is the other kind (a folder
  requested as a file), instead of failing with an HTTP 500. An unknown download mode answers HTTP 400.
- Renaming a file or a folder to the name of one that already exists no longer replaces it silently: it answers
  "... already exists" and keeps both. Renaming to its own name is still accepted.
- Uploading an empty file now answers "File is empty : <name>". Before, the form rejected it without any
  message and the user saw nothing. `FileManagerForm.ufile` accepts empty files (`allow_empty_file=True`) so the
  message can be produced; an empty file is never stored.

## [1.0.0] - 2026-11-25

First release maintained by Talana at `TalanaHRM/lib-django-filemanager`. It is based on the
`talana-cl/django-filemanager` fork (0.0.3), which is itself a fork of
[IMGIITRoorkee/django-filemanager](https://github.com/IMGIITRoorkee/django-filemanager). It is a major
release because the supported versions change and some behaviour that was unsafe or broken now differs.
Jira: TM-815, TM-817.

### Changed (breaking)

- Requires Python 3.8 or newer and Django 4.2 or newer (`django>=4.2`). Before, the README listed Python 2.7 to
  3.7 and Django 1.8 and 1.11, and nothing enforced it. Tested with Django 4.2, 5.2 and 6.1.
- A path that points outside the base folder is rejected: the form actions answer "Invalid path" and `media`
  and `download` raise `Http404`. Symbolic links that leave the base folder are treated the same way.
- An upload name must be a single file name: names with a folder part (`sub/a.png`) or an absolute path are
  rejected with "File name is not valid".
- `extensions=None` now accepts every extension, as the README always said. Before, uploading or unzipping a
  file with `extensions=None` raised an error.
- "Unexpected error" messages no longer include the exception text. The exception is logged with
  `logging.getLogger("filemanager")`.
- `CKEditorWidget.render(name, value, attrs=None, renderer=None)` follows the current Django widget API, and
  `CKEditorWidget(attrs=None, config=None, filemanager_url='')` no longer shares a mutable default.

### Fixed

- Thumbnails returned HTTP 500 on Pillow 10 or newer (`Image.ANTIALIAS` was removed and `Image.resize` needs
  integer sizes). They use `Image.LANCZOS` with integer sizes.
- A corrupt image, a decompression bomb or a non-image file served by `media` shows the icon of its extension
  instead of a 500.
- Path traversal: `delete`, `move`, `copy`, `download`, `media` and `unzip` could read, write or delete files
  outside the base folder with `..` in the path. `unzip` now also skips members whose real path leaves the
  destination folder, for example through a symbolic link.
- The file manager no longer calls `os.chdir`, which changed the working directory of the whole process and was
  not safe with threads.
- Cross-site scripting: directory names, file names and messages were written into the page with `|safe` and
  `.html()`. The template uses `json_script`, the script escapes names and uses `.text()`, and the CKEditor
  widget escapes its configuration (`<`, `>`, `&`).
- `Content-Disposition` of downloads is built with `django.utils.http.content_disposition_header`, so names with
  spaces or non-ASCII letters are quoted correctly.
- An upload name that carries a path could write outside the target folder. Reported by Aikido as
  "Potential file inclusion attack via reading file" (CWE-23).

### Added

- A pytest suite of 25 tests (`tests/`) that runs without a project or a database.
- `pyproject.toml` and `uv.lock` so that `uv` and dependency scanners can resolve the dependency tree.
  Packaging is still defined in `setup.py`.
- `.github/CODEOWNERS`: changes need the approval of IT-Managers or Tech Leads - Principals.
- `CHANGELOG.md`.

### Removed

- The old sample Django project in `tests/` (`manage.py`, `settings.py`, `urls.py`, `views.py`, `tests.py`) and
  `runtests.py`, replaced by the pytest suite.
- `.travis.yml` (Python 2.7 and Django 1.7) and `requirements-test.txt`. Development tools are now the `dev`
  dependency group of `pyproject.toml`; `coveralls` and `responses` were not used and are gone.
- The GitHub workflows `ai-review.yml` and `cleanup-branch.yml`: the repository is public and cannot call the
  reusable workflows of the private `platform-ci-workflows` repository.

## [0.0.3] - 2021-04-20

Fork `talana-cl/django-filemanager`: the Django requirement is no longer pinned and the static files are
included in the package.

## [0.0.1] - 2019-01-21

Last release of the upstream project (`IMGIITRoorkee/django-filemanager`): Python 3 and Django 1.11 support.

[1.0.0]: https://github.com/TalanaHRM/lib-django-filemanager/releases/tag/v1.0.0
