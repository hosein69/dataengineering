# -*- coding: utf-8 -*-
"""قالب دقیق ذخیره DataFrame در Parquet برای انبار داده نسخه ۲.

هر فریم یک فایل Parquet می‌شود که با اثرانگشت محتوایش در پوشه بایگانی می‌نشیند
(``objects.py``). فریمی که عوض نشده دوباره نوشته نمی‌شود، چون همان اثرانگشت را دارد.

قرارداد دقت: ``decode_frame(encode_frame(df))`` همان فریم را برمی‌گرداند؛ همان ستون‌ها
با همان ترتیب و برچسب، همان dtype، همان index (RangeIndex هم RangeIndex می‌ماند)، همان
``attrs`` و در ستون‌های object همان نوع پایتونی هر خانه (str، float، None، pd.NA،
Timestamp، numpy scalar، list و …). خانه خالی هرگز صفر نمی‌شود.

سه شکل ذخیره ستون:

* ``np``: ستون‌های عددی، بولی و تاریخی numpy مستقیم در Arrow؛ NaN همان NaN می‌ماند.
* ``obj``: ستون object که همه مقدارهایش دقیقاً یک نوع پایتونی دارند (str، float، bool یا
  int) و خانه‌های خالی‌اش هم یک نوع (None یا NaN یا pd.NA یا NaT)؛ نوع خانه خالی در
  متادیتا ثبت می‌شود.
* ``json``: هر ستون دیگر؛ هر خانه با برچسب نوعش به JSON می‌رود و برمی‌گردد، سپس به
  dtype ثبت‌شده برگردانده می‌شود.
"""
from __future__ import annotations

import base64
import datetime as _dt
import decimal
import io
import json
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

CODEC = "gsi-frame/1"
_META_KEY = b"gsi.frame"

# نوع خانه خالی در ستون‌های متنی
_NULLS = {"none": None, "nan": float("nan"), "npnan": np.float64("nan"), "na": pd.NA, "nat": pd.NaT}


def _arrow():
    import pyarrow as pa
    import pyarrow.parquet as pq
    return pa, pq


def _np(col) -> np.ndarray:
    """ستون Arrow (تکه‌تکه یا یکپارچه) ← numpy؛ روی pyarrow قدیمی هم کار می‌کند."""
    if hasattr(col, "combine_chunks"):
        col = col.combine_chunks()
    return col.to_numpy(zero_copy_only=False)


def _strings(col) -> np.ndarray:
    """ستون متنی Arrow ← آرایه object از str پایتون (خالی‌ها None).

    to_pandas با deduplicate_objects متن‌های تکراری را یک‌بار می‌سازد؛ برای ستون‌های
    وضعیت، ارز و کد که مقدار تکراری زیاد دارند تقریباً دو برابر تندتر از to_numpy است.
    """
    try:
        series = col.to_pandas(use_threads=False, deduplicate_objects=True)
        values = series.to_numpy(dtype=object) if hasattr(series, "to_numpy") else np.asarray(series, dtype=object)
        if values.dtype != object:
            values = values.astype(object)
        return values
    except (TypeError, AttributeError):
        return np.asarray(_np(col), dtype=object)


def _null_mask(col) -> np.ndarray:
    if hasattr(col, "combine_chunks"):
        col = col.combine_chunks()
    return np.asarray(col.is_null().to_numpy(zero_copy_only=False), dtype=bool)


# ─────────────────────────── خانه‌ها ← → JSON ───────────────────────────
def _tz_name(tz) -> str | None:
    if tz is None:
        return None
    for attr in ("key", "zone"):
        name = getattr(tz, attr, None)
        if isinstance(name, str) and name:
            return name
    return None


def enc(x: Any) -> Any:
    """Tagged JSON-able form; exact for every type the pipeline puts in a cell."""
    t = type(x)
    if x is None or t is str or t is bool or t is int:
        return x
    if t is float:
        return x                      # json با allow_nan نویسه NaN/Infinity را هم برمی‌گرداند
    if t is list:
        return [enc(v) for v in x]
    if x is pd.NA:
        return {"$": "NA"}
    if x is pd.NaT:
        return {"$": "NaT"}
    if isinstance(x, np.generic):
        dt = x.dtype
        if dt.kind in "Mm":
            return {"$": "np", "t": dt.str, "i": int(x.view("i8"))}
        if dt.kind == "U":
            return {"$": "np", "t": "U", "v": str(x)}
        if dt.kind == "c":
            return {"$": "np", "t": dt.str, "v": [float(x.real), float(x.imag)]}
        if dt.kind in "biuf":
            return {"$": "np", "t": dt.str, "v": x.item()}
        raise TypeError(f"Unsupported warehouse value: {type(x).__name__}")
    if isinstance(x, pd.Timestamp):
        return {"$": "ts", "iso": x.isoformat(), "unit": x.unit, "tz": _tz_name(x.tz)}
    if isinstance(x, pd.Timedelta):
        return {"$": "ptd", "v": int(x.value), "unit": x.unit}
    if t is _dt.datetime:
        return {"$": "dt", "v": x.isoformat()}
    if t is _dt.date:
        return {"$": "date", "v": x.isoformat()}
    if t is _dt.time:
        return {"$": "time", "v": x.isoformat()}
    if t is _dt.timedelta:
        return {"$": "td", "d": x.days, "s": x.seconds, "us": x.microseconds}
    if t is tuple:
        return {"$": "tuple", "v": [enc(v) for v in x]}
    if t is dict:
        return {"$": "dict", "v": [[enc(k), enc(v)] for k, v in x.items()]}
    if isinstance(x, decimal.Decimal):
        return {"$": "dec", "v": str(x)}
    if isinstance(x, (bytes, bytearray)):
        return {"$": "bytes", "v": base64.b64encode(bytes(x)).decode("ascii")}
    if isinstance(x, (set, frozenset)):
        items = sorted((enc(v) for v in x), key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False))
        return {"$": "set" if isinstance(x, set) else "frozenset", "v": items}
    if isinstance(x, list):
        # SharedList آداپترها در attrs: فهرستی که pandas نباید کپی عمیق کند
        kind = "SharedList" if t.__name__ == "SharedList" else "list"
        return {"$": kind, "v": [enc(v) for v in x]}
    if isinstance(x, str):
        return str(x)
    if isinstance(x, float):
        return float(x)
    if isinstance(x, int):
        return int(x)
    raise TypeError(f"Unsupported warehouse value: {type(x).__name__}")


def dec(x: Any) -> Any:
    if isinstance(x, list):
        return [dec(v) for v in x]
    if not isinstance(x, dict):
        return x
    kind = x.get("$")
    if kind == "NA":
        return pd.NA
    if kind == "NaT":
        return pd.NaT
    if kind == "np":
        t = x["t"]
        if t == "U":
            return np.str_(x["v"])
        dt = np.dtype(t)
        if dt.kind in "Mm":
            return np.array(x["i"], dtype="i8").view(dt)[()]
        if dt.kind == "c":
            return dt.type(complex(*x["v"]))
        return dt.type(x["v"])
    if kind == "ts":
        ts = pd.Timestamp(x["iso"])
        if x.get("tz"):
            ts = ts.tz_convert(x["tz"])
        return ts.as_unit(x["unit"]) if x.get("unit") else ts
    if kind == "ptd":
        td = pd.Timedelta(int(x["v"]), unit="ns")
        return td.as_unit(x["unit"]) if x.get("unit") else td
    if kind == "dt":
        return _dt.datetime.fromisoformat(x["v"])
    if kind == "date":
        return _dt.date.fromisoformat(x["v"])
    if kind == "time":
        return _dt.time.fromisoformat(x["v"])
    if kind == "td":
        return _dt.timedelta(days=x["d"], seconds=x["s"], microseconds=x["us"])
    if kind == "tuple":
        return tuple(dec(v) for v in x["v"])
    if kind == "dict":
        return {dec(k): dec(v) for k, v in x["v"]}
    if kind == "dec":
        return decimal.Decimal(x["v"])
    if kind == "bytes":
        return base64.b64decode(x["v"])
    if kind in ("set", "frozenset"):
        items = [dec(v) for v in x["v"]]
        return set(items) if kind == "set" else frozenset(items)
    if kind == "SharedList":
        try:
            from gsi.adapters.base import SharedList
        except Exception:                               # پکیج آداپتر در دسترس نیست
            return [dec(v) for v in x["v"]]
        return SharedList(dec(v) for v in x["v"])
    if kind == "list":
        return [dec(v) for v in x["v"]]
    raise ValueError(f"Unknown warehouse cell tag: {kind!r}")


def dumps(x: Any) -> str:
    return json.dumps(enc(x), ensure_ascii=False, separators=(",", ":"), allow_nan=True)


def loads(text: str) -> Any:
    return dec(json.loads(text))


# ─────────────────────────── ستون‌ها ───────────────────────────
def _null_flavour(v) -> str | None:
    if v is None:
        return "none"
    if v is pd.NA:
        return "na"
    if v is pd.NaT:
        return "nat"
    t = type(v)
    if t is float and v != v:
        return "nan"
    if t is np.float64 and v != v:
        return "npnan"
    return None


_NULL_BY_TYPE = {type(None): "none", float: "nan", np.float64: "npnan", type(pd.NA): "na", type(pd.NaT): "nat"}
_INT64 = (-(2 ** 63), 2 ** 63 - 1)


def _typed_object_column(values: np.ndarray):
    """ستون object با یک نوع پایتونی (str، float، bool یا int) و یک نوع خانه خالی.

    مقدارها به نوع بومی Arrow می‌روند و خانه‌های خالی با نوع خودشان ثبت می‌شوند؛ هنگام
    بازخوانی همان اشیای پایتونی ساخته می‌شوند. هر حالت دیگری ← None (مسیر JSON).
    """
    pa, _ = _arrow()
    mask = pd.isna(values)
    has_null = bool(mask.any())
    present = values[~mask] if has_null else values
    kinds = set(map(type, present))
    if len(kinds) > 1:
        return None
    kind = kinds.pop() if kinds else str
    name = kind.__name__ if kind in (str, float, bool, int) else None
    if name is None:
        return None
    if kind is int and len(present) and (min(present) < _INT64[0] or max(present) > _INT64[1]):
        return None
    flavour = None
    if has_null:
        # pd.isna این خانه‌ها را خالی دانسته؛ پس نوعشان برای شناختن نوع خانه خالی کافی است
        null_types = set(map(type, values[mask]))
        if len(null_types) != 1:
            return None
        flavour = _NULL_BY_TYPE.get(null_types.pop())
        if flavour is None:
            return None
        values = values.copy()
        values[mask] = None
    arrow_type = {"str": pa.large_string(), "float": pa.float64(), "bool": pa.bool_(), "int": pa.int64()}[name]
    return {"k": "obj", "t": name, "null": flavour}, pa.array(values, type=arrow_type)


def _json_column(values, dtype_text: str):
    pa, _ = _arrow()
    cells = [dumps(v) for v in values]
    return {"k": "json", "dtype": dtype_text}, pa.array(cells, type=pa.large_string())


def _encode_column(s: pd.Series):
    pa, _ = _arrow()
    dt = s.dtype
    if isinstance(dt, np.dtype) and dt.kind in "biufMm" and dt.itemsize and dt.kind != "c":
        values = s.to_numpy(copy=False)
        if dt.kind in "Mm":
            # NaT باید NaT بماند نه عدد: ذخیره به شکل int64 همراه dtype دقیق
            return {"k": "np", "dtype": dt.str}, pa.array(values.view("i8"))
        return {"k": "np", "dtype": dt.str}, pa.array(values)
    if isinstance(dt, pd.CategoricalDtype):
        cats = list(dt.categories)
        spec = {"k": "cat", "ordered": bool(dt.ordered), "cats": [enc(v) for v in cats],
                "cats_dtype": str(dt.categories.dtype)}
        return spec, pa.array(s.cat.codes.to_numpy(dtype="int32", copy=False))
    if dt == object:
        values = s.to_numpy(dtype=object, copy=False)
        fast = _typed_object_column(values)
        if fast is not None:
            return fast
        return _json_column(values, "object")
    return _json_column(s.astype(object).to_numpy(), str(dt))


def _decode_column(spec: Dict[str, Any], col, rows: int):
    kind = spec["k"]
    if kind == "np":
        dt = np.dtype(spec["dtype"])
        raw = _np(col)
        if dt.kind in "Mm":
            return np.asarray(raw, dtype="i8").view(dt)
        return np.asarray(raw).astype(dt, copy=False)
    if kind == "obj":
        flavour = spec.get("null")
        if spec["t"] == "str":
            values = _strings(col)
        else:
            pa, _ = _arrow()
            if hasattr(col, "combine_chunks"):
                col = col.combine_chunks()
            zero = {"float": 0.0, "bool": False, "int": 0}[spec["t"]]
            filled = col.fill_null(pa.scalar(zero, type=col.type)) if col.null_count else col
            values = np.asarray(filled.to_numpy(zero_copy_only=False)).astype(object)
            if flavour is None or flavour == "none":
                if col.null_count:
                    values[_null_mask(col)] = None
                return values
        if flavour and flavour != "none":
            mask = _null_mask(col)
            if mask.any():
                values[mask] = _NULLS[flavour]
        return values
    if kind == "cat":
        codes = np.asarray(_np(col), dtype="int32")
        cats = pd.Index([dec(v) for v in spec["cats"]])
        if spec.get("cats_dtype") and str(cats.dtype) != spec["cats_dtype"]:
            cats = cats.astype(spec["cats_dtype"])
        return pd.Categorical.from_codes(codes, categories=cats, ordered=spec["ordered"])
    if kind == "json":
        cells = _np(col)
        values = np.empty(rows, dtype=object)
        for i, text in enumerate(cells):
            values[i] = loads(text)
        dtype = spec.get("dtype", "object")
        if dtype == "object":
            return values
        return pd.Series(values, dtype=object).astype(dtype).array
    raise ValueError(f"Unknown frame column kind: {kind!r}")


# ─────────────────────────── index و برچسب ستون‌ها ───────────────────────────
def _encode_labels(index: pd.Index) -> Dict[str, Any]:
    if isinstance(index, pd.RangeIndex):
        return {"k": "range", "start": index.start, "stop": index.stop, "step": index.step,
                "name": enc(index.name)}
    if isinstance(index, pd.MultiIndex):
        return {"k": "multi", "names": [enc(n) for n in index.names],
                "values": [enc(tuple(v)) for v in index]}
    return {"k": "list", "name": enc(index.name), "dtype": str(index.dtype),
            "values": [enc(v) for v in index]}


def _decode_labels(spec: Dict[str, Any]) -> pd.Index:
    if spec["k"] == "range":
        return pd.RangeIndex(spec["start"], spec["stop"], spec["step"], name=dec(spec["name"]))
    if spec["k"] == "multi":
        return pd.MultiIndex.from_tuples([dec(v) for v in spec["values"]], names=[dec(n) for n in spec["names"]])
    values = [dec(v) for v in spec["values"]]
    dtype = spec.get("dtype")
    try:
        return pd.Index(values, dtype=dtype, name=dec(spec["name"]))
    except (TypeError, ValueError):
        return pd.Index(values, dtype=object, name=dec(spec["name"]))


def _encode_index(index: pd.Index):
    """Index سطرها: RangeIndex با سه عدد؛ بقیه مثل ستون ذخیره می‌شوند."""
    if isinstance(index, pd.RangeIndex):
        return {"k": "range", "start": index.start, "stop": index.stop, "step": index.step,
                "name": enc(index.name)}, []
    if isinstance(index, pd.MultiIndex):
        levels = []
        arrays = []
        for i in range(index.nlevels):
            spec, arr = _encode_column(pd.Series(index.get_level_values(i)))
            levels.append(spec)
            arrays.append(arr)
        return {"k": "multi", "names": [enc(n) for n in index.names], "levels": levels}, arrays
    spec, arr = _encode_column(pd.Series(index, copy=False))
    return {"k": "col", "name": enc(index.name), "spec": spec, "type": type(index).__name__}, [arr]


def _decode_index(spec: Dict[str, Any], table, rows: int) -> pd.Index:
    if spec["k"] == "range":
        return pd.RangeIndex(spec["start"], spec["stop"], spec["step"], name=dec(spec["name"]))
    if spec["k"] == "multi":
        arrays = [_decode_column(level, table.column(f"i{i}"), rows) for i, level in enumerate(spec["levels"])]
        return pd.MultiIndex.from_arrays(arrays, names=[dec(n) for n in spec["names"]])
    values = _decode_column(spec["spec"], table.column("i0"), rows)
    return pd.Index(values, name=dec(spec["name"]), dtype=getattr(values, "dtype", None))


# ─────────────────────────── فریم ───────────────────────────
def encode_frame(df: pd.DataFrame, *, compression: str = "zstd") -> bytes:
    """DataFrame ← بایت‌های Parquet، قطعی: همان فریم همیشه همان بایت‌ها را می‌دهد."""
    pa, pq = _arrow()
    rows = len(df)
    names: List[str] = []
    arrays = []
    specs = []
    for i in range(df.shape[1]):
        spec, arr = _encode_column(df.iloc[:, i])
        specs.append(spec)
        arrays.append(arr)
        names.append(f"c{i}")
    index_spec, index_arrays = _encode_index(df.index)
    for i, arr in enumerate(index_arrays):
        arrays.append(arr)
        names.append(f"i{i}")
    meta = {
        "codec": CODEC,
        "rows": rows,
        "columns": _encode_labels(df.columns),
        "specs": specs,
        "index": index_spec,
        "attrs": enc(dict(df.attrs)),
    }
    if arrays:
        table = pa.Table.from_arrays(arrays, names=names)
    else:
        table = pa.table({})
    table = table.replace_schema_metadata({_META_KEY: json.dumps(meta, ensure_ascii=False, separators=(",", ":"),
                                                                 allow_nan=True).encode("utf-8")})
    if not pa.Codec.is_available(compression):
        compression = "snappy" if pa.Codec.is_available("snappy") else "none"
    sink = io.BytesIO()
    pq.write_table(table, sink, compression=compression, write_statistics=False)
    return sink.getvalue()


def frame_meta(data: bytes) -> Dict[str, Any]:
    _, pq = _arrow()
    schema = pq.read_schema(io.BytesIO(data))
    return json.loads(schema.metadata[_META_KEY].decode("utf-8"))


def decode_frame(data: bytes) -> pd.DataFrame:
    _, pq = _arrow()
    # use_threads=False: خواندن چندرشته‌ای pyarrow گاهی هنگام خروج پایتون فرایند را با
    # «terminate called without an active exception» (کد 134) می‌بندد؛ فریم‌ها کوچک‌تر از
    # آن‌اند که رشته‌های موازی ارزشش را داشته باشند.
    # pre_buffer=False: بدون آن، خواندن تک‌رشته‌ای pyarrow برای فریم‌های پهن تا ده برابر کندتر است.
    try:
        table = pq.read_table(io.BytesIO(data), use_threads=False, pre_buffer=False)
    except TypeError:                                   # pyarrow خیلی قدیمی
        table = pq.read_table(io.BytesIO(data), use_threads=False)
    raw = (table.schema.metadata or {}).get(_META_KEY)
    if raw is None:
        raise ValueError("این فایل Parquet فریم انبار GSI نیست (متادیتای gsi.frame ندارد).")
    meta = json.loads(raw.decode("utf-8"))
    if meta.get("codec") != CODEC:
        raise ValueError(f"قالب فریم پشتیبانی نمی‌شود: {meta.get('codec')!r}")
    rows = int(meta["rows"])
    if table.num_rows != rows and meta["specs"]:
        raise RuntimeError("Warehouse row count mismatch")
    index = _decode_index(meta["index"], table, rows)
    data = {i: _decode_column(spec, table.column(f"c{i}"), rows) for i, spec in enumerate(meta["specs"])}
    df = pd.DataFrame(data, index=index, copy=False)
    if not data:
        df = pd.DataFrame(index=index)
    df.columns = _decode_labels(meta["columns"])
    df.attrs.update(dec(meta.get("attrs") or {}))
    return df



def decode_columns(data: bytes, wanted) -> pd.DataFrame:
    """فقط ستون‌های ``wanted`` یک فریم انبار (برای خواندن سبک تاریخچه از فریم‌های پهن)؛ نمایه بازسازی نمی‌شود.

    ستونی که در فریم نیست برگردانده نمی‌شود؛ خواننده خودش نبودنش را «بی‌داده» می‌خواند.
    """
    _, pq = _arrow()
    pf = pq.ParquetFile(io.BytesIO(data))
    raw = (pf.schema_arrow.metadata or {}).get(_META_KEY)
    if raw is None:
        raise ValueError("این فایل Parquet فریم انبار GSI نیست (متادیتای gsi.frame ندارد).")
    meta = json.loads(raw.decode("utf-8"))
    if meta.get("codec") != CODEC:
        raise ValueError(f"قالب فریم پشتیبانی نمی‌شود: {meta.get('codec')!r}")
    labels = list(_decode_labels(meta["columns"]))
    want = set(wanted)
    idx = [i for i, label in enumerate(labels) if label in want]
    rows = int(meta["rows"])
    table = pf.read(columns=[f"c{i}" for i in idx], use_threads=False)
    return pd.DataFrame({labels[i]: _decode_column(meta["specs"][i], table.column(f"c{i}"), rows) for i in idx})

# ─────────────────────────── مقایسه دقیق ───────────────────────────
def _same_cell(a, b) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, float) or isinstance(a, np.floating):
        if a != a and b != b:
            return True
        return a == b and (a != 0 or np.signbit(a) == np.signbit(b))
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(_same_cell(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return list(a) == list(b) and all(_same_cell(a[k], b[k]) for k in a)
    if a is pd.NA or a is pd.NaT or a is None:
        return a is b
    if isinstance(a, decimal.Decimal) and a.is_nan():
        return b.is_nan() and str(a) == str(b)
    try:
        eq = a == b
        return bool(eq) if not isinstance(eq, np.ndarray) else bool(eq.all())
    except Exception:
        return False


def frame_differences(a: pd.DataFrame, b: pd.DataFrame, limit: int = 20) -> List[str]:
    """تفاوت‌های دو فریم تا ``limit`` مورد؛ فهرست خالی یعنی دقیقاً یکسان."""
    out: List[str] = []
    if type(a.index) is not type(b.index) or not a.index.equals(b.index) or a.index.dtype != b.index.dtype \
            or a.index.names != b.index.names:
        out.append("index")
    if type(a.columns) is not type(b.columns) or list(a.columns) != list(b.columns) \
            or a.columns.dtype != b.columns.dtype or a.columns.names != b.columns.names:
        out.append("columns")
        return out
    if not _same_cell(dict(a.attrs), dict(b.attrs)) or \
            [type(v).__name__ for v in a.attrs.values()] != [type(v).__name__ for v in b.attrs.values()]:
        out.append("attrs")
    for i in range(a.shape[1]):
        x, y = a.iloc[:, i], b.iloc[:, i]
        if x.dtype != y.dtype:
            out.append(f"dtype:{a.columns[i]!r}:{x.dtype}!={y.dtype}")
            continue
        if x.dtype == object:
            for r, (u, v) in enumerate(zip(x.to_numpy(), y.to_numpy())):
                if not _same_cell(u, v):
                    out.append(f"cell:{a.columns[i]!r}:{r}:{u!r}!={v!r}")
                    break
        else:
            xa, ya = x.to_numpy(), y.to_numpy()
            if xa.dtype.kind == "f":
                same = np.array_equal(xa, ya, equal_nan=True) and np.array_equal(np.signbit(xa), np.signbit(ya))
            elif xa.dtype.kind in "Mm":
                same = np.array_equal(xa.view("i8"), ya.view("i8"))
            else:
                try:
                    same = bool(x.equals(y))
                except Exception:
                    same = False
            if not same:
                out.append(f"values:{a.columns[i]!r}")
        if len(out) >= limit:
            break
    return out
