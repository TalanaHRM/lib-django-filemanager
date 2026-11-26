"""Thumbnails on current Pillow, paths confined to the upload root and no process-wide chdir."""

import io
import os

import pytest
from django.http import Http404
from django.template.loader import render_to_string
from PIL import Image

from filemanager import FileManager, FileManagerForm


@pytest.fixture
def root(tmp_path):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (tmp_path / "outside.txt").write_text("secret")
    Image.new("RGB", (10, 10), "red").save(tmp_path / "outside.png")
    return uploads


@pytest.fixture
def manager(root):
    return FileManager(str(root), extensions=["png", "jpg", "jpeg", "txt"])


@pytest.fixture
def keep_cwd():
    before = os.getcwd()
    yield before
    os.chdir(before)


def _form(**data):
    data.setdefault("file_or_dir", "file")
    data.setdefault("current_path", "/")
    form = FileManagerForm(data)
    assert form.is_valid(), form.errors
    return form


def _size(response):
    with Image.open(io.BytesIO(response.content)) as image:
        return image.size


def test_media_returns_a_scaled_thumbnail(manager, root):
    Image.new("RGB", (200, 100), "red").save(root / "wide.png")

    response = manager.media("wide.png")

    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert _size(response) == (60, 30)


def test_media_keeps_a_small_image_size(manager, root):
    Image.new("RGB", (40, 20), "red").save(root / "small.png")

    assert _size(manager.media("small.png")) == (40, 20)


@pytest.mark.parametrize("path", ["../outside.png", "a/../../outside.png"])
def test_media_rejects_a_path_outside_the_root(manager, path):
    with pytest.raises(Http404):
        manager.media(path)


def test_media_rejects_a_symlink_that_points_outside_the_root(manager, root):
    (root / "link.png").symlink_to(root.parent / "outside.png")

    with pytest.raises(Http404):
        manager.media("link.png")


@pytest.mark.parametrize("file_or_dir, path", [("file", "../outside.txt"), ("dir", "../")])
def test_download_rejects_a_path_outside_the_root(manager, file_or_dir, path):
    with pytest.raises(Http404):
        manager.download(path, file_or_dir)


def test_download_serves_a_file_inside_the_root(manager, root):
    (root / "notes.txt").write_text("hello")

    response = manager.download("notes.txt", "file")

    assert response.content == b"hello"


def test_delete_rejects_a_path_outside_the_root(manager, root, keep_cwd):
    messages = manager.handle_form(_form(action="delete", path="/../outside.txt"), files=None)

    assert (root.parent / "outside.txt").exists()
    assert any("Invalid path" in message for message in messages)


def test_move_rejects_a_destination_outside_the_root(manager, root, keep_cwd):
    (root / "notes.txt").write_text("hello")

    messages = manager.handle_form(
        _form(action="move", path="/notes.txt", current_path="/../"), files=None
    )

    assert (root / "notes.txt").exists()
    assert not (root.parent / "notes.txt").exists()
    assert any("Invalid path" in message for message in messages)


def test_add_folder_creates_it_without_changing_the_working_directory(manager, root, keep_cwd):
    messages = manager.handle_form(
        _form(action="add", path="/", name="docs", file_or_dir="dir"), files=None
    )

    assert (root / "docs").is_dir()
    assert os.getcwd() == keep_cwd
    assert messages == ["Folder created successfully : docs"]


def test_rename_and_delete_a_file_inside_the_root(manager, root, keep_cwd):
    (root / "old.txt").write_text("x")

    manager.handle_form(_form(action="rename", path="/old.txt", name="new.txt"), files=None)
    assert (root / "new.txt").exists()

    manager.handle_form(_form(action="delete", path="/new.txt"), files=None)
    assert not (root / "new.txt").exists()
    assert os.getcwd() == keep_cwd


def test_directory_structure_does_not_change_the_working_directory(manager, root, keep_cwd):
    (root / "docs").mkdir()
    (root / "docs" / "a.txt").write_text("x")
    manager.current_path = "/"

    structure = manager.directory_structure()

    assert os.getcwd() == keep_cwd
    assert "docs" in structure[""]["dirs"]
    assert structure[""]["dirs"]["docs"]["files"] == ["a.txt"]


def test_template_does_not_let_a_message_close_the_script_tag():
    payload = "Invalid path : </script><script>alert(1)</script>"

    html = render_to_string(
        "filemanager/index.html",
        {"dir_structure": {"": {"id": 1, "open": "yes", "dirs": {}, "files": []}}, "messages": [payload], "current_id": 1},
    )

    assert "<script>alert(1)" not in html
    assert "|safe" not in html


def test_media_serves_the_extension_icon_for_a_non_image_file(manager, root):
    (root / "notes.txt").write_text("plain text")

    response = manager.media("notes.txt")

    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"


def test_media_serves_the_extension_icon_for_a_corrupt_image(manager, root):
    (root / "broken.png").write_bytes(b"not an image")

    response = manager.media("broken.png")

    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert max(_size(response)) <= 60


def test_move_into_its_own_child_folder_is_rejected(manager, root, keep_cwd):
    (root / "docs" / "inner").mkdir(parents=True)

    messages = manager.handle_form(
        _form(action="move", path="/docs/", current_path="/docs/inner/", file_or_dir="dir"), files=None
    )

    assert messages == ["Cannot move/copy to a child folder"]
    assert (root / "docs" / "inner").is_dir()


def test_unzip_skips_members_that_resolve_outside_the_folder(manager, root, keep_cwd):
    import zipfile

    image = io.BytesIO()
    Image.new("RGB", (5, 5), "red").save(image, "PNG")
    with zipfile.ZipFile(root / "bundle.zip", "w") as bundle:
        bundle.writestr("../escaped.png", image.getvalue())
        bundle.writestr("kept.png", image.getvalue())

    messages = manager.handle_form(_form(action="unzip", path="/bundle.zip"), files=None)

    assert not (root.parent / "escaped.png").exists()
    assert (root / "kept.png").exists()
    assert "File in the zip is not allowed : ../escaped.png" in messages


def test_ckeditor_widget_renders_on_current_django_and_escapes_its_config():
    from filemanager.widgets import CKEditorWidget

    widget = CKEditorWidget(config={"title": "</script><script>alert(1)</script>"})

    html = widget.render("body", "text", attrs={"id": "id_body"})

    assert "<script>alert(1)" not in html
    assert 'CKEDITOR.replace("id_body", ' in html
    assert '"toolbar": "Standard"' in html


def test_download_quotes_a_file_name_with_spaces_and_non_ascii_letters(manager, root):
    (root / "año 2026.txt").write_text("x")

    response = manager.download("año 2026.txt", "file")

    assert response["Content-Disposition"] == "attachment; filename*=utf-8''a%C3%B1o%202026.txt"


def test_unzip_reads_the_zip_from_its_own_folder(manager, root, keep_cwd):
    import zipfile

    image = io.BytesIO()
    Image.new("RGB", (5, 5), "red").save(image, "PNG")
    (root / "sub").mkdir()
    with zipfile.ZipFile(root / "sub" / "bundle.zip", "w") as bundle:
        bundle.writestr("kept.png", image.getvalue())

    messages = manager.handle_form(_form(action="unzip", path="/sub/bundle.zip", current_path="/sub/"), files=None)

    assert messages == ["Extraction completed successfully."]
    assert (root / "sub" / "kept.png").exists()


def test_unzip_without_an_extension_list_does_not_fail(root, keep_cwd):
    import zipfile

    manager = FileManager(str(root))
    image = io.BytesIO()
    Image.new("RGB", (5, 5), "red").save(image, "PNG")
    with zipfile.ZipFile(root / "bundle.zip", "w") as bundle:
        bundle.writestr("kept.png", image.getvalue())

    messages = manager.handle_form(_form(action="unzip", path="/bundle.zip"), files=None)

    assert messages == ["Extraction completed successfully."]
    assert (root / "kept.png").exists()


class _FakeUpload:
    """Upload whose name keeps its path, as an object that did not go through Django's multipart parser."""

    def __init__(self, name, content=b"payload"):
        self.name = name
        self._content = content
        self.size = len(content)

    def chunks(self):
        yield self._content

    def close(self):
        pass


class _FakeFiles:
    def __init__(self, *uploads):
        self._uploads = list(uploads)

    def getlist(self, key):
        return self._uploads if key == "ufile" else []


@pytest.mark.parametrize("name_for", [
    lambda tmp: str(tmp / "escaped.txt"),  # absolute path: os.path.join drops the upload folder
    lambda tmp: "sub/escaped.txt",  # separator: names are single path components
])
def test_upload_rejects_a_name_that_carries_a_path(manager, root, tmp_path, name_for):
    messages = manager.handle_form(
        _form(action="upload", path="/"), _FakeFiles(_FakeUpload(name_for(tmp_path)))
    )

    assert any("File name is not valid" in str(m) for m in messages)
    assert not (tmp_path / "escaped.txt").exists()
    assert not (root / "sub").exists()


def test_upload_stores_a_plain_name_inside_the_folder(manager, root):
    messages = manager.handle_form(
        _form(action="upload", path="/"), _FakeFiles(_FakeUpload("note.txt", b"hello world"))
    )

    assert (root / "note.txt").read_bytes() == b"hello world"
    assert "All files uploaded successfully" in [str(m) for m in messages]


# --- 1.0.1: inputs that used to end in an HTTP 500 or in a silent overwrite -------------------------------


@pytest.mark.parametrize("fields, expected", [
    # A first character outside the allowed class made re.match return None and crashed with AttributeError.
    (dict(action="delete", path="<x>"), "Invalid path"),
    (dict(action="delete", path="@x"), "Invalid path"),
    (dict(action="add", path="", name="docs", file_or_dir="dir"), "Invalid path"),
    (dict(action="add", path="/", name="..", file_or_dir="dir"), "Invalid folder name"),
    (dict(action="add", path="/", name="[docs]", file_or_dir="dir"), "Invalid folder name"),
    (dict(action="rename", path="/old.txt", name="<x>.txt"), "Invalid file name"),
])
def test_form_actions_answer_a_message_for_a_value_that_starts_with_an_unlisted_character(
    manager, root, keep_cwd, fields, expected
):
    (root / "old.txt").write_text("x")

    messages = manager.handle_form(_form(**fields), files=None)

    assert any(expected in str(m) for m in messages)
    assert (root / "old.txt").read_text() == "x"


@pytest.mark.parametrize("name", ["@x.png", "[report].png", "~backup.png", "=x.png"])
def test_upload_answers_a_message_for_a_name_that_starts_with_an_unlisted_character(manager, root, name):
    messages = manager.handle_form(_form(action="upload", path="/"), _FakeFiles(_FakeUpload(name)))

    assert any("File name is not valid" in str(m) for m in messages)
    assert list(root.iterdir()) == []


def test_download_answers_invalid_path_for_a_path_that_starts_with_an_unlisted_character(manager):
    response = manager.download("@x.png", "file")

    assert response.content == b"Invalid path"


def test_download_of_a_file_that_does_not_exist_is_a_404(manager):
    with pytest.raises(Http404):
        manager.download("missing.txt", "file")


def test_download_of_a_folder_that_does_not_exist_is_a_404(manager):
    with pytest.raises(Http404):
        manager.download("missing/", "dir")


def test_download_of_a_folder_as_a_file_is_a_404(manager, root):
    (root / "docs").mkdir()

    with pytest.raises(Http404):
        manager.download("docs", "file")


def test_download_with_an_unknown_mode_is_a_400(manager, root):
    (root / "notes.txt").write_text("hello")

    assert manager.download("notes.txt", "bogus").status_code == 400


def test_rename_a_file_onto_an_existing_one_keeps_both(manager, root, keep_cwd):
    (root / "a.txt").write_text("first")
    (root / "b.txt").write_text("second")

    messages = manager.handle_form(_form(action="rename", path="/a.txt", name="b.txt"), files=None)

    assert (root / "a.txt").read_text() == "first"
    assert (root / "b.txt").read_text() == "second"
    assert any("already exists" in str(m) for m in messages)
    assert not any("renamed successfully" in str(m) for m in messages)


def test_rename_a_folder_onto_an_existing_one_keeps_both(manager, root, keep_cwd):
    (root / "one").mkdir()
    (root / "two").mkdir()
    (root / "one" / "inside.txt").write_text("x")

    messages = manager.handle_form(
        _form(action="rename", path="/one/", name="two", file_or_dir="dir"), files=None
    )

    assert (root / "one" / "inside.txt").exists()
    assert (root / "two").is_dir()
    assert any("already exists" in str(m) for m in messages)


def test_rename_a_file_to_its_own_name_is_still_accepted(manager, root, keep_cwd):
    (root / "a.txt").write_text("first")

    messages = manager.handle_form(_form(action="rename", path="/a.txt", name="a.txt"), files=None)

    assert (root / "a.txt").read_text() == "first"
    assert not any("already exists" in str(m) for m in messages)


def test_form_accepts_an_empty_upload_so_the_user_gets_a_message():
    from django.core.files.uploadedfile import SimpleUploadedFile

    form = FileManagerForm(
        {"action": "upload", "path": "/", "file_or_dir": "file", "current_path": "/"},
        {"ufile": SimpleUploadedFile("empty.txt", b"")},
    )

    assert form.is_valid(), form.errors


def test_upload_of_an_empty_file_is_rejected_with_a_message(manager, root):
    messages = manager.handle_form(_form(action="upload", path="/"), _FakeFiles(_FakeUpload("empty.txt", b"")))

    assert "File is empty : empty.txt" in [str(m) for m in messages]
    assert list(root.iterdir()) == []
