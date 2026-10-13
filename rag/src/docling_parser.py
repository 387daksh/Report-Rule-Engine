"""
docling_parser.py
-----------------
IBM Docling (2024-2026) Multimodal Document Intelligence Parser.
Paper: Auer et al., 'Docling Technical Report' (arXiv:2408.09869, 2024).

Features:
  - Ingests native & scanned PDFs, DOCX, XLSX, HTML, and Images
  - Preserves layout hierarchy (DocLayNet layout analysis)
  - Extracts complex multi-row/column audit tables into structured Markdown/DataFrames (TableFormer)
  - Captions and indexes figures, network diagrams, and vulnerability charts
  - Provides graceful offline fallback for plain-text or when Docling is unavailable
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("audit_rag.docling_parser")


@dataclass
class ParsedTable:
    table_id: str
    caption: str
    markdown: str
    row_count: int
    col_count: int


@dataclass
class ParsedReport:
    report_id: str
    file_path: str
    full_text: str
    tables: List[ParsedTable] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    has_images: bool = False
    source_format: str = "txt"


class AuditDocumentParser:
    """Multimodal document parser using IBM Docling with local fallback."""

    def __init__(self, enable_ocr: bool = True):
        self.enable_ocr = enable_ocr
        self._docling_available = self._check_docling()

    def _check_docling(self) -> bool:
        try:
            import docling
            from docling.document_converter import DocumentConverter
            return True
        except ImportError:
            logger.info("Docling package not installed. Running in text-fallback mode.")
            return False

    def parse(self, file_path: str, report_id: Optional[str] = None) -> ParsedReport:
        path = Path(file_path)
        rid = report_id or path.stem
        suffix = path.suffix.lower()

        if suffix == ".json":
            return self._parse_json(path, rid)

        if suffix in [".txt", ".md"] or not self._docling_available:
            return self._parse_text_fallback(path, rid)

        try:
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions

            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_table_structure = True
            pipeline_options.do_ocr = self.enable_ocr

            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )

            result = converter.convert(str(path))
            doc = result.document

            # Extract markdown text preserving headings & hierarchy
            full_text = doc.export_to_markdown()

            # Extract structured tables
            parsed_tables = []
            for idx, table in enumerate(doc.tables):
                df = table.to_dataframe()
                md_table = df.to_markdown(index=False)
                caption = table.caption_text(doc) if hasattr(table, "caption_text") else f"Table {idx + 1}"
                parsed_tables.append(
                    ParsedTable(
                        table_id=f"{rid}_table_{idx + 1}",
                        caption=caption or f"Table {idx + 1}",
                        markdown=md_table,
                        row_count=len(df),
                        col_count=len(df.columns),
                    )
                )

            return ParsedReport(
                report_id=rid,
                file_path=str(path),
                full_text=full_text,
                tables=parsed_tables,
                metadata={"title": doc.name if hasattr(doc, "name") else rid},
                has_images=len(getattr(doc, "pictures", [])) > 0,
                source_format=suffix.lstrip("."),
            )

        except Exception as e:
            logger.warning("Docling conversion failed for %s (%s). Falling back to text.", path, e)
            return self._parse_text_fallback(path, rid)

    def _parse_text_fallback(self, path: Path, report_id: str) -> ParsedReport:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception as e:
            logger.error("Failed to read file %s: %s", path, e)
            text = ""

        return ParsedReport(
            report_id=report_id,
            file_path=str(path),
            full_text=text,
            tables=[],
            metadata={},
            has_images=False,
            source_format=path.suffix.lower().lstrip(".") or "txt",
        )

    def _parse_json(self, path: Path, report_id: str) -> ParsedReport:
        """Flatten extractor JSON into provenance-labelled text for retrieval.

        The supplied extractor format is recursive and often repeats values at
        the top level. Paths are retained so retrieved evidence remains auditable.
        Image/figure context is intentionally ignored by policy.
        """
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("Failed to read JSON %s: %s", path, e)
            data = {}

        if isinstance(data, dict) and isinstance(data.get("detailed_observations"), list):
            return self._parse_structured_audit_json(path, report_id, data)

        rows: List[str] = []
        seen = set()

        def visit(value: Any, path_parts: List[str]) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    key_text = str(key)
                    lowered = key_text.lower()
                    if any(token in lowered for token in ("image", "figure")):
                        continue
                    visit(child, path_parts + [key_text])
            elif isinstance(value, list):
                for index, child in enumerate(value, 1):
                    visit(child, path_parts + [f"[{index}]"])
            elif value is not None:
                text = str(value).strip()
                if text:
                    row = f"{' > '.join(path_parts)}: {text}"
                    if row not in seen:
                        seen.add(row)
                        rows.append(row)

        visit(data, [])
        return ParsedReport(
            report_id=report_id,
            file_path=str(path),
            full_text="\n".join(rows),
            metadata=data.get("_meta", {}) if isinstance(data, dict) else {},
            has_images=False,
            source_format="json",
        )

    def _parse_structured_audit_json(self, path: Path, report_id: str, data: dict) -> ParsedReport:
        """Serialize the extractor's canonical finding schema without duplicating summaries."""
        rows = []
        meta = data.get("report_meta", {})
        for key in ("report_title", "report_type", "report_release_date", "audit_type", "classification"):
            if meta.get(key):
                rows.append(f"REPORT > {key}: {meta[key]}")

        for key in ("introduction", "engagement_scope", "audit_timeline", "methodology", "executive_summary"):
            value = data.get(key)
            if value:
                rows.append(f"{key.upper()}:\n{self._compact_json_text(value)}")

        for finding in data["detailed_observations"]:
            if not isinstance(finding, dict):
                continue
            fid = finding.get("finding_id", "UNKNOWN")
            title = finding.get("title", "Untitled finding")
            rows.append(f"FINDING {fid} | {title}")
            for key in (
                "status", "severity", "cvss_score", "cvss_vector", "cwe", "affected_asset",
                "observation_description", "preconditions", "impact", "likely_root_cause",
                "recommendation", "reference", "new_or_repeat", "proof_of_concept_steps",
            ):
                value = finding.get(key)
                if value not in (None, "", [], {}):
                    rows.append(f"FINDING {fid} > {key}: {self._compact_json_text(value)}")

        return ParsedReport(
            report_id=report_id,
            file_path=str(path),
            full_text="\n\n".join(rows),
            metadata={**meta, "source_file": str(path)},
            has_images=False,
            source_format="json",
        )

    @staticmethod
    def _compact_json_text(value: Any) -> str:
        if isinstance(value, list):
            return "; ".join(
                AuditDocumentParser._compact_json_text(v)
                for v in value
                if not (isinstance(v, str) and v.strip().startswith("[IMAGE_"))
            )
        if isinstance(value, dict):
            return "; ".join(f"{k}: {AuditDocumentParser._compact_json_text(v)}" for k, v in value.items())
        return str(value).replace("\n", " ").strip()


def parse_document(file_path: str, report_id: Optional[str] = None) -> ParsedReport:
    parser = AuditDocumentParser()
    return parser.parse(file_path, report_id=report_id)
