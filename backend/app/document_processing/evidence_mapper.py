"""EvidenceMapper — attach page/bbox provenance to field candidates."""

from __future__ import annotations

from app.document_processing.intelligence_types import FieldCandidate, PageText


class EvidenceMapper:
    name = "evidence_mapper"

    def map_fields(self, fields: list[FieldCandidate], pages: list[PageText]) -> list[FieldCandidate]:
        by_page = {p.page_number: p for p in pages}
        out: list[FieldCandidate] = []
        for f in fields:
            if f.page_number and f.page_number in by_page and f.bbox is None:
                page = by_page[f.page_number]
                needle = f.raw_value.strip().casefold()
                for b in page.blocks:
                    if needle and needle in (b.get("text") or "").casefold():
                        box = b.get("bbox")
                        if box and len(box) == 4:
                            from app.document_processing.intelligence_types import BBox

                            f.bbox = BBox(
                                x0=float(box[0]),
                                y0=float(box[1]),
                                x1=float(box[2]),
                                y1=float(box[3]),
                                coordinate_space=b.get("coordinate_space") or "pdf_page_points",
                            )
                        break
            if f.page_number and not f.page_reference:
                f.page_reference = f"p.{f.page_number}"
            out.append(f)
        return out
