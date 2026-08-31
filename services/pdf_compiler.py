"""
LaTeX to PDF compiler using pdflatex.

Input: LaTeX source string.
Output: PDF bytes on success, or raises RuntimeError with the pdflatex log on failure.

Runs pdflatex twice (standard practice for cross-references to resolve correctly).
Cleans up all temp files after compilation.
"""

import os
import subprocess
import tempfile
import logging

logger = logging.getLogger(__name__)


def compile_latex(latex_source: str) -> bytes:
    """
    Compile a LaTeX string to PDF bytes.

    Writes the source to a temp .tex file, runs pdflatex twice,
    reads the resulting PDF, then removes all temp files.

    Raises RuntimeError with pdflatex log output if compilation fails.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "resume.tex")
        pdf_path = os.path.join(tmpdir, "resume.pdf")
        log_path = os.path.join(tmpdir, "resume.log")

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_source)

        compile_cmd = [
            "pdflatex",
            "-interaction=nonstopmode",
            "-output-directory", tmpdir,
            tex_path,
        ]

        for run_number in range(2):
            try:
                result = subprocess.run(
                    compile_cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=tmpdir,
                )
                logger.debug(f"pdflatex run {run_number + 1} exit code: {result.returncode}")
            except subprocess.TimeoutExpired:
                raise RuntimeError("pdflatex timed out after 120 seconds. The LaTeX source may have an infinite loop.")
            except FileNotFoundError:
                raise RuntimeError(
                    "pdflatex not found. Install texlive-latex-base or run the Render build command locally."
                )

        if not os.path.exists(pdf_path):
            log_content = ""
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8", errors="replace") as lf:
                    log_content = lf.read()

            error_lines = [
                line for line in log_content.splitlines()
                if line.startswith("!") or "Error" in line or "undefined" in line.lower()
            ]
            readable_error = "\n".join(error_lines[:20]) if error_lines else log_content[-2000:]
            raise RuntimeError(f"pdflatex failed to produce a PDF.\n\nRelevant errors:\n{readable_error}")

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        return pdf_bytes
