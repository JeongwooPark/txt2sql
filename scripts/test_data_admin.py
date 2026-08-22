"""데이터 관리 식별자·ZIP 검사."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from llm2sql.config import Settings
from llm2sql.data.names import (
    create_column_description,
    extract_display_name_and_unit,
    is_protected_table,
    is_safe_ident,
    parse_al_table_name,
    split_schema_table,
    table_from_shapefile,
)
from llm2sql.data.upload import process_zip_upload


def main() -> int:
    failed: list[str] = []
    passed = 0

    def ok(name: str, cond: bool, detail: str = "") -> None:
        nonlocal passed
        if cond:
            passed += 1
            print(f"[ok] {name}")
        else:
            failed.append(f"{name}: {detail}")
            print(f"[fail] {name} {detail}")

    ok("ident al d198", is_safe_ident("AL_D198_26_20250704"))
    ok("ident reject sql", not is_safe_ident("AL;drop"))
    ok("protect metadata", is_protected_table("table_metadata"))
    ok("protect temp", is_protected_table("temp_abc"))
    ok("allow building", not is_protected_table("AL_D010_26_20250704"))

    schema, table = split_schema_table("public.AL_D198_26_20250704")
    ok("split schema", schema == "public" and table.startswith("AL_D198"))
    try:
        split_schema_table("public.table_metadata")
        ok("reject metadata table", False, "should raise")
    except ValueError:
        ok("reject metadata table", True)

    ok("shp stem", table_from_shapefile("AL_D198_26_20250704.shp") == "AL_D198_26_20250704")
    parsed = parse_al_table_name("AL_D198_26_20250704")
    ok("parse code", parsed is not None and parsed["data_code"] == "AL_D198")
    ok("parse date", bool(parsed and parsed["formatted_date"].startswith("2025")))
    ok("parse short", parse_al_table_name("BND_ADM_DONG_PG") is None)

    from llm2sql.data.coverage import register_uploaded_dataset
    from llm2sql.domain import (
        d198_coverage_label,
        d198_gu_mentioned,
        d198_table_for_gu,
        gu_from_d198_table,
        reset_d198_coverage,
        set_d198_coverage,
    )
    from llm2sql.sql_validator import diagnose_sql

    ok("pnu namgu", gu_from_d198_table("AL_D198_26290_20250704") == "남구")
    ok("pnu dongrae", gu_from_d198_table("AL_D198_26260_20250115") == "동래구")
    ok("pnu citywide none", gu_from_d198_table("AL_D198_26_20250704") is None)
    ok("register hook", callable(register_uploaded_dataset))

    namgu_table = "AL_D198_26290_20250115"
    try:
        set_d198_coverage(
            {
                "동래구": "AL_D198_26260_20250115",
                "금정구": "AL_D198_26410_20250115",
                "남구": namgu_table,
            }
        )
        ok("namgu mapped", d198_table_for_gu("남구") == namgu_table)
        ok(
            "namgu mentioned",
            d198_gu_mentioned("남구 용도별건물 사용승인") == "남구",
        )
        ok("namgu stem skip", d198_gu_mentioned("남향 건물") is None)
        ok("label has namgu", "남구" in d198_coverage_label())
        diag = diagnose_sql(
            "남구 용도별건물 건수는?",
            f'SELECT COUNT(*) FROM "{namgu_table}";',
        )
        ok("validator allows namgu d198", diag is None)
        diag2 = diagnose_sql(
            "해운대구 건물 건수는?",
            f'SELECT COUNT(*) FROM "{namgu_table}";',
        )
        ok("validator rejects haeundae d198", diag2 is not None)
        from llm2sql.intent_router import fix_common_sql_mistakes

        kept = fix_common_sql_mistakes(
            f'SELECT COUNT(*) FROM "{namgu_table}";',
            "남구 용도별건물 건수는?",
        )
        ok("router keeps namgu d198", namgu_table in kept)
        swapped = fix_common_sql_mistakes(
            f'SELECT COUNT(*) FROM "{namgu_table}";',
            "해운대구 건물 건수는?",
        )
        ok("router swaps haeundae d198", "AL_D010_26_20250704" in swapped)
    finally:
        reset_d198_coverage()
    ok("default namgu gone", d198_table_for_gu("남구") is None)
    ok("default dongrae kept", d198_table_for_gu("동래구") is not None)

    display, unit = extract_display_name_and_unit("건축물면적(㎡)")
    ok("unit paren", display == "건축물면적" and unit == "㎡")
    ok("desc sample", create_column_description("아파트", None) == "예시: 아파트")
    ok("desc skip nan", create_column_description("nan", "nan") == "")

    settings = Settings(database_url="postgresql://x:x@127.0.0.1/x")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "no shapefile")
    try:
        process_zip_upload(settings, filename="empty.zip", content=buf.getvalue())
        ok("zip without shp", False, "should raise")
    except ValueError as exc:
        ok("zip without shp", "SHP" in str(exc))

    try:
        process_zip_upload(settings, filename="data.shp", content=b"abc")
        ok("reject non zip", False)
    except ValueError:
        ok("reject non zip", True)

    html = (
        Path(__file__).resolve().parents[1]
        / "llm2sql"
        / "webapp"
        / "static"
        / "data_upload.html"
    ).read_text(encoding="utf-8")
    ok("upload posts api", "/api/data/upload" in Path(
        Path(__file__).resolve().parents[1]
        / "llm2sql"
        / "webapp"
        / "static"
        / "js"
        / "data-upload.js"
    ).read_text(encoding="utf-8"))
    upload_js = (
        Path(__file__).resolve().parents[1]
        / "llm2sql"
        / "webapp"
        / "static"
        / "js"
        / "data-upload.js"
    ).read_text(encoding="utf-8")
    ok("upload wired status", "d198_coverage" in upload_js)
    ok("upload zip input", 'id="shapefile-input"' in html)
    meta_js = (
        Path(__file__).resolve().parents[1]
        / "llm2sql"
        / "webapp"
        / "static"
        / "js"
        / "data-metadata.js"
    ).read_text(encoding="utf-8")
    ok("metadata save api", "/api/data/metadata" in meta_js)
    ok("parse api", "/parse" in meta_js)

    print(f"\npassed={passed} failed={len(failed)}")
    for item in failed:
        print(" -", item)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
