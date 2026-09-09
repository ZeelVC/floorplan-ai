# Orientation benchmark manifest

This manifest maps the supplied benchmark original media to the M5 contract:
Trial 1 has twelve horizontal photos plus `1000177529.mp4`; Trial 2 has twelve
vertical photos plus `1000177534.mp4`. Their three room associations and the
separate evaluation workbook reference are explicit manifest data.

Original customer/benchmark photos, videos, and ground-truth workbook are not
committed to this repository. Copy them to the exact manifest paths before
running `load_dataset`; the manifest deliberately fails validation if they are
not present. The workbook remains evaluation-only and is not part of the
inference capture collection.
