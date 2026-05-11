"""Pydantic models for migration complexity analysis."""

from typing import Optional

from pydantic import BaseModel, Field


class UDFRecord(BaseModel):
    name: str
    language: str = Field(description="SQL | Python | Java | C | JavaScript | R | proprietary")
    is_portable: bool = Field(description="can it be rewritten as a Spark UDF without logic changes?")


class StoredProcRecord(BaseModel):
    name: str
    line_count: int
    has_loops: bool = Field(description="cursor loops, WHILE, FOR — these need PySpark rewrite")
    has_external_calls: bool = Field(description="HTTP, file system, email")
    has_ddl: bool = Field(description="creates/drops tables inside the proc")
    migration_path: str = Field(description="notebook | workflow_task | sql_udf")


class BinaryColumnRecord(BaseModel):
    table: str
    column: str
    data_type: str = Field(description="BLOB, BYTEA, RAW, VARBINARY, HIERARCHYID, GEOMETRY, etc.")
    migration_path: str = Field(description="base64_string | wkt_string | custom_parser | unsupported")


class MigrationComplexitySignals(BaseModel):
    platform: str
    udf_count: int = 0
    udf_records: list[UDFRecord] = Field(default=[])
    stored_proc_count: int = 0
    stored_proc_records: list[StoredProcRecord] = Field(default=[])
    trigger_count: int = 0
    sequence_count: int = Field(default=0, description="sequences / identity columns")
    cross_db_join_count: int = Field(default=0, description="queries joining across database boundaries")
    binary_column_count: int = 0
    binary_column_records: list[BinaryColumnRecord] = Field(default=[])
    proprietary_type_count: int = Field(default=0, description="types with no Delta equivalent")
    linked_server_count: int = Field(default=0, description="SQL Server: linked server dependencies")
    dblink_count: int = Field(default=0, description="Oracle: db link dependencies")
    estimated_migration_weeks: float = 0.0
    has_unsupported_types: bool = False
