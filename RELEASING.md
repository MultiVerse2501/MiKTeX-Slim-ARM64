# Releasing

Produce and publish a release. Run from the project root on Windows 11 on Arm; the build in [BUILD.md](BUILD.md) has to be finished first — the MiKTeX sandbox plus `recipes\build.cmd biber all` and `recipes\build.cmd ghostscript all`.

In the examples, `<version>` is the dotted release number and `<miktex-tag>` is the upstream MiKTeX version it was built from; the release tag is `v<version>-<miktex-tag>`.

1. Set `version` in [versions.txt](versions.txt) to the next dotted release number. `miktex-tag` has to match the MiKTeX version compiled into `build\include\miktex\Version.h`; a mismatch makes the pack refuse.

2. `arch-scan.cmd` must print `NON_ARM64=0`.

3. `coverage-scan.cmd` must print `MISSING=0`. It reads the package database that a portable bootstrap downloaded; see the script header for the search path and the exclusion list.

4. `portable\pack-portable.cmd` writes `portable\dist\miktex-portable-arm64-v<version>-<miktex-tag>.zip`.

5. `python portable\smoke-test.py --fresh` must print `SMOKE PASS`. It wipes `portable\dist\smoke-run` first, so do not keep a shell inside that directory while it runs.

6. Build the source archive and the checksums. `git archive` runs from the project root; run from a subdirectory it would restrict itself to the files under it:

   ```bat
   git archive --format=zip --prefix=MiKTeX-Slim-ARM64-v<version>-<miktex-tag>/ -o portable\dist\miktex-slim-arm64-v<version>-<miktex-tag>-source.zip HEAD
   cd portable\dist
   powershell -NoProfile -Command "Get-ChildItem *.zip | Get-FileHash -Algorithm SHA256 | ForEach-Object { '{0}  {1}' -f $_.Hash.ToLower(), (Split-Path $_.Path -Leaf) } | Set-Content SHA256SUMS.txt"
   ```

   `SHA256SUMS.txt` ends up covering every zip in the directory; older zips that are not part of this release can be removed first.

7. Commit the release, tag it, and push:

   ```bat
   git add versions.txt RELEASING.md
   git commit -m "Release v<version>-<miktex-tag>."
   git tag -a v<version>-<miktex-tag> -m "MiKTeX Slim v<version> (MiKTeX <miktex-tag>)."
   git push origin main v<version>-<miktex-tag>
   ```

8. Publish the GitHub release for the pushed tag with the portable zip, the source zip, and `SHA256SUMS.txt` attached. The MiKTeX tag in the name is the upstream version the release was built from, not a claim of origin: it is an unofficial build, not a MiKTeX.org release.
