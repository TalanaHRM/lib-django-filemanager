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
