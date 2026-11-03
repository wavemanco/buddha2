# The offline builder verifies this local alias against immutable image ID
# sha256:8792a096b4881d47ab19cc7cbf6a74a232f9ff7cedc978fe93f902a71522d4f2.
FROM buddha2-h1-base:8792a096b488
RUN --mount=type=bind,source=runtime.py,target=/h1-runtime.py,readonly python -B /h1-runtime.py patch
