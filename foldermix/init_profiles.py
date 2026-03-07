from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InitProfile:
    slug: str
    summary: str
    rationale: str
    pack_values: dict[str, object]
    stats_values: dict[str, object]


def _build_profile(
    *,
    slug: str,
    summary: str,
    rationale: str,
    include_ext: list[str],
    on_oversize: str,
    continue_on_error: bool,
    redact: str,
    strip_frontmatter: bool,
    pdf_ocr: bool,
    pdf_ocr_strict: bool,
    extra_pack_values: dict[str, object] | None = None,
    extra_stats_values: dict[str, object] | None = None,
) -> InitProfile:
    # Keep include-ext source-of-truth per profile while writing pack/stats TOML sections.
    ext_values = list(include_ext)
    pack_values: dict[str, object] = {
        "include_ext": list(ext_values),
        "hidden": False,
        "respect_gitignore": True,
        "on_oversize": on_oversize,
        "continue_on_error": continue_on_error,
        "redact": redact,
        "strip_frontmatter": strip_frontmatter,
        "include_sha256": True,
        "include_toc": True,
        "pdf_ocr": pdf_ocr,
        "pdf_ocr_strict": pdf_ocr_strict,
    }
    if extra_pack_values:
        pack_values.update(extra_pack_values)

    stats_values: dict[str, object] = {
        "include_ext": list(ext_values),
        "hidden": False,
    }
    if extra_stats_values:
        stats_values.update(extra_stats_values)

    return InitProfile(
        slug=slug,
        summary=summary,
        rationale=rationale,
        pack_values=pack_values,
        stats_values=stats_values,
    )


_LEGAL_EXT = [".txt", ".md", ".pdf", ".docx", ".csv"]
_RESEARCH_EXT = [
    ".txt",
    ".md",
    ".rst",
    ".pdf",
    ".docx",
    ".xlsx",
    ".csv",
    ".tsv",
    ".json",
    ".yaml",
    ".yml",
]
_SUPPORT_EXT = [".txt", ".md", ".json", ".yaml", ".yml", ".csv", ".tsv", ".log"]
_ENGINEERING_DOCS_EXT = [
    ".md",
    ".rst",
    ".txt",
    ".py",
    ".js",
    ".ts",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
]
_COURSE_REFRESH_EXT = [
    ".txt",
    ".md",
    ".rst",
    ".pdf",
    ".docx",
    ".pptx",
    ".ipynb",
    ".xlsx",
    ".csv",
    ".tsv",
    ".json",
    ".yaml",
    ".yml",
]

_PROFILES: dict[str, InitProfile] = {
    "legal": _build_profile(
        slug="legal",
        summary="Privilege-aware document bundles with aggressive redaction defaults.",
        rationale=(
            "Legal matter folders often contain privileged and personal data; this profile favors "
            "privacy-first output while keeping chain-of-custody checksums enabled."
        ),
        include_ext=_LEGAL_EXT,
        on_oversize="truncate",
        continue_on_error=True,
        redact="all",
        strip_frontmatter=True,
        pdf_ocr=True,
        pdf_ocr_strict=False,
    ),
    "research": _build_profile(
        slug="research",
        summary="Broad multimodal ingest for literature-heavy corpora with OCR enabled.",
        rationale=(
            "Research folders are mixed-format and usually benefit from recall-first ingestion; "
            "this profile keeps outputs rich while still masking obvious direct identifiers."
        ),
        include_ext=_RESEARCH_EXT,
        on_oversize="truncate",
        continue_on_error=True,
        redact="emails",
        strip_frontmatter=False,
        pdf_ocr=True,
        pdf_ocr_strict=False,
    ),
    "support": _build_profile(
        slug="support",
        summary="Ticket and runbook context profile with strict PII redaction.",
        rationale=(
            "Support exports commonly include customer identifiers; this profile defaults to full "
            "redaction while preserving lightweight operational formats."
        ),
        include_ext=_SUPPORT_EXT,
        on_oversize="truncate",
        continue_on_error=True,
        redact="all",
        strip_frontmatter=False,
        pdf_ocr=False,
        pdf_ocr_strict=False,
    ),
    "engineering-docs": _build_profile(
        slug="engineering-docs",
        summary="Source-adjacent technical docs profile for repeatable team handoffs.",
        rationale=(
            "Engineering docs usually mix prose and lightweight code examples; this profile keeps "
            "content fidelity high while stripping frontmatter noise from markdown."
        ),
        include_ext=_ENGINEERING_DOCS_EXT,
        on_oversize="skip",
        continue_on_error=False,
        redact="none",
        strip_frontmatter=True,
        pdf_ocr=False,
        pdf_ocr_strict=False,
    ),
    "course-refresh": _build_profile(
        slug="course-refresh",
        summary="High-signal teaching-material profile for refreshing a course offering.",
        rationale=(
            "Course refresh bundles should focus on syllabus, slides, assignments, notebooks, and "
            "other teaching artifacts while excluding grades, rosters, responses, feedback, and "
            "other student/admin material that adds noise or privacy risk."
        ),
        include_ext=_COURSE_REFRESH_EXT,
        on_oversize="truncate",
        continue_on_error=True,
        redact="none",
        strip_frontmatter=False,
        pdf_ocr=True,
        pdf_ocr_strict=False,
        extra_pack_values={
            "exclude_dirs": [
                "Feedbacks",
                "feedbacks",
                "Responses",
                "responses",
                "Grades",
                "grades",
                "Rosters",
                "rosters",
                "Students",
                "students",
                "Submissions",
                "submissions",
            ],
            "exclude_glob": [
                "*[Gg]rade*",
                "*[Rr]oster*",
                "*[Rr]esponse*",
                "*[Ff]eedback*",
                "*[Ss]ubmission*",
                "*[Ss]tudent*",
            ],
        },
    ),
}


def available_profiles() -> tuple[str, ...]:
    return tuple(_PROFILES)


def has_profile(name: str) -> bool:
    return name in _PROFILES


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML value type: {type(value)!r}")


def _render_section(name: str, values: dict[str, object]) -> list[str]:
    lines = [f"[{name}]"]
    for key, value in values.items():
        lines.append(f"{key} = {_toml_value(value)}")
    return lines


def render_profile_config(name: str) -> str:
    profile = _PROFILES[name]
    lines = [
        "# foldermix starter configuration",
        f"# profile: {profile.slug}",
        f"# intent: {profile.summary}",
        f"# rationale: {profile.rationale}",
        "",
        "# Pack defaults for this profile.",
    ]
    lines.extend(_render_section("pack", profile.pack_values))
    lines.append("")
    lines.append("# Stats defaults for this profile.")
    lines.extend(_render_section("stats", profile.stats_values))
    lines.append("")
    return "\n".join(lines)
