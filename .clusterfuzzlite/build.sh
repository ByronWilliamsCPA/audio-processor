#!/bin/bash -eu
# ClusterFuzzLite Build Script
# Compiles Python fuzz targets with coverage instrumentation
#
# Reference: https://google.github.io/clusterfuzzlite/build-integration/python/

# Install atheris fuzzing engine
# SCORECARD:Pinned-Dependencies: Add version pin and hash for reproducible fuzz builds.
# Run: pip download atheris==<ver> && pip hash atheris-<ver>*.whl
# Then replace with: pip3 install 'atheris==<ver>' --hash=sha256:<hash>
pip3 install atheris

# Install the package with fuzzing support
pip3 install -e .

# Copy fuzz targets to the output directory
# Each Python file in fuzz/ directory becomes a fuzz target
for fuzzer in $SRC/audio_processor/fuzz/fuzz_*.py; do
    if [ -f "$fuzzer" ]; then
        fuzzer_basename=$(basename -s .py $fuzzer)
        cp $fuzzer $OUT/$fuzzer_basename
        chmod +x $OUT/$fuzzer_basename
        echo "Copied fuzzer: $fuzzer_basename"
    fi
done

# Verify at least one fuzzer was copied
if [ -z "$(ls -A $OUT/fuzz_* 2>/dev/null)" ]; then
    echo "ERROR: No fuzz targets were copied to $OUT"
    echo "Contents of $SRC/audio_processor/fuzz/:"
    ls -la $SRC/audio_processor/fuzz/ || true
    exit 1
fi

echo "Successfully built fuzz targets:"
ls -la $OUT/fuzz_*
