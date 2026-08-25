"""데이터 관리: Shapefile 업로드와 메타데이터 편집."""

from txt2sql.data.catalog import (
    get_table_display_name,
    get_table_metadata,
    get_table_structure,
    list_spatial_tables,
    parse_table_code,
    rename_table,
    update_table_metadata,
)
from txt2sql.data.names import (
    extract_display_name_and_unit,
    is_protected_table,
    is_safe_ident,
    parse_al_table_name,
    split_schema_table,
    table_from_shapefile,
)
from txt2sql.data.router import create_data_router
from txt2sql.data.upload import process_zip_upload

__all__ = [
    "create_data_router",
    "extract_display_name_and_unit",
    "get_table_display_name",
    "get_table_metadata",
    "get_table_structure",
    "is_protected_table",
    "is_safe_ident",
    "list_spatial_tables",
    "parse_al_table_name",
    "parse_table_code",
    "process_zip_upload",
    "rename_table",
    "split_schema_table",
    "table_from_shapefile",
    "update_table_metadata",
]
