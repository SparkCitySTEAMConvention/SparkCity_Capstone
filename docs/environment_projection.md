# Environment event-day projection map

The November 3–5, 2027 map shows a **planning baseline**, not a forecast for
those dates. For each of nine map locations and each calendar day, it retrieves
Open-Meteo historical reanalysis daily mean temperature (°F) and daily total
precipitation (mm) for November 3–5 in 2021–2026. The displayed value is the
arithmetic mean across the six matching historical dates; map tooltips also show
the minimum and maximum daily values observed in those six years. Those ranges
are historical extremes at the sampled points, **not prediction intervals**.

The map uses fixed color bands so dates can be compared without the legend
changing. The circles represent coarse source model grid cells (approximately
9 km resolution); multiple nearby circles may use the same underlying cell.
Colors between points are not spatial forecasts, and the precipitation layer
shows a historical average daily amount, not a probability of rain. Check an
actual weather forecast close to the event.

The S2 observations remain in the separate convention outlook. The projected map uses reanalysis to provide consistent spatial coverage; S2 observations are used for the separate November planning metrics and are not interpolated into the map.
