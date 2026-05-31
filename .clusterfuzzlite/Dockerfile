# ClusterFuzzLite Build Container
# This Dockerfile builds the fuzz targets for ClusterFuzzLite
#
# Reference: https://google.github.io/clusterfuzzlite/build-integration/python/

# SCORECARD:Pinned-Dependencies: Pin this image by SHA digest.
# Run: docker pull gcr.io/oss-fuzz-base/base-builder-python:v1
#      docker inspect gcr.io/oss-fuzz-base/base-builder-python:v1 --format '{{index .RepoDigests 0}}'
# Then replace with: FROM gcr.io/oss-fuzz-base/base-builder-python@sha256:<digest>  # v1
FROM gcr.io/oss-fuzz-base/base-builder-python:v1

# Copy project source
COPY . $SRC/audio_processor
WORKDIR $SRC/audio_processor

# Install dependencies for fuzzing
# SCORECARD:Pinned-Dependencies: Pin atheris to a specific version with hash.
# Run: pip download atheris==<ver> && pip hash atheris-<ver>*.whl
# Then use: pip3 install 'atheris==<ver>' --hash=sha256:<hash>
RUN pip3 install --upgrade pip && \
    pip3 install atheris && \
    pip3 install -e .

# Copy build script
COPY .clusterfuzzlite/build.sh $SRC/
