from kstars_sync.userdb_report import (
    TABLE_LABELS,
    format_changed_tables,
)


def test_all_observed_userdb_tables_have_labels():
    observed_tables = {
        "SkyMapViews",
        "Version",
        "collimationoverlayelements",
        "customdrivers",
        "darkframe",
        "driver",
        "dslr",
        "dslrlens",
        "effectivefov",
        "eyepiece",
        "filter",
        "flags",
        "fov",
        "hips",
        "horizon_1",
        "horizon_2",
        "horizon_3",
        "horizons",
        "imageOverlays",
        "imagingPlanner",
        "lens",
        "logentry",
        "opticaltraindevices",
        "opticaltrains",
        "opticaltrainsettings",
        "profile",
        "profilesettings",
        "telescope",
        "user",
        "wishlist",
    }

    assert set(TABLE_LABELS) == observed_tables


def test_format_changed_tables_uses_known_labels():
    result = format_changed_tables(
        ["imageOverlays", "opticaltrains"]
    )

    assert result == (
        "Image overlays (imageOverlays)\n"
        "Optical trains (opticaltrains)"
    )


def test_format_changed_tables_preserves_unknown_table_name():
    result = format_changed_tables(["future_kstars_table"])

    assert result == "future_kstars_table"


def test_format_changed_tables_preserves_input_order():
    result = format_changed_tables(
        ["profile", "imageOverlays", "filter"]
    )

    assert result.splitlines() == [
        "Profiles (profile)",
        "Image overlays (imageOverlays)",
        "Filters (filter)",
    ]


def test_format_changed_tables_empty_list_returns_empty_string():
    assert format_changed_tables([]) == ""
