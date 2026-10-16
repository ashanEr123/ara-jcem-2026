# Add this release to the existing repository

This ZIP is an overlay, not a complete replacement for the existing repository. Nothing has been pushed to GitHub automatically.

1. Open VS Code and its PowerShell terminal. Create a fresh clone and branch:

```powershell
cd D:\RAGBOT
git clone https://github.com/ashanEr123/ara-jcem-2026.git ara-jcem-2026-release
cd ara-jcem-2026-release
git switch -c revision-r2-release
```

2. Extract the ZIP elsewhere. Copy the CONTENTS of `ARA_GitHub_R2_Release` into the clone. Replace the root README with this version. Merge the supplied `.gitignore` entries with any existing entries. Preserve existing primary experiment files and LICENSE. Do not copy the enclosing release folder as an extra nested directory.

3. Run the offline analysis using the README commands. To verify the supplied release hashes before making any changes, run:

```powershell
python verify_release.py
```

4. Stage only this release's paths:

```powershell
git status --short
git add README.md .gitignore COMMIT_GUIDE.md RELEASE_NOTES_R2.md verify_release.py R2_RELEASE_SHA256.json
git add experiments/r2_rerun/ docs/ARA_R2_supplement.docx
git diff --cached --stat
git diff --cached
```

The review should show code, numeric data, instructions and the clean supplement. Source PDFs, `.env`, OCR text, vector databases and raw answer logs are not part of this package. Existing tracked files are not removed by `.gitignore`.

5. Commit and upload your branch:

```powershell
git commit -m "Add completed R2 evaluation and reproducible supplementary analysis"
git push -u origin revision-r2-release
```

6. Open the repository in GitHub, choose Compare & pull request, review the changes, and merge. A push uploads the branch; a commit alone only records local changes. If Git requests authentication, complete its normal GitHub sign-in. Do not place a token in a file or repository URL.

Suggested pull-request description:

> Adds the completed supplementary rerun, anonymous independent ratings, and offline analysis. Includes 540 completed trials and one archived failed attempt, updated Evaluator 2 B050/B054 counts, and 200 equal-context comparisons. Keeps primary and supplementary experiments separate. Private corpus text and credentials are excluded; the README explains the resulting reproducibility limits.

The checksum manifest covers this release overlay, not pre-existing repository files. If you deliberately edit a covered file, its checksum will no longer match. Keep the original manifest with the release for provenance, or regenerate it and record your changes before publishing a new version.
