# Environment event-day projection map

The April 6–8, 2027 map shows a **planning baseline**, not a forecast for
those dates. For each of nine map locations and each calendar day, it retrieves
Open-Meteo historical reanalysis daily mean temperature (°F) and daily total
precipitation (mm) for April 6–8 in 2021–2026. The displayed value is the
arithmetic mean across the six matching historical dates; map tooltips also show
the minimum and maximum daily values observed in those six years. Those ranges
are historical extremes at the sampled points, **not prediction intervals**.

The map uses fixed color bands so dates can be compared without the legend
changing. The circles represent coarse source model grid cells (approximately
9 km resolution); multiple nearby circles may use the same underlying cell.
Colors between points are not spatial forecasts, and the precipitation layer
shows a historical average daily amount, not a probability of rain. Check an
actual weather forecast close to the event.

The S2 observations remain in the separate convention outlook. April 2025 S2
weather locations form a narrow band near latitude 40.78 and April 2026
locations a separate band near latitude 40.69. Their limited and nonoverlapping
spatial coverage cannot support a citywide projected heatmap. Historical air
quality for matching dates is available only for 2025; this map does not
project air quality.

Source and method details:
[Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api).
The API is queried at runtime; the result is cached for 24 hours in Streamlit.
If it is unavailable, the map displays an availability warning while the S2
outlook remains usable.
