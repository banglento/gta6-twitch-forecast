# gta6-twitch-forecast
[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/banglento/gta6-twitch-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/banglento/gta6-twitch-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecasts how many people watch Grand Theft Auto VI live on Twitch in each hour of its release day (2026-11-19 UTC), from the first hour's viewer count. It builds the launch-day curve from the release-day shapes of past big-game launches in the case file (per-hour median log-ratio to hour 1), anchors it on the case's own hour-1 print, stretches the rise when hour 1 is weak next to the launch-eve hype peak, and reports five quantiles per hour with a log-normal spread that widens through the day. Standard library only, deterministic, no network.

## Run it

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

That reads every `*.in` case in `input/` and writes one `<id>.out` forecast per case to `out/`, with 23 rows (hours 2–24) of five quantiles each. Without the environment variables it reads `/input` and writes `/output`, as the grader does.

<sub>Entered on [make.fun](https://make.fun/?ref=d4q39cjn&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
