# AQICN Air Pollutant Tool
A command line tool which uses the the WAQI public API to report realtime PM2.5 results

## instructions
- in order to use this tool, please generate a free key from https://aqicn.org/data-platform/token/

## example usage
- An area with 53 stations
  - `python main.py token 32.999436,116.09123,40.235643,116.78438`
- An area with 27 stations
  - `python main.py token 37.999436,116.09123,40.235643,116.78438 0.5 8`
- An area with 4 stations
  - `python main.py token 39.999436,116.09123,40.235643,116.78438 0.5 8`