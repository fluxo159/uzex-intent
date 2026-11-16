import datetime as dt

from fastapi import APIRouter, HTTPException, Query

from . import calendar as cal
from . import chart
from . import counterfactual as cf

router = APIRouter(prefix="/market", tags=["market"])

@router.get("/chart")
def get_chart(commodity: str = "cement", grade: str | None = "32.5", region: str | None = None,
              date_from: dt.date | None = None, date_to: dt.date | None = None,
              bucket: str = Query("day", pattern="^(day|week)$")) -> dict:
    if commodity != "cement":
        raise HTTPException(404, "график есть только для цемента")
    g = chart.normalize_grade_param(grade)
    r = chart.normalize_region_param(region)
    df = chart.hist_df()
    res = chart.points(df, g, r, date_from, date_to, bucket)
    res.update({
        "commodity": commodity, "grade": g, "grade_label": chart.GRADE_LABELS.get(g or "", g),
        "region": r if r != "__unknown__" else None, "region_unknown": r == "__unknown__",
        "bucket": bucket, "corridor": chart.corridor(df, g, r),
        "headline": chart.headline(df, g, r),
        "source": "данные UZEX, двойной аукцион", "data_cutoff": chart.config.DATA_CUTOFF,
    })
    return res

@router.get("/calendar")
def get_calendar(now: str | None = None, n: int = Query(cal.N_WINDOWS, ge=1, le=20)) -> dict:
    try:
        return cal.build(now, n)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e

@router.get("/counterfactual/ai92")
def get_ai92() -> dict:
    try:
        return cf.ai92()
    except FileNotFoundError as e:
        raise HTTPException(503, "нет файла data/demo/ai92_2026-11-06.json") from e
