# Bench test data

| Path | What |
|---|---|
| `PowerBoard_Rev3_BenchTest_Log.xlsx` | The test log: procedure steps, limits, verdicts and notes. Also the regulation matrix, eFuse, load-step, outstanding-tests, design-notes and issue-log sheets |
| `AeroDesign_PowerBoard_DVT_EOL_Test_Plan.xlsx` | The original DVT/EOL plan this campaign was cut down from (test IDs map via the `Plan ref` column) |
| `probe_point_map.png` | Where the probe and bodge wires go, generated from the PCB pad data |
| `tools/bench_lib.py` | Instrument layer: KA3005P supply, DHO804 scope and DC-load control, with hard limits, an abort path and a monitor thread |
| `results/<date>_<time>_<test>/` | Raw data per run: `data.csv`, `meta.json` (settings, probe map, results), `notes.txt`, scope PNGs, waveform CSVs |
| `scope/` | The latest scope capture per test ID |
| `scope_annotated/` | Every capture in `scope/` with a title, the test conditions, a channel legend (signal, probe point, scale, coupling) and call-outs. |

Runs are kept as recorded, including aborted and superseded ones. Every abort is explained in its `notes.txt` and
in the Issue Log. The values quoted in the top-level README come from the runs named in the log's notes column.

The instrument drivers (`bench.instruments.*`) come from the
[dc-electronic-load](https://github.com/WeymenKoo/dc-electronic-load) repository's `bench_test/` folder.
