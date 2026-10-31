# Change study: 3 complete run(s) [1, 2, 3]

## synthetic

| Group | ACE | AWM | G-Memory | MAVRA |
|---|---|---|---|---|
| holdout | 100.0% [100–100] · 15.8k tok · 4s | 66.7% [67–67] · 35.3k tok · 19s | 72.2% [67–83] · 28.1k tok · 11s | 100.0% [100–100] · 14.7k tok · 5s |
| non_breaking | 95.8% [88–100] · 25.2k tok · 10s | 47.9% [38–62] · 57.3k tok · 35s | 45.8% [31–62] · 59.0k tok · 32s | 100.0% [100–100] · 13.0k tok · 6s |
| covered_breaks | 68.2% [59–77] · 43.3k tok · 20s | 40.9% [32–45] · 57.7k tok · 44s | 43.9% [36–50] · 60.4k tok · 34s | 97.0% [95–100] · 19.2k tok · 23s |
| outside_conditions | 79.2% [62–88] · 57.3k tok · 32s | 25.0% [12–38] · 95.9k tok · 71s | 29.2% [12–50] · 89.1k tok · 51s | 20.8% [0–38] · 37.9k tok · 27s |
| all | 82.1% [77–88] · 36.7k tok · 17s | 43.6% [35–52] · 60.9k tok · 42s | 45.5% [42–48] · 60.7k tok · 33s | 86.5% [83–88] · 19.7k tok · 16s |

## tpch

| Group | ACE | AWM | G-Memory | MAVRA |
|---|---|---|---|---|
| holdout | 100.0% [100–100] · 14.4k tok · 4s | 100.0% [100–100] · 16.0k tok · 6s | 100.0% [100–100] · 19.6k tok · 6s | 100.0% [100–100] · 10.8k tok · 4s |
| non_breaking | 94.4% [92–100] · 24.1k tok · 12s | 97.2% [92–100] · 22.4k tok · 13s | 97.2% [92–100] · 24.6k tok · 11s | 100.0% [100–100] · 11.0k tok · 13s |
| covered_breaks | 64.6% [50–75] · 31.8k tok · 20s | 60.4% [56–69] · 36.0k tok · 23s | 75.0% [75–75] · 24.1k tok · 12s | 75.0% [75–75] · 17.7k tok · 124s |
| outside_conditions | 61.1% [50–67] · 39.1k tok · 21s | 61.1% [50–67] · 38.8k tok · 27s | 83.3% [67–100] · 36.1k tok · 19s | 33.3% [33–33] · 22.5k tok · 35s |
| all | 78.3% [70–85] · 28.0k tok · 15s | 77.5% [75–82] · 29.3k tok · 18s | 86.7% [85–88] · 25.4k tok · 12s | 80.0% [80–80] · 15.4k tok · 60s |

## both

| Group | ACE | AWM | G-Memory | MAVRA |
|---|---|---|---|---|
| holdout | 100.0% [100–100] · 15.1k tok · 4s | 83.3% [83–83] · 25.6k tok · 13s | 86.1% [83–92] · 23.8k tok · 9s | 100.0% [100–100] · 12.8k tok · 4s |
| non_breaking | 95.2% [89–100] · 24.7k tok · 11s | 69.0% [64–79] · 42.4k tok · 25s | 67.9% [61–79] · 44.3k tok · 23s | 100.0% [100–100] · 12.1k tok · 9s |
| covered_breaks | 66.7% [63–71] · 38.4k tok · 20s | 49.1% [47–50] · 48.5k tok · 35s | 57.0% [53–61] · 45.1k tok · 25s | 87.7% [87–89] · 18.6k tok · 65s |
| outside_conditions | 71.4% [64–79] · 49.5k tok · 27s | 40.5% [36–43] · 71.4k tok · 52s | 52.4% [36–71] · 66.4k tok · 37s | 26.2% [14–36] · 31.3k tok · 31s |
| all | 80.4% [78–83] · 32.9k tok · 16s | 58.3% [55–62] · 47.2k tok · 32s | 63.4% [62–65] · 45.3k tok · 24s | 83.7% [82–85] · 17.8k tok · 35s |

## Per change (correct / clarify / wrong over complete runs)

| Schema/change | ACE | AWM | G-Memory | MAVRA |
|---|---|---|---|---|
| synthetic/holdout | 18/0/0 of 18 | 12/0/6 of 18 | 13/0/5 of 18 | 18/0/0 of 18 |
| synthetic/append | 16/0/2 of 18 | 9/0/9 of 18 | 8/0/10 of 18 | 18/0/0 of 18 |
| synthetic/backfill | 6/0/0 of 6 | 1/1/4 of 6 | 1/0/5 of 6 | 6/0/0 of 6 |
| synthetic/correct | 18/0/0 of 18 | 12/0/6 of 18 | 12/0/6 of 18 | 18/0/0 of 18 |
| synthetic/addcol | 6/0/0 of 6 | 1/0/5 of 6 | 1/0/5 of 6 | 6/0/0 of 6 |
| synthetic/status | 6/0/0 of 6 | 2/0/4 of 6 | 1/0/5 of 6 | 6/0/0 of 6 |
| synthetic/revision | 15/0/3 of 18 | 10/0/8 of 18 | 11/0/7 of 18 | 18/0/0 of 18 |
| synthetic/dupload | 13/0/5 of 18 | 9/0/9 of 18 | 11/0/7 of 18 | 16/0/2 of 18 |
| synthetic/dimhist | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 |
| synthetic/latekey | 5/0/13 of 18 | 0/0/18 of 18 | 0/0/18 of 18 | 18/0/0 of 18 |
| synthetic/unit | 13/0/5 of 18 | 6/0/12 of 18 | 7/0/11 of 18 | 1/0/17 of 18 |
| synthetic/mirror | 6/0/0 of 6 | 0/0/6 of 6 | 0/0/6 of 6 | 4/0/2 of 6 |
| tpch/holdout | 18/0/0 of 18 | 18/0/0 of 18 | 18/0/0 of 18 | 18/0/0 of 18 |
| tpch/append | 11/0/1 of 12 | 11/0/1 of 12 | 11/0/1 of 12 | 12/0/0 of 12 |
| tpch/backfill | 5/0/1 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 |
| tpch/correct | 12/0/0 of 12 | 12/0/0 of 12 | 12/0/0 of 12 | 12/0/0 of 12 |
| tpch/addcol | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 |
| tpch/status | 6/0/0 of 6 | 5/0/1 of 6 | 6/0/0 of 6 | 6/0/0 of 6 |
| tpch/revision | 9/0/3 of 12 | 7/0/5 of 12 | 12/0/0 of 12 | 12/0/0 of 12 |
| tpch/dupload | 10/0/2 of 12 | 11/0/1 of 12 | 12/0/0 of 12 | 12/0/0 of 12 |
| tpch/dimhist | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 |
| tpch/latekey | 0/0/12 of 12 | 0/0/12 of 12 | 0/0/12 of 12 | 0/12/0 of 12 |
| tpch/unit | 7/0/5 of 12 | 6/0/6 of 12 | 9/0/3 of 12 | 0/0/12 of 12 |
| tpch/mirror | 4/0/2 of 6 | 5/0/1 of 6 | 6/0/0 of 6 | 6/0/0 of 6 |

Cost: CNY 27.53 charged over 7889 calls (0 errors).
