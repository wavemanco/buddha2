# Offline host launch-test correction

An early offline host test imported Linux-default output paths before supplying the Windows output root. Its temporary-fixture setup created the empty directory `C:\results\phase3a-h1-integrated-v1`. Only that exact, validated, empty directory was removed with a non-recursive directory deletion; the `C:\results` parent was left unchanged. No original Buddha2 path was accessed.

The test also passed positional arguments to PowerShell `-Command`, which concatenated them into script text and caused a parser failure. Corrected tests write temporary public fixture scripts and invoke `-File` with native argument arrays. Actual Windows verification supplies `BUDDHA2_OUTPUT_ROOT=C:\Users\arvik\code\research\Buddha2\runs` before Python imports; the tests additionally locate host fixtures explicitly beneath that research run root.

All five launch boundary tests subsequently passed on Windows, including PS5.1 bootstrap parsing/private input rejection and PS7 lexical private/stream exclusion plus reparse-ancestor rejection. This was offline test-harness work: no keys, provider requests or provider run were involved. This note is evidence only and does not authorize a live launch.
