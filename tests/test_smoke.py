import coc_pointer


def test_package_imports() -> None:
    assert callable(coc_pointer.main)
