import pytest

from app.data import loader
from app.regions import normalize_region, find_regions

@pytest.mark.parametrize("raw,exp", [
    ("32,5Н", "32.5"), ("32.5 Н", "32.5"), ("ЦЕМ II А-И 32,5", "32.5"), ("32.5(~M400)", "32.5"),
    ("Портландцемент Марка Цем II В-К 42,5H Тури композиционный", "42.5"), ("42.5", "42.5"),
    ("М400", "32.5"), ("m500", "42.5"), ("ЦЕМ I 52,5", "other"), ("", "other"), (None, "other"),
    (float("nan"), "other"),
])
def test_normalize_grade(raw, exp):
    assert loader.normalize_grade(raw) == exp

@pytest.mark.parametrize("raw,exp", [
    ("Samarqand viloyati", "Samarkand"), ("Qoraqalpog‘iston Respublikasi", "Karakalpakstan"),
    ("Jizzax viloyati", "Jizzakh"), ("Farg‘ona viloyati", "Fergana"),
    ("Aндижон вилояти", "Andijan"),
    ("Xorazm viloyati", "Khorezm"), ("ТОШКЕНТ ВИЛОЯТИ, ОХАНГАРОН ТУМАНИ", "Tashkent_region"),
    ("Кашкадарё обл ,Китоб р-н", "Qashqadaryo"), ("Джизакская область", "Jizzakh"),
    ("Андижанская область,Булокбошинский район", "Andijan"), ("Ташкент", "Tashkent_city"),
    ("Ташкентская область", "Tashkent_region"), ("", None), (None, None), ("Луна", None),
])
def test_normalize_region(raw, exp):
    assert normalize_region(raw) == exp

def test_find_regions_order():
    hits = find_regions("из Ташкента в Карши")
    assert [c for _, c in hits] == ["Tashkent_city", "Qashqadaryo"]

@pytest.mark.parametrize("s,exp", [
    ("Бекор қилинган (Тўланмаган)", True), ("Бекор қилинган (Юкланмаган)", True),
    ("Бажарилган", False), ("Бажарилган(Қисман)", False), (None, False),
])
def test_is_cancelled(s, exp):
    assert loader.is_cancelled(s) is exp

def test_price_per_t_recomputed():
    assert loader.price_per_t(29_151_000, 55) == pytest.approx(530_018.18, rel=1e-6)
    assert loader.price_per_t(100, 0) is None
    assert loader.price_per_t("x", 5) is None

@pytest.mark.parametrize("p,exp", [
    (199_999, True), (200_000, False), (3_000_000, False), (3_000_001, True), (4_700, True), (None, True),
])
def test_is_suspect(p, exp):
    assert loader.is_suspect(p) is exp

def test_load_hist_shape_and_traps():
    df = loader.load_hist()
    assert len(df) == 2339
    assert int(df["cancelled"].sum()) == 119
    assert set(df["grade"]) <= {"32.5", "42.5", "other"}
    assert df["region"].isna().sum() == 0
    assert "Andijan" in set(df["region"])

def test_load_main_shape():
    df = loader.load_main()
    assert len(df) == 401
    assert df["suspect"].sum() > 0
    toshkent = df[df["seller"] == "Toshkent Conch Cement"]
    assert set(toshkent["wh_region"]) == {"Tashkent_region"}

def test_schedule_numbers_with_comma():
    df = loader.load_schedule()
    assert len(df) > 10
    assert (df["volume_t"] > 0).all()

def test_build_db(tmp_path):
    p = loader.build_db(tmp_path / "t.duckdb")
    import duckdb
    con = duckdb.connect(str(p), read_only=True)
    assert con.execute("select count(*) from deals_hist").fetchone()[0] == 2339
    assert con.execute("select count(*) from deals_main").fetchone()[0] == 401
