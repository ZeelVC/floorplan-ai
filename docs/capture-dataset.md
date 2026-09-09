# How to prepare a floorplan-ai capture dataset

Milestone 5 accepts **original photos and videos** through a versioned JSON
manifest. It only validates and organizes input; it does not rotate, alter,
calibrate, estimate scale from, or reconstruct any media.

## Directory layout

The dataset directory contains a required `floorplan-dataset.json`. File paths
in it are relative to that directory. Names and directory nesting are your
choice; the manifest, not filename conventions, is authoritative.

```text
customer-capture/
├── floorplan-dataset.json
├── property-a/session-morning/photos/entry-01.jpg
├── property-a/session-morning/videos/walkthrough.mp4
└── evaluation/measurements.xlsx       # optional; evaluation only
```

## Manifest contract (schema version 1.0)

Required fields are `schema_version` (`"1.0"`), `dataset_id`, at least one
`property_id`, at least one `trial_id` per property, and capture `capture_id`,
`source_type`, and `file`. IDs are unique strings of letters, numbers, dots,
hyphens, and underscores. `source_type` is exactly `photo` or `video`.

`room_id`, `sequence`, `orientation`, labels, and `metadata` are optional.
Declare property-level `rooms` only when room identifiers are known; do not
invent rooms. A declared capture `room_id` must resolve to that property's
`rooms`. Omit it when unknown. `sequence` is a non-negative integer. Captures
with a sequence sort first by sequence then ID; captures without one sort by
ID. Properties and trials sort by ID, so loading is deterministic.

Orientation is optional and is an object so its provenance remains clear:
`{"value": "horizontal|vertical|unknown", "source": "declared|derived"}`.
`source: "derived"` means an upstream component or dataset-preparation process
derived and supplied the value; M5 does not visually infer orientation. The
loader never rotates a file. `metadata` is an optional JSON object for
device details, image/video resolution, frame rate, timestamps, EXIF, or camera
information. Missing EXIF is valid and means no metadata prior was supplied.

```json
{
  "schema_version": "1.0",
  "dataset_id": "customer-2026-09",
  "properties": [
    {
      "property_id": "property-a",
      "rooms": [{"room_id": "entry", "label": "Entry"}],
      "trials": [
        {
          "trial_id": "morning",
          "captures": [
            {"capture_id": "photo-01", "source_type": "photo", "file": "property-a/session-morning/photos/entry-01.jpg", "room_id": "entry", "sequence": 1, "orientation": {"value": "vertical", "source": "declared"}, "metadata": {"device": "customer phone"}},
            {"capture_id": "video-01", "source_type": "video", "file": "property-a/session-morning/videos/walkthrough.mp4", "orientation": {"value": "unknown", "source": "derived"}}
          ]
        }
      ]
    }
  ],
  "evaluation": {"ground_truth_file": "evaluation/measurements.xlsx", "format": "xlsx"}
}
```

This is valid only when each referenced original media file exists and is
readable. Photo extensions supported by this lightweight validator are `.jpg`,
`.jpeg`, `.png`, `.heic`, `.heif`, and `.webp`; video extensions are `.mp4`,
`.mov`, `.m4v`, and `.avi`.

## Media validation boundary

M5 validates manifest/schema correctness, safe relative paths, a readable
regular file, supported extensions, and `source_type`/extension compatibility.
It does **not** decode images or video and therefore does not guarantee JPEG or
PNG semantic validity, video container/codec validity, successful decoding,
corruption detection, frame extraction, or visual quality. Those checks belong
to downstream media-processing stages. No image rotation, orientation
correction, camera calibration, or computer-vision processing occurs in M5.

An invalid example is `{ "capture_id": "p1", "source_type":
"image_sequence", "file": "a.jpg" }`: use `photo` for an individual image.
Likewise, a capture with `room_id: "kitchen"` is invalid unless `kitchen` is
listed in its property's `rooms`.

## Ground truth

`evaluation` is optional. It is a pointer for the evaluation API only and is
not included in `load_dataset(...).captures`. Normal customer inference inputs
must be valid without it. Never include laser/tape measurements, floor-plan
answers, PDFs/contact sheets as photo substitutes, or ground truth used to set
scale/calibration as capture inputs. Keep the source workbook separately from
the inference media where practical. When the explicit evaluation helper is
used, a declared ground-truth reference must resolve to a readable regular file;
a missing or unreadable workbook produces a dataset validation error.
