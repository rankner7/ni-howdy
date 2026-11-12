# Taiwan guided stroke templates

Guided practice uses outlines and ordered pen tracks from the Republic of China
(Taiwan) Ministry of Education, archived by
[g0v/zh-stroke-data](https://github.com/g0v/zh-stroke-data). The archive identifies
the MOE stroke-order service as its source. These are separate from the Make Me
a Hanzi geometry used by the other drawing levels.

Original source: [中華民國教育部 國字標準字體筆順學習網](https://stroke-order.learningweb.moe.edu.tw/).
The MOE retains copyright. Its [usage notice](https://stroke-order.learningweb.moe.edu.tw/page.jsp?ID=52&la=1)
restricts use to noncommercial teaching and identifies its animations and
stroke-order hints as CC BY-NC-ND 3.0 Taiwan. The archive separately describes
how it obtained the XML for nonprofit education; it does not claim a general
open-source license for those data. This application is for personal learning.
Do not treat the templates as unrestricted assets for redistribution.

`python3 scripts/prepare_taiwan.py` downloads the source archive and imports its
XML-backed JSON entries. Synthetic entries from the archive's `missing/` set
are excluded. Import never reads or rewrites the existing `data/` directory.
It retains stroke order and direction, converts the coordinate system for a
1024-unit canvas, and writes the compact offline asset atomically. When outline
control points or pen tracks extend beyond the nominal 2000-unit source box,
the entire character is fitted with one uniform scale and translation. This
preserves stroke proportions and direction without clamping individual points.
Characters already inside the source box keep their existing placement.
Malformed and non-finite coordinates are still excluded. A local
source `.tar.gz` may be supplied instead of downloading. Preparation failures
leave the previous asset intact.

The initial bundled subset was retrieved from the archive's `master/json/`
files on 2026-11-12: `4e00.json` (一), `6211.json` (我), and `6728.json` (木).
In particular, 我 has the Taiwan sequence with the dot before the final
left-falling stroke. Preparation replaces that subset with the available
archive catalog. No PRC template is silently
substituted when a Taiwan character is absent.

The archive predates the current MOE site's additions and is not a complete
copy of its current catalog. Coordinate conversion and automated tests are
not a native-teacher audit of every glyph.
