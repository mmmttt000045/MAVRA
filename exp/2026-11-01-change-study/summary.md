# Change study: 3 complete run(s) [1, 2, 3]; TeCoD runs [1, 2, 3]; Shared recheck runs [1, 2, 3]

## synthetic

| Group | ACE | AWM | G-Memory | MAVRA | TeCoD | Shared recheck |
|---|---|---|---|---|---|---|
| holdout | 100.0% [100–100] · 15.8k tok · 4s | 66.7% [67–67] · 35.3k tok · 19s | 72.2% [67–83] · 28.1k tok · 11s | 100.0% [100–100] · 14.0k tok · 5s | 100.0% [100–100] · 7.3k tok · 4s | 100.0% [100–100] · 15.9k tok · 6s |
| non_breaking | 95.8% [88–100] · 25.2k tok · 10s | 47.9% [38–62] · 57.3k tok · 35s | 45.8% [31–62] · 59.0k tok · 32s | 100.0% [100–100] · 14.1k tok · 6s | 100.0% [100–100] · 12.2k tok · 8s | 100.0% [100–100] · 16.7k tok · 8s |
| covered_breaks | 68.2% [59–77] · 43.3k tok · 20s | 40.9% [32–45] · 57.7k tok · 44s | 43.9% [36–50] · 60.4k tok · 34s | 98.5% [95–100] · 16.9k tok · 10s | 69.7% [64–77] · 22.6k tok · 20s | 75.8% [73–77] · 43.5k tok · 31s |
| outside_conditions | 79.2% [62–88] · 57.3k tok · 32s | 25.0% [12–38] · 95.9k tok · 71s | 29.2% [12–50] · 89.1k tok · 51s | 75.0% [62–88] · 75.4k tok · 44s | 45.8% [25–62] · 60.3k tok · 45s | 79.2% [62–88] · 55.9k tok · 37s |
| all | 82.1% [77–88] · 36.7k tok · 17s | 43.6% [35–52] · 60.9k tok · 42s | 45.5% [42–48] · 60.7k tok · 33s | 95.5% [94–98] · 24.7k tok · 13s | 78.8% [77–81] · 23.5k tok · 18s | 86.5% [85–88] · 34.0k tok · 22s |

## tpch

| Group | ACE | AWM | G-Memory | MAVRA | TeCoD | Shared recheck |
|---|---|---|---|---|---|---|
| holdout | 100.0% [100–100] · 14.4k tok · 4s | 100.0% [100–100] · 16.0k tok · 6s | 100.0% [100–100] · 19.6k tok · 6s | 100.0% [100–100] · 11.7k tok · 4s | 100.0% [100–100] · 6.5k tok · 4s | 100.0% [100–100] · 11.6k tok · 5s |
| non_breaking | 94.4% [92–100] · 24.1k tok · 12s | 97.2% [92–100] · 22.4k tok · 13s | 97.2% [92–100] · 24.6k tok · 11s | 100.0% [100–100] · 11.9k tok · 12s | 97.2% [92–100] · 13.7k tok · 15s | 100.0% [100–100] · 11.6k tok · 28s |
| covered_breaks | 64.6% [50–75] · 31.8k tok · 20s | 60.4% [56–69] · 36.0k tok · 23s | 75.0% [75–75] · 24.1k tok · 12s | 75.0% [75–75] · 14.1k tok · 27s | 68.8% [56–75] · 19.3k tok · 21s | 72.9% [69–75] · 22.3k tok · 47s |
| outside_conditions | 61.1% [50–67] · 39.1k tok · 21s | 61.1% [50–67] · 38.8k tok · 27s | 83.3% [67–100] · 36.1k tok · 19s | 100.0% [100–100] · 51.6k tok · 48s | 44.4% [33–50] · 33.9k tok · 31s | 83.3% [67–100] · 40.1k tok · 55s |
| all | 78.3% [70–85] · 28.0k tok · 15s | 77.5% [75–82] · 29.3k tok · 18s | 86.7% [85–88] · 25.4k tok · 12s | 90.0% [90–90] · 18.7k tok · 22s | 78.3% [72–82] · 17.9k tok · 18s | 86.7% [85–90] · 20.1k tok · 36s |

## both

| Group | ACE | AWM | G-Memory | MAVRA | TeCoD | Shared recheck |
|---|---|---|---|---|---|---|
| holdout | 100.0% [100–100] · 15.1k tok · 4s | 83.3% [83–83] · 25.6k tok · 13s | 86.1% [83–92] · 23.8k tok · 9s | 100.0% [100–100] · 12.8k tok · 5s | 100.0% [100–100] · 6.9k tok · 4s | 100.0% [100–100] · 13.8k tok · 5s |
| non_breaking | 95.2% [89–100] · 24.7k tok · 11s | 69.0% [64–79] · 42.4k tok · 25s | 67.9% [61–79] · 44.3k tok · 23s | 100.0% [100–100] · 13.2k tok · 8s | 98.8% [96–100] · 12.8k tok · 11s | 100.0% [100–100] · 14.5k tok · 16s |
| covered_breaks | 66.7% [63–71] · 38.4k tok · 20s | 49.1% [47–50] · 48.5k tok · 35s | 57.0% [53–61] · 45.1k tok · 25s | 88.6% [87–89] · 15.7k tok · 17s | 69.3% [63–76] · 21.2k tok · 20s | 74.6% [71–76] · 34.6k tok · 38s |
| outside_conditions | 71.4% [64–79] · 49.5k tok · 27s | 40.5% [36–43] · 71.4k tok · 52s | 52.4% [36–71] · 66.4k tok · 37s | 85.7% [79–93] · 65.2k tok · 45s | 45.2% [29–57] · 49.0k tok · 39s | 81.0% [79–86] · 49.1k tok · 45s |
| all | 80.4% [78–83] · 32.9k tok · 16s | 58.3% [55–62] · 47.2k tok · 32s | 63.4% [62–65] · 45.3k tok · 24s | 93.1% [92–95] · 22.1k tok · 17s | 78.6% [77–79] · 21.0k tok · 18s | 86.6% [86–87] · 28.0k tok · 28s |

## Per change (correct / clarify / wrong over complete runs)

| Schema/change | ACE | AWM | G-Memory | MAVRA | TeCoD | Shared recheck |
|---|---|---|---|---|---|---|
| synthetic/holdout | 18/0/0 of 18 | 12/0/6 of 18 | 13/0/5 of 18 | 18/0/0 of 18 | 18/0/0 of 18 | 18/0/0 of 18 |
| synthetic/append | 16/0/2 of 18 | 9/0/9 of 18 | 8/0/10 of 18 | 18/0/0 of 18 | 18/0/0 of 18 | 18/0/0 of 18 |
| synthetic/backfill | 6/0/0 of 6 | 1/1/4 of 6 | 1/0/5 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 |
| synthetic/correct | 18/0/0 of 18 | 12/0/6 of 18 | 12/0/6 of 18 | 18/0/0 of 18 | 18/0/0 of 18 | 18/0/0 of 18 |
| synthetic/addcol | 6/0/0 of 6 | 1/0/5 of 6 | 1/0/5 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 |
| synthetic/status | 6/0/0 of 6 | 2/0/4 of 6 | 1/0/5 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 |
| synthetic/revision | 15/0/3 of 18 | 10/0/8 of 18 | 11/0/7 of 18 | 18/0/0 of 18 | 15/0/3 of 18 | 17/0/1 of 18 |
| synthetic/dupload | 13/0/5 of 18 | 9/0/9 of 18 | 11/0/7 of 18 | 18/0/0 of 18 | 17/0/1 of 18 | 16/0/2 of 18 |
| synthetic/dimhist | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 |
| synthetic/latekey | 5/0/13 of 18 | 0/0/18 of 18 | 0/0/18 of 18 | 17/0/1 of 18 | 2/0/16 of 18 | 5/10/3 of 18 |
| synthetic/unit | 13/0/5 of 18 | 6/0/12 of 18 | 7/0/11 of 18 | 16/2/0 of 18 | 5/0/13 of 18 | 13/4/1 of 18 |
| synthetic/mirror | 6/0/0 of 6 | 0/0/6 of 6 | 0/0/6 of 6 | 2/0/4 of 6 | 6/0/0 of 6 | 6/0/0 of 6 |
| tpch/holdout | 18/0/0 of 18 | 18/0/0 of 18 | 18/0/0 of 18 | 18/0/0 of 18 | 18/0/0 of 18 | 18/0/0 of 18 |
| tpch/append | 11/0/1 of 12 | 11/0/1 of 12 | 11/0/1 of 12 | 12/0/0 of 12 | 11/0/1 of 12 | 12/0/0 of 12 |
| tpch/backfill | 5/0/1 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 |
| tpch/correct | 12/0/0 of 12 | 12/0/0 of 12 | 12/0/0 of 12 | 12/0/0 of 12 | 12/0/0 of 12 | 12/0/0 of 12 |
| tpch/addcol | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 |
| tpch/status | 6/0/0 of 6 | 5/0/1 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 |
| tpch/revision | 9/0/3 of 12 | 7/0/5 of 12 | 12/0/0 of 12 | 12/0/0 of 12 | 9/0/3 of 12 | 12/0/0 of 12 |
| tpch/dupload | 10/0/2 of 12 | 11/0/1 of 12 | 12/0/0 of 12 | 12/0/0 of 12 | 12/0/0 of 12 | 11/0/1 of 12 |
| tpch/dimhist | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 6/0/0 of 6 |
| tpch/latekey | 0/0/12 of 12 | 0/0/12 of 12 | 0/0/12 of 12 | 0/12/0 of 12 | 0/0/12 of 12 | 0/12/0 of 12 |
| tpch/unit | 7/0/5 of 12 | 6/0/6 of 12 | 9/0/3 of 12 | 12/0/0 of 12 | 3/0/9 of 12 | 9/2/1 of 12 |
| tpch/mirror | 4/0/2 of 6 | 5/0/1 of 6 | 6/0/0 of 6 | 6/0/0 of 6 | 5/0/1 of 6 | 6/0/0 of 6 |

Cost: CNY 27.53 charged over 7889 calls (0 errors).
